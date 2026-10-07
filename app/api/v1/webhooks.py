import json
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_or_create_tenant
from app.db.database import get_db
from app.db.models import WebhookEvent
from app.schemas.lead import WebhookLeadEvent
from app.services.recovery_worker import process_webhook_event_task

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/leads", status_code=status.HTTP_202_ACCEPTED)
def receive_lead_webhook(
    payload: WebhookLeadEvent,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    get_or_create_tenant(db, payload.tenant_id)

    existing_event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.tenant_id == payload.tenant_id,
            WebhookEvent.idempotency_key == payload.event_id,
        )
        .first()
    )

    if existing_event:
        return {
            "status": "duplicate_ignored",
            "message": "Webhook event already received and processed or in progress.",
            "event_id": payload.event_id,
            "tenant_id": payload.tenant_id,
            "current_status": existing_event.status,
            "created_at": existing_event.created_at,
        }

    new_event = WebhookEvent(
        tenant_id=payload.tenant_id,
        idempotency_key=payload.event_id,
        status="pending",
        payload=payload.model_dump_json(),
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    background_tasks.add_task(
        process_webhook_event_task,
        event_id=payload.event_id,
        tenant_id=payload.tenant_id,
    )

    return {
        "status": "accepted",
        "message": "Webhook accepted for background analysis.",
        "event_id": payload.event_id,
        "tenant_id": payload.tenant_id,
        "lead_id": payload.lead_id,
    }


@router.get("/events/{event_id}")
def get_webhook_event_status(
    event_id: str,
    tenant_id: str,
    db: Session = Depends(get_db),
):
    event = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.tenant_id == tenant_id,
            WebhookEvent.idempotency_key == event_id,
        )
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' not found for tenant '{tenant_id}'",
        )

    return {
        "event_id": event.idempotency_key,
        "tenant_id": event.tenant_id,
        "status": event.status,
        "error_message": event.error_message,
        "created_at": event.created_at,
        "processed_at": event.processed_at,
    }