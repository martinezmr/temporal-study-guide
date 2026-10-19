"""The contract. The ONLY thing caller and handler share."""

import nexusrpc
from pydantic import BaseModel


class PolicyRequest(BaseModel):
    role: str


class Policy(BaseModel):
    role: str
    required_lines: list[str]


@nexusrpc.service
class ComplianceService:
    get_policy: nexusrpc.Operation[PolicyRequest, Policy]
