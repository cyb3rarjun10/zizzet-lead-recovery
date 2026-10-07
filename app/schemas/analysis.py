from typing import Literal, Optional
from pydantic import BaseModel, Field


class LeadAnalysisOutput(BaseModel):
    lead_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence/intent score of the lead from 0 to 100",
    )
    priority: Literal["high", "medium", "low"] = Field(
        ..., description="Action priority level"
    )
    intent: str = Field(
        ...,
        description="Detected intent such as purchase, demo_request, inquiry, or opt_out",
    )
    stage: str = Field(
        ...,
        description="Sales funnel stage like pricing_interest, evaluation, or opted_out",
    )
    summary: str = Field(
        ...,
        description="Concise 1-2 sentence overview of the conversation and customer need",
    )
    next_best_action: str = Field(
        ..., description="Recommended immediate next step for the sales rep"
    )
    follow_up_channel: Literal["whatsapp", "email", "sms", "call"] = Field(
        default="whatsapp"
    )
    follow_up_message: Optional[str] = Field(
        default=None,
        description="Personalized follow-up message to send, or null if opted out",
    )
    do_not_contact: bool = Field(
        default=False,
        description="True if customer expressed clear intent not to be contacted or said STOP",
    )