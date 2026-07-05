# Scheduler Design Prompt

## Goal

Build reliable local scheduling for birthday messages, festival greetings, reminders, and future tasks.

## Current Behavior

The scheduler reads `data/birthday_tasks.csv`, matches today's date, and prints dry-run tasks.

## Required Safety Behavior

- Scheduler defaults to dry-run.
- It must not send to normal contacts unless a future prompt explicitly enables that path.
- It must log planned actions and blocked actions.
- It must support previewing tasks before execution.

## Task Fields

Birthday tasks:

```text
wechat_remark,birthday,message,enabled
```

Future general tasks may include:

```text
task_id,target,message_template,run_at,enabled,last_run_at
```

## Scheduling Strategy

- Use `schedule` for lightweight local scheduling.
- Keep actual task matching pure and unit-testable.
- Keep send execution behind safety policy.
- Add manual command checks before background loops.

## Testing

Test date parsing, enabled filtering, dry-run output, and blocked real-send behavior.
