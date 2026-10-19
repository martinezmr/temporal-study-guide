from temporalio.common import SearchAttributeKey

DEVICE_NAME = SearchAttributeKey.for_keyword("DeviceName")
SITE = SearchAttributeKey.for_keyword("Site")
COMPLIANCE_STATE = SearchAttributeKey.for_keyword("ComplianceState")
ALL = [DEVICE_NAME, SITE, COMPLIANCE_STATE]
