# Task Management

Prioritize tasks, detect overdue items, and help with daily planning.

## When to Use

- A new task is created (triggered automatically via hook)
- Daily review schedule fires (weekday mornings)
- User asks to prioritize, plan their day, or review tasks

## Process

1. **Assess new tasks**: When a task is created without a priority, evaluate it:
   - Check the `due_date` — tasks due within 24 hours get `high` or `critical`
   - Check the `effort` — `epic` tasks with near due dates get `critical`
   - Check the project — inherit urgency from project due dates
   - Default to `medium` if no signals are present

2. **Daily review**: Scan all active tasks and surface:
   - Overdue tasks (past `due_date`) — flag these first
   - Tasks due today — sorted by priority
   - Tasks due this week with no priority set
   - Stale tasks (no update in 7+ days)

3. **Project progress**: When reviewing tasks, summarize project health:
   - Count active vs. completed tasks per project
   - Flag projects with many overdue tasks
   - Note projects approaching their `due_date` with incomplete tasks

4. **Suggest next actions**: After review, recommend:
   - Which tasks to tackle first (highest priority, smallest effort)
   - Tasks that could be broken down (large/epic effort, no subtasks)
   - Tasks that may need re-prioritization

## Priority Assignment Rubric

| Signal | Suggested Priority |
|--------|--------------------|
| Due today, any effort | `critical` |
| Due within 3 days, medium+ effort | `high` |
| Due within 7 days | `medium` |
| No due date, part of active project | `medium` |
| No due date, standalone | `low` |
| Blocked or waiting on external input | `low` (add "blocked" tag) |

## Rules

- Never change a user-set priority without asking first
- Always explain why you assigned or changed a priority
- When marking a task complete, set `completed_at` to the current timestamp
- Archive completed tasks after 30 days to keep the active list clean
- Link tasks to their project via a `belongs_to` relationship
- Link tasks to labels via a `labeled` relationship
