"""The same agent using Temporal's OpenAI Agents SDK integration. NOT used by tests; untested here.

    uv add temporalio-openai-agents        # needs OPENAI_API_KEY (or a compatible provider)

Import paths below follow docs.temporal.io/develop/python/integrations/openai-agents; check them
against your installed version. Register OpenAIAgentsPlugin on BOTH the client and the worker:

    client = await Client.connect("localhost:7233", plugins=[
        OpenAIAgentsPlugin(model_params=ModelActivityParameters(start_to_close_timeout=timedelta(seconds=60)))])
    Worker(client, task_queue="solutions-day26-sdk", workflows=[SdkTroubleshootingAgent],
           activities=[get_interfaces, get_lldp, get_bgp_summary, get_logging])
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents import Agent, Runner
    from temporalio.openai_agents.workflow import activity_as_tool

    from solutions.shared.activities import get_bgp_summary, get_interfaces, get_lldp, get_logging


@workflow.defn
class SdkTroubleshootingAgent:
    @workflow.run
    async def run(self, question: str) -> str:
        t = timedelta(seconds=30)
        agent = Agent(
            name="NetOps troubleshooter",
            instructions="You diagnose Arista EOS issues. Use tools; never guess device state. Tools are read-only.",
            tools=[activity_as_tool(get_interfaces, start_to_close_timeout=t),
                   activity_as_tool(get_lldp, start_to_close_timeout=t),
                   activity_as_tool(get_bgp_summary, start_to_close_timeout=t),
                   activity_as_tool(get_logging, start_to_close_timeout=t)],
        )
        result = await Runner.run(agent, question)
        return result.final_output
