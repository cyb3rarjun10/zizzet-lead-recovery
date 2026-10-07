from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    leads = relationship("Lead", back_populates="tenant", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    external_lead_id = Column(String(128), nullable=False, index=True)  # e.g. "lead_1024"
    customer_name = Column(String(128), nullable=True)
    customer_phone = Column(String(32), nullable=True)
    source = Column(String(64), default="whatsapp")
    status = Column(String(64), default="contacted")
    last_contacted_at = Column(DateTime, nullable=True)
    do_not_contact = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Scoped uniqueness per tenant
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_lead_id", name="uq_tenant_lead"),
    )

    tenant = relationship("Tenant", back_populates="leads")
    analyses = relationship("LeadAnalysis", back_populates="lead", cascade="all, delete-orphan", order_by="desc(LeadAnalysis.created_at)")


class LeadAnalysis(Base):
    __tablename__ = "lead_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    lead_score = Column(Integer, nullable=False)
    priority = Column(String(32), nullable=False)  # high, medium, low
    intent = Column(String(64), nullable=False)    # purchase, inquiry, demo_request, etc.
    stage = Column(String(64), nullable=False)     # pricing_interest, evaluation, opted_out, etc.
    summary = Column(Text, nullable=False)
    next_best_action = Column(Text, nullable=False)
    follow_up_channel = Column(String(32), default="whatsapp")
    follow_up_message = Column(Text, nullable=True)
    do_not_contact = Column(Boolean, default=False)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="analyses")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False, index=True)
    status = Column(String(32), default="pending")  # pending, completed, failed
    payload = Column(Text, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Enforces Case E: exact duplicate webhook payload/event cannot be ingested twice
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_idempotency"),
    )