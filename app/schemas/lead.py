from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.analysis import LeadAnalysisOutput


class CustomerInfo(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class LeadMeta(BaseModel):
    source: str = "whatsapp"
    status: str = "contacted"
    created_at: Optional[str] = None
    last_contacted_at: Optional[str] = None


class ConversationMessage(BaseModel):
    role: Literal["customer", "agent", "system"]
    message: str


class LeadAnalysisRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    lead_id: str = Field(..., min_length=1)
    customer: Optional[CustomerInfo] = Field(default_factory=CustomerInfo)
    lead: Optional[LeadMeta] = Field(default_factory=LeadMeta)
    conversation: List[ConversationMessage] = Field(default_factory=list)


class LeadAnalysisResponse(BaseModel):
    tenant_id: str
    lead_id: str
    analysis: LeadAnalysisOutput
    analyzed_at: datetime


class WebhookLeadEvent(BaseModel):
    event_id: str = Field(
        ..., min_length=1, description="Unique idempotency key for this event"
    )
    tenant_id: str = Field(..., min_length=1)
    lead_id: str = Field(..., min_length=1)
    customer: Optional[CustomerInfo] = Field(default_factory=CustomerInfo)
    lead: Optional[LeadMeta] = Field(default_factory=LeadMeta)
    conversation: List[ConversationMessage] = Field(default_factory=list)