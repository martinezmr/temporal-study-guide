from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.day26.agent import AgentInput, AgentResult, run_agent

TASK_QUEUE = "solutions-day28"
GUARDED_TOOLS = ["get_interfaces", "get_lldp", "get_logging", "run_show_command"]


@workflow.defn
class GuardedTroubleshootingWorkflow:
    """Like Day 26, plus a free-form `run_show_command` tool whose allowlist is enforced in the activity."""

    @workflow.run
    async def run(self, inp: AgentInput) -> AgentResult:
        return await run_agent(inp, GUARDED_TOOLS)
