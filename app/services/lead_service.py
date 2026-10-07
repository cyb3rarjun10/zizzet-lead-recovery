import re
from typing import Optional
from app.schemas.analysis import LeadAnalysisOutput
from app.schemas.lead import LeadAnalysisRequest
from app.services.llm_service import get_llm_service

OPT_OUT_PATTERNS = [
    r"\bstop\b",
    r"\bunsubscribe\b",
    r"don'?t\s+message\s+me",
    r"do\s+not\s+contact",
    r"not\s+interested",
    r"remove\s+me",
]


def check_for_opt_out(conversation_messages) -> bool:
    for item in conversation_messages:
        if item.role == "customer":
            text = item.message.lower()
            for pattern in OPT_OUT_PATTERNS:
                if re.search(pattern, text):
                    return True
    return False


def build_analysis_prompt(request: LeadAnalysisRequest) -> str:
    customer_info = (
        f"Name: {request.customer.name or 'Unknown'}, "
        f"Phone: {request.customer.phone or 'N/A'}, "
        f"Email: {request.customer.email or 'N/A'}"
    )
    lead_info = (
        f"Source: {request.lead.source}, "
        f"Status: {request.lead.status}, "
        f"Created: {request.lead.created_at or 'N/A'}, "
        f"Last Contacted: {request.lead.last_contacted_at or 'N/A'}"
    )

    conv_lines = [
        f"[{msg.role.upper()}]: {msg.message}" for msg in request.conversation
    ]
    conv_text = "\n".join(conv_lines) if conv_lines else "No conversation recorded."

    return (
        f"=== Customer Profile ===\n{customer_info}\n\n"
        f"=== Lead Metadata ===\n{lead_info}\n\n"
        f"=== Conversation History ===\n{conv_text}\n\n"
        "Evaluate this lead according to these guidelines:\n"
        "1. High employee count or direct pricing inquiries indicate high intent/priority.\n"
        "2. General questions indicate low/medium priority with educational follow-ups.\n"
        "3. Demo requests require demo scheduling as the next best action.\n"
        "Return the structured output matching the JSON schema."
    )


def process_lead_analysis(
    request: LeadAnalysisRequest, llm_override: Optional[object] = None
) -> LeadAnalysisOutput:
    if check_for_opt_out(request.conversation):
        return LeadAnalysisOutput(
            lead_score=0,
            priority="low",
            intent="opt_out",
            stage="opted_out",
            summary="Customer explicitly requested not to be contacted or opted out.",
            next_best_action="Mark lead as Do Not Contact and close recovery workflow.",
            follow_up_channel="whatsapp",
            follow_up_message=None,
            do_not_contact=True,
        )

    llm = llm_override or get_llm_service()
    prompt = build_analysis_prompt(request)
    return llm.analyze_lead(prompt)