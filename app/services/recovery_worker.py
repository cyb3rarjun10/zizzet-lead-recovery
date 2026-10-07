import json
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import Lead, LeadAnalysis, WebhookEvent
from app.schemas.analysis import LeadAnalysisOutput
from app.schemas.lead import LeadAnalysisRequest, WebhookLeadEvent
from app.services.lead_service import process_lead_analysis


def process_webhook_event_task(event_id: str, tenant_id: str):
    db = SessionLocal()
    try:
        event = (
            db.query(WebhookEvent)
            .filter(
                WebhookEvent.tenant_id == tenant_id,
                WebhookEvent.idempotency_key == event_id,
            )
            .first()
        )
        if not event or event.status == "completed":
            return

        event.status = "processing"
        db.commit()

        payload_dict = json.loads(event.payload)
        webhook_data = WebhookLeadEvent.model_validate(payload_dict)

        lead = (
            db.query(Lead)
            .filter(
                Lead.tenant_id == tenant_id,
                Lead.external_lead_id == webhook_data.lead_id,
            )
            .first()
        )

        if not lead:
            lead = Lead(
                tenant_id=tenant_id,
                external_lead_id=webhook_data.lead_id,
                customer_name=webhook_data.customer.name if webhook_data.customer else None,
                customer_phone=webhook_data.customer.phone if webhook_data.customer else None,
                source=webhook_data.lead.source if webhook_data.lead else "whatsapp",
                status=webhook_data.lead.status if webhook_data.lead else "contacted",
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)

        analysis_req = LeadAnalysisRequest(
            tenant_id=tenant_id,
            lead_id=webhook_data.lead_id,
            customer=webhook_data.customer,
            lead=webhook_data.lead,
            conversation=webhook_data.conversation,
        )

        analysis_output: LeadAnalysisOutput = process_lead_analysis(analysis_req)

        if analysis_output.do_not_contact:
            lead.do_not_contact = True

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

        event.status = "completed"
        event.processed_at = datetime.utcnow()
        db.commit()

    except Exception as exc:
        db.rollback()
        event = (
            db.query(WebhookEvent)
            .filter(
                WebhookEvent.tenant_id == tenant_id,
                WebhookEvent.idempotency_key == event_id,
            )
            .first()
        )
        if event:
            event.status = "failed"
            event.error_message = str(exc)
            event.processed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()