import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_or_create_tenant
from app.db.database import get_db
from app.db.models import Lead, LeadAnalysis
from app.schemas.analysis import LeadAnalysisOutput
from app.schemas.lead import (
    LeadAnalysisRequest,
    LeadAnalysisResponse,
)
from app.services.lead_service import process_lead_analysis

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("/analyze", response_model=LeadAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_lead_endpoint(
    payload: LeadAnalysisRequest,
    db: Session = Depends(get_db),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
):
    tenant_id = x_tenant_id or payload.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id must be provided in payload or X-Tenant-ID header",
        )

    get_or_create_tenant(db, tenant_id)

    lead = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant_id, Lead.external_lead_id == payload.lead_id)
        .first()
    )

    if not lead:
        lead = Lead(
            tenant_id=tenant_id,
            external_lead_id=payload.lead_id,
            customer_name=payload.customer.name if payload.customer else None,
            customer_phone=payload.customer.phone if payload.customer else None,
            source=payload.lead.source if payload.lead else "whatsapp",
            status=payload.lead.status if payload.lead else "contacted",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

    analysis_output: LeadAnalysisOutput = process_lead_analysis(payload)

    if analysis_output.do_not_contact:
        lead.do_not_contact = True
        db.commit()

    db_analysis = LeadAnalysis(
        lead_id=lead.id,
        tenant_id=tenant_id,
        lead_score=analysis_output.lead_score,
        priority=analysis_output.priority,
        intent=analysis_output.intent,
        stage=analysis_output.stage,
        summary=analysis_output.summary,
        next_best_action=analysis_output.next_best_action,
        follow_up_channel=analysis_output.follow_up_channel,
        follow_up_message=analysis_output.follow_up_message,
        do_not_contact=analysis_output.do_not_contact,
        raw_response=analysis_output.model_dump_json(),
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    return LeadAnalysisResponse(
        tenant_id=tenant_id,
        lead_id=payload.lead_id,
        analysis=analysis_output,
        analyzed_at=db_analysis.created_at,
    )


@router.get("/{lead_id}/analysis", response_model=LeadAnalysisResponse)
def get_latest_lead_analysis(
    lead_id: str,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    lead = (
        db.query(Lead)
        .filter(Lead.tenant_id == x_tenant_id, Lead.external_lead_id == lead_id)
        .first()
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found for tenant '{x_tenant_id}'",
        )

    latest_analysis = (
        db.query(LeadAnalysis)
        .filter(LeadAnalysis.lead_id == lead.id, LeadAnalysis.tenant_id == x_tenant_id)
        .order_by(LeadAnalysis.created_at.desc())
        .first()
    )

    if not latest_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for lead '{lead_id}'",
        )

    structured_analysis = LeadAnalysisOutput(
        lead_score=latest_analysis.lead_score,
        priority=latest_analysis.priority,
        intent=latest_analysis.intent,
        stage=latest_analysis.stage,
        summary=latest_analysis.summary,
        next_best_action=latest_analysis.next_best_action,
        follow_up_channel=latest_analysis.follow_up_channel,
        follow_up_message=latest_analysis.follow_up_message,
        do_not_contact=latest_analysis.do_not_contact,
    )

    return LeadAnalysisResponse(
        tenant_id=x_tenant_id,
        lead_id=lead_id,
        analysis=structured_analysis,
        analyzed_at=latest_analysis.created_at,
    )


@router.post("/{lead_id}/follow-up")
def trigger_lead_follow_up(
    lead_id: str,
    db: Session = Depends(get_db),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    lead = (
        db.query(Lead)
        .filter(Lead.tenant_id == x_tenant_id, Lead.external_lead_id == lead_id)
        .first()
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found for tenant '{x_tenant_id}'",
        )

    if lead.do_not_contact:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot dispatch follow-up: Customer has opted out (do_not_contact=True)",
        )

    latest_analysis = (
        db.query(LeadAnalysis)
        .filter(LeadAnalysis.lead_id == lead.id, LeadAnalysis.tenant_id == x_tenant_id)
        .order_by(LeadAnalysis.created_at.desc())
        .first()
    )

    if not latest_analysis or not latest_analysis.follow_up_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No actionable follow-up message generated for this lead",
        )

    return {
        "status": "dispatched",
        "tenant_id": x_tenant_id,
        "lead_id": lead_id,
        "recipient": {
            "name": lead.customer_name,
            "phone": lead.customer_phone,
        },
        "channel": latest_analysis.follow_up_channel,
        "dispatched_message": latest_analysis.follow_up_message,
        "dispatched_at": datetime.utcnow().isoformat(),
    }