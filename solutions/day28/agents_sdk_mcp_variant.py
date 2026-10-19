"""Using the MCP server above from a durable OpenAI Agents SDK agent. NOT used by tests; untested here.

    uv add "temporalio-openai-agents[mcp]"
Serve mcp_server.py over streamable HTTP (mcp.run(transport="streamable-http")), then on the worker:

    from agents.mcp import MCPServerStreamableHttp
    from temporalio.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin

    plugin = OpenAIAgentsPlugin(
        model_params=ModelActivityParameters(start_to_close_timeout=timedelta(seconds=60)),
        mcp_servers={"netops": lambda: MCPServerStreamableHttp(params={"url": "http://localhost:8000/mcp"})},
    )
Check the factory signature in docs.temporal.io/develop/python/integrations/openai-agents for your version.
"""

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from agents import Agent, Runner
    from temporalio.openai_agents.workflow import temporal_mcp_server


@workflow.defn
class McpTroubleshootingAgent:
    @workflow.run
    async def run(self, question: str) -> str:
        agent = Agent(name="NetOps troubleshooter", instructions="Diagnose using the netops tools. Read-only.",
                      mcp_servers=[temporal_mcp_server("netops")])
        return (await Runner.run(agent, question, max_turns=8)).final_output
