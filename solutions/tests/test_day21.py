import pytest
from temporalio.api.common.v1 import Payload

from solutions.day21.workflows import ORCHESTRATION_TASK_QUEUE, RoutedBackupWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.settings import DEVICE_IO_TASK_QUEUE
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_activities_run_on_device_io_queue():
    async with await time_skipping_env() as env:
        async with worker(env, ORCHESTRATION_TASK_QUEUE, [RoutedBackupWorkflow], activities=[]), \
                worker(env, DEVICE_IO_TASK_QUEUE, [], activities=DEVICE_ACTIVITIES):
            r = await env.client.execute_workflow(RoutedBackupWorkflow.run, id=wf_id(),
                                                  task_queue=ORCHESTRATION_TASK_QUEUE)
    assert len(r.saved) == 4


async def test_encryption_codec_round_trip():
    fernet = pytest.importorskip("cryptography.fernet")
    from solutions.day21.codec import EncryptionCodec

    codec = EncryptionCodec(fernet.Fernet.generate_key())
    original = Payload(metadata={"encoding": b"json/plain"}, data=b'{"password":"admin"}')
    encoded = await codec.encode([original])
    assert b"admin" not in encoded[0].data
    assert (await codec.decode(encoded))[0] == original
