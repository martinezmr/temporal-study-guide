import nexusrpc

from solutions.day22.service import Policy, PolicyRequest
from solutions.shared.models import ComplianceInput, ComplianceResult


@nexusrpc.service
class ComplianceService:
    get_policy: nexusrpc.Operation[PolicyRequest, Policy]
    remediate: nexusrpc.Operation[ComplianceInput, ComplianceResult]  # async: backed by a workflow
