import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPToolClient:
    """
    Connects to an MCP server (your mcp_server.py) and exposes:
      - list_tools()
      - call_tool(tool_name, arguments)

    This implementation uses the MCP stdio transport by spawning the server as a subprocess.
    That matches how FastMCP servers run by default via `mcp.run()`.
    """

    def __init__(
        self,
        server_command: str,
        server_args: list[str],
        server_env: Optional[dict[str, str]] = None,
    ) -> None:
        self._server_params = StdioServerParameters(
            command=server_command,
            args=server_args,
            env=server_env,
        )
        self._read = None
        self._write = None
        self._stdio_cm = None
        self._session_cm = None
        self.session: Optional[ClientSession] = None

    async def __aenter__(self) -> "MCPToolClient":
        self._stdio_cm = stdio_client(self._server_params)
        self._read, self._write = await self._stdio_cm.__aenter__()

        self._session_cm = ClientSession(self._read, self._write)
        self.session = await self._session_cm.__aenter__()

        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc, tb)
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(exc_type, exc, tb)

        self.session = None
        self._read = None
        self._write = None
        self._stdio_cm = None
        self._session_cm = None

    async def list_tools(self) -> list[ToolSpec]:
        if self.session is None:
            raise RuntimeError("MCP session not initialized")

        tools = await self.session.list_tools()

        specs: list[ToolSpec] = []
        for t in tools:
            name = getattr(t, "name", "")
            description = getattr(t, "description", "") or ""
            input_schema = getattr(t, "inputSchema", None) or {}
            specs.append(ToolSpec(name=name, description=description, input_schema=input_schema))

        return specs

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if self.session is None:
            raise RuntimeError("MCP session not initialized")

        result = await self.session.call_tool(tool_name, arguments=arguments)
        
        return self._normalize_tool_result(result)

    def _normalize_tool_result(self, result: Any) -> Any:
        """
        MCP tool results often contain `content` items (text, json, images).
        Return a compact JSON-like value when possible.
        """
        if result is None:
            return None

        content = getattr(result, "content", None)
        if content is None:
            return result

        normalized_items: list[Any] = []
        for item in content:
            item_type = getattr(item, "type", None)
            if item_type == "text":
                text = getattr(item, "text", "")
                normalized_items.append(text)
            elif item_type == "json":
                data = getattr(item, "data", None)
                normalized_items.append(data)
            else:
                normalized_items.append({"type": item_type})

        if len(normalized_items) == 1:
            return normalized_items[0]
        return normalized_items


class ReActAgent:
    """
    Single-agent ReAct loop:
      - Ask the model what to do next
      - If it chooses an MCP tool, execute it and feed the observation back
      - Stop when the model produces Final

    The model is instructed to output either:
      Action: {"tool": "...", "arguments": {...}, "reason": "..."}
    or:
      Final: "..."
    """

    def __init__(self, model: str, openai_client: OpenAI, tools: list[ToolSpec]) -> None:
        self.model = model
        self.client = openai_client
        self.tools = tools
        self.tool_index = {t.name: t for t in tools}

        self.instructions = self._build_instructions(tools)

    def _build_instructions(self, tools: list[ToolSpec]) -> str:
        tool_lines: list[str] = []
        for t in tools:
            schema_json = json.dumps(t.input_schema, ensure_ascii=False)
            desc = t.description.strip() if t.description else ""
            tool_lines.append(f"- {t.name}: {desc}\n  input_schema: {schema_json}")

        tools_block = "\n".join(tool_lines) if tool_lines else "- (no tools available)"

        return (
            "You are a CLI automation agent that can use MCP tools to execute real actions.\n"
            "You must follow a strict ReAct-style loop: decide whether a tool call is needed, "
            "then either call exactly one tool or produce the final answer.\n\n"
            "Available tools:\n"
            f"{tools_block}\n\n"
            "Output format rules:\n"
            "1) If you need to use a tool, output exactly two lines:\n"
            '   Action: {"tool":"<tool_name>","arguments":{...},"reason":"<one short sentence>"}\n'
            "   (no other text)\n"
            "2) If you are done, output exactly one line:\n"
            '   Final: "<your answer>"\n'
            "3) Tool arguments must be valid JSON. Use only the tools listed.\n"
            "4) Never include hidden reasoning or multi-paragraph thoughts. Keep 'reason' to one sentence.\n"
        )

    def _parse_model_output(self, text: str) -> tuple[str, Any]:
        """
        Returns ("action", action_dict) or ("final", final_text).

        Intentionally keep parsing strict so the agent doesn't drift.
        """
        if not text:
            raise ValueError("Empty model output")

        stripped = text.strip()

        if stripped.startswith("Final:"):
            final = stripped[len("Final:") :].strip()
            if final.startswith('"') and final.endswith('"') and len(final) >= 2:
                final = final[1:-1]
            return ("final", final)

        if stripped.startswith("Action:"):
            payload = stripped[len("Action:") :].strip()
            try:
                action = json.loads(payload)
            except json.JSONDecodeError as e:
                raise ValueError(f"Action JSON was invalid: {e}") from e

            if not isinstance(action, dict):
                raise ValueError("Action must be a JSON object")

            tool = action.get("tool")
            arguments = action.get("arguments", {})
            if not isinstance(tool, str) or not tool:
                raise ValueError("Action.tool must be a non-empty string")
            if not isinstance(arguments, dict):
                raise ValueError("Action.arguments must be an object")

            return ("action", action)

        raise ValueError("Model output must start with 'Action:' or 'Final:'")

    def _chat(self, user_input: str, history: list[dict[str, str]]) -> str:
        """
        Sends a chat completion with developer instructions + history + user_input.
        """
        messages = [{"role": "developer", "content": self.instructions}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return completion.choices[0].message.content or ""

    async def run(self, mcp: MCPToolClient, prompt: str, max_steps: int = 8) -> str:
        history: list[dict[str, str]] = []

        user_input = prompt
        for step in range(1, max_steps + 1):
            model_text = self._chat(user_input=user_input, history=history)
            kind, payload = self._parse_model_output(model_text)

            if kind == "final":
                return str(payload)

            action = payload
            tool_name = action["tool"]
            arguments = action.get("arguments", {})

            if tool_name not in self.tool_index:
                history.append({"role": "assistant", "content": model_text})
                user_input = (
                    f"Tool '{tool_name}' is not available. "
                    f"Choose one of: {', '.join(sorted(self.tool_index.keys()))}.\n"
                    "Respond using the required format."
                )
                continue

            try:
                tool_result = await mcp.call_tool(tool_name, arguments)
            except Exception as e:
                history.append({"role": "assistant", "content": model_text})
                user_input = (
                    f"Tool call failed for '{tool_name}' with error: {type(e).__name__}: {e}\n"
                    "Either try a different tool or produce a Final answer."
                )
                continue

            history.append({"role": "assistant", "content": model_text})
            observation = json.dumps(tool_result, ensure_ascii=False)
            user_input = (
                f"Observation from tool '{tool_name}': {observation}\n"
                "If another tool call is needed, do it now. Otherwise produce Final."
            )

        return "Reached max_steps without a Final answer."


async def main() -> None:
    parser = argparse.ArgumentParser(description="ReAct CLI agent with MCP tool execution (n8n via MCP server).")
    parser.add_argument("--prompt", required=True, help="User prompt to run through the agent.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o"), help="OpenAI model name.")
    parser.add_argument(
        "--mcp-server",
        default=os.environ.get("MCP_SERVER_PATH", "mcp_server.py"),
        help="Path to your FastMCP server file (stdio).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Maximum ReAct iterations before stopping.",
    )
    args = parser.parse_args()

    openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    server_command = sys.executable
    server_args = [args.mcp_server]

    async with MCPToolClient(server_command=server_command, server_args=server_args) as mcp:
        tool_specs = await mcp.list_tools()

        agent = ReActAgent(
            model=args.model,
            openai_client=openai_client,
            tools=tool_specs,
        )

        result = await agent.run(mcp=mcp, prompt=args.prompt, max_steps=args.max_steps)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
