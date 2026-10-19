"""Create a Nexus endpoint from Python (same as `temporal operator nexus endpoint create`)."""

from temporalio.api.nexus.v1 import EndpointSpec, EndpointTarget
from temporalio.api.operatorservice.v1 import CreateNexusEndpointRequest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode


async def ensure_endpoint(client: Client, name: str, target_namespace: str, target_task_queue: str) -> None:
    try:
        await client.operator_service.create_nexus_endpoint(
            CreateNexusEndpointRequest(
                spec=EndpointSpec(
                    name=name,
                    target=EndpointTarget(
                        worker=EndpointTarget.Worker(namespace=target_namespace, task_queue=target_task_queue)),
                )
            )
        )
        print(f"created Nexus endpoint {name} -> {target_namespace}/{target_task_queue}")
    except RPCError as e:
        if e.status != RPCStatusCode.ALREADY_EXISTS:
            raise
        print(f"Nexus endpoint {name} already exists")
