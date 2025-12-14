import os
import re
from groq import Groq 
from tools import * 

# from dotenv import load_dotenv
# load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_key)

# chat_completion = client.chat.completions.create(
#     messages=[
#         {
#             "role": "user",
#             "content": "Explain the importance of fast language models",
#         }
#     ],
#     model="llama3-8b-8192",
# )
# print(chat_completion.choices[0].message.content)

with open("system_prompt.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read()
# print(system_prompt)

class Agent:
    def __init__(self, client: Groq, system: str = "") -> None:
        self.client = client
        self.system = system
        self.messages: list = []
        if self.system:
            self.messages.append({"role": "system", "content": system})

    def __call__(self, message=""):
        if message:
            self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result

    def execute(self):
        completion = client.chat.completions.create(
            model="llama3-70b-8192", messages=self.messages
        )
        return completion.choices[0].message.content
    
def loop(max_iterations=5, query: str = ""):

    agent = Agent(client=client, system=system_prompt)

    tools = ["calculate", "wikipedia"]

    next_prompt = query

    i = 0
  
    while i < max_iterations:
        i += 1
        result = agent(next_prompt)
        print(result)

        if "PAUSE" in result and "Action" in result:
            action = re.findall(r"Action: ([a-z_]+): (.+)", result, re.IGNORECASE) # Action: calculate: 5.972e24 * 2 -> [("calculate", "5.972e24 * 2")]
            print(action) 
            chosen_tool = action[0][0]
            arg = action[0][1]

            if chosen_tool in tools:
                result_tool = eval(f"{chosen_tool}('{arg}')")
                next_prompt = f"Observation: {result_tool}"

            else:
                next_prompt = "Observation: Tool not found"

            print(next_prompt)
            continue

        if "Answer" in result:
            break
    
    return agent.messages, result

def extract_answer(result: str):
    """Extracts only the 'Answer' part from the LLM result."""
    match = re.search(r"Answer:\s*(.*)", result, re.IGNORECASE)
    if match:
        return match.group(1).strip()  
    return "No answer found."

messages, result = loop(query="What is the square root of mass of the earth multiplied by 10?")
print("Result: ", extract_answer(result))
print("Messages: ", messages)
