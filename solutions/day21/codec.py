"""Optional payload encryption. `uv add cryptography`, then:

    client = await Client.connect(..., data_converter=dataclasses.replace(
        pydantic_data_converter, payload_codec=EncryptionCodec(key)))

Use the same codec on every client and worker. The UI then shows ciphertext unless you run a codec server.
"""

from collections.abc import Sequence

from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec

ENCODING = b"binary/encrypted"


class EncryptionCodec(PayloadCodec):
    def __init__(self, key: bytes) -> None:
        from cryptography.fernet import Fernet  # optional dependency

        self._fernet = Fernet(key)

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        return [Payload(metadata={"encoding": ENCODING}, data=self._fernet.encrypt(p.SerializeToString()))
                for p in payloads]

    async def decode(self, payloads: Sequence[Payload]) -> list[Payload]:
        out = []
        for p in payloads:
            if p.metadata.get("encoding") != ENCODING:
                out.append(p)
                continue
            decoded = Payload()
            decoded.ParseFromString(self._fernet.decrypt(p.data))
            out.append(decoded)
        return out
