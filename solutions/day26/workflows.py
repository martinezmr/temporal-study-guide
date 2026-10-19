from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.day26.agent import AgentInput, AgentResult, run_agent

TASK_QUEUE = "solutions-day26"
READ_ONLY_TOOLS = ["get_interfaces", "get_lldp", "get_bgp_summary", "get_logging"]


@workflow.defn
class TroubleshootingAgentWorkflow:
    @workflow.run
    async def run(self, inp: AgentInput) -> AgentResult:
        return await run_agent(inp, READ_ONLY_TOOLS)
