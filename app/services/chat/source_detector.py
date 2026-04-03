def detect_zoho_source(headers) -> str:
    # Zoho SalesIQ
    if "x-siqsignature" in headers:
        return "salesiq"

    # Zoho Flow
    if "x-webhook-secret" in headers:
        return "flow"

    if headers.get("x-source") == "zoho_form_lead":
        return "flow"

    if headers.get("user-agent") == "ZohoFlow":
        return "flow"

    return "unknown"

def resolve_channel(source: str) -> str:
    if source == "flow":
        return "flow"

    if source == "salesiq":
        return "website"

    return "website"
