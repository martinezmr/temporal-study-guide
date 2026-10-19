# Day 01 — Solution

The Day 1 code already lives in the repo: `src/netops_temporal/{activities,workflows,workers,starters}/hello.py` and `tests/test_hello.py`. Today's work is reading the history, not writing code.

## The events in `HelloWorkflow`'s history

| # | Event | Produced by | Meaning |
| --- | --- | --- | --- |
| 1 | `WorkflowExecutionStarted` | Client (your starter) → server | Input `"Manny"`, task queue `netops-orchestration` |
| 2 | `WorkflowTaskScheduled` | Server | "A worker should run the workflow code now" |
| 3 | `WorkflowTaskStarted` | Worker picked it up | |
| 4 | `WorkflowTaskCompleted` | Worker | The code ran until `execute_activity` and returned a command |
| 5 | `ActivityTaskScheduled` | Server (from the worker's command) | `say_hello` queued, with its timeouts and retry policy |
| 6 | `ActivityTaskStarted` | Worker picked it up | Written lazily: you'll see it once the activity finishes |
| 7 | `ActivityTaskCompleted` | Worker | Result `"Hello, Manny!"` stored in history |
| 8–10 | `WorkflowTaskScheduled/Started/Completed` | Server + worker | Workflow code resumes with the result |
| 11 | `WorkflowExecutionCompleted` | Worker's final command | Result returned to the client |

## Break-it answers

- **No worker running:** the workflow sits at event 2. Nothing is lost; the task waits on the queue. The UI's *Pending* section and `temporal task-queue describe --task-queue netops-orchestration` (no pollers) show why.
- **Container restart:** the history survives because of `--db-filename /data/temporal.db` on the `temporal-data` volume.

## CLI cheat-sheet

```bash
temporal workflow list --query 'WorkflowType="HelloWorkflow"'
temporal workflow describe --workflow-id hello-manny
temporal workflow show --workflow-id hello-manny
temporal workflow show --workflow-id hello-manny -o json > tests/histories/hello.json
temporal task-queue describe --task-queue netops-orchestration
```
