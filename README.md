# ReAct AI Agent with MCP for Workflow Automation
AI agent following ReAct (Reasoning + Action) architecture with CLI interface connected to MCP server for tool calling (email, calendar, social media, web search etc.) to automate daily workflows and schedule tasks from user prompts.

## Example Run
**Prompt:** *"Summarise my unread emails from today, create tasks for anything urgent, and schedule follow-ups tomorrow at 10am."*

```bash
Thought: The user wants inbox processing, task creation, and calendar scheduling.
I need to first fetch unread emails from today using the email tool.

Action: email.fetch_unread
PAUSE
[('email.fetch_unread', {'date': 'today'})]

Observation: Retrieved 7 unread emails. 
3 emails are marked high priority related to meetings and deadlines.

Thought: I should summarise the unread emails and identify urgent items.
Then I need to create tasks for the urgent emails.

Action: task.create
PAUSE
[('task.create', {
  'tasks': [
    {'title': 'Reply to client about contract deadline', 'priority': 'high'},
    {'title': 'Prepare slides for tomorrow’s meeting', 'priority': 'high'},
    {'title': 'Confirm availability for project kickoff call', 'priority': 'high'}
  ]
})]

Observation: 3 tasks successfully created in the task manager.

Thought: Now I need to schedule follow-up reminders for tomorrow at 10am.

Action: calendar.create_event
PAUSE
[('calendar.create_event', {
  'title': 'Email follow-ups',
  'date': 'tomorrow',
  'time': '10:00'
})]

Observation: Calendar event successfully created.

Thought: I should provide the user with a concise summary of what was done.

Action:
Answer: I summarised your unread emails, created tasks for urgent items, and scheduled follow-up reminders for tomorrow at 10am.
```
