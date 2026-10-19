import nexusrpc
from pydantic import BaseModel

from solutions.shared.models import ComplianceInput, ComplianceResult

__all__ = ["ComplianceInput", "ComplianceResult", "ComplianceService", "Policy", "PolicyRequest"]


class PolicyRequest(BaseModel):
    role: str


class Policy(BaseModel):
    role: str
    required_lines: list[str]


@nexusrpc.service(name="NetOpsCompliance")
class ComplianceService:
    get_policy: nexusrpc.Operation[PolicyRequest, Policy]
    remediate: nexusrpc.Operation[ComplianceInput, ComplianceResult]
