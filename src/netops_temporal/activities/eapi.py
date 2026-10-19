from temporalio import activity
from src.netops_temporal.constants import DEVICE_HOSTS
import pyeapi

@activity.defn
async def get_device_facts(device: str) -> dict:
    host = pyeapi.connect(
        transport="https",
        host=DEVICE_HOSTS[device],
        username="admin",
        password="admin"
        port=443
        )
    node = pyeapi.client.Node(host)
    result = await node.run_commands(["show version"])
    response = result[0]
    return {
        "device": device,
        "model": response["modelName"],
    }
    