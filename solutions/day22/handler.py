"""Lives with the 'compliance team', in the compliance namespace."""

import nexusrpc
import nexusrpc.handler

from solutions.day22.service import ComplianceService, Policy, PolicyRequest

POLICIES = {
    "access": ["ntp server 10.0.0.1", "logging host 10.0.0.50", "aaa authorization exec default local"],
    "router": ["ntp server 10.0.0.1", "logging host 10.0.0.50", "aaa authorization exec default local"],
}


@nexusrpc.handler.service_handler(service=ComplianceService)
class ComplianceServiceHandler:
    @nexusrpc.handler.sync_operation
    async def get_policy(self, ctx: nexusrpc.handler.StartOperationContext, input: PolicyRequest) -> Policy:
        if input.role not in POLICIES:
            raise nexusrpc.HandlerError(f"no policy for role {input.role!r}", type=nexusrpc.HandlerErrorType.NOT_FOUND)
        return Policy(role=input.role, required_lines=POLICIES[input.role])
