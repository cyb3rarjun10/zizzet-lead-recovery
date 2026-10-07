import pytest
from app.schemas.analysis import LeadAnalysisOutput
from app.services.lead_service import process_lead_analysis


class MockLLMService:
    def __init__(self, output: LeadAnalysisOutput):
        self.output = output

    def analyze_lead(self, prompt: str) -> LeadAnalysisOutput:
        return self.output


def test_case_a_high_intent_pricing(client):
    payload = {
        "tenant_id": "tenant_eval",
        "lead_id": "lead_eval_a",
        "customer": {"name": "Vikas Patel", "phone": "+919988776655"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "We have 50 employees and need CRM pricing."},
            {"role": "agent", "message": "We offer tiered enterprise pricing."},
            {"role": "customer", "message": "Can you share the cost for 50 licenses?"}
        ]
    }
    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    analysis = data["analysis"]
    assert analysis["priority"] in ["high", "medium"]
    assert analysis["lead_score"] >= 70
    assert analysis["do_not_contact"] is False
    assert analysis["follow_up_message"] is not None


def test_case_b_low_priority_generic_inquiry(client):
    mock_low = LeadAnalysisOutput(
        lead_score=35,
        priority="low",
        intent="inquiry",
        stage="discovery",
        summary="Customer asked a high-level question about product capabilities.",
        next_best_action="Send product overview deck or 1-minute video link.",
        follow_up_channel="whatsapp",
        follow_up_message="Hi! Here is a quick 1-minute overview of what we do.",
        do_not_contact=False
    )
    payload = {
        "tenant_id": "tenant_eval",
        "lead_id": "lead_eval_b",
        "customer": {"name": "Siddharth", "phone": "+919123456789"},
        "lead": {"source": "website", "status": "new"},
        "conversation": [
            {"role": "customer", "message": "What does your product do?"}
        ]
    }
    from app.schemas.lead import LeadAnalysisRequest
    req = LeadAnalysisRequest.model_validate(payload)
    result = process_lead_analysis(req, llm_override=MockLLMService(mock_low))
    assert result.priority == "low"
    assert result.lead_score <= 50
    assert result.do_not_contact is False


def test_case_c_demo_call_request(client):
    mock_demo = LeadAnalysisOutput(
            lead_score=90,
            priority="high",
            intent="demo_request",
            stage="evaluation",
            summary="Customer requested a live demo call for tomorrow.",
            next_best_action="Schedule a product demo call for tomorrow and send calendar invite.",
            follow_up_channel="whatsapp",
            follow_up_message="I'd be glad to schedule your demo call for tomorrow. What time works best for you?",
            do_not_contact=False
        )
    payload = {
        "tenant_id": "tenant_eval",
        "lead_id": "lead_eval_c",
        "customer": {"name": "Meera Nair", "phone": "+919876501234"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Can we schedule a demo call tomorrow?"}
        ]
    }
    from app.schemas.lead import LeadAnalysisRequest
    req = LeadAnalysisRequest.model_validate(payload)
    result = process_lead_analysis(req, llm_override=MockLLMService(mock_demo))
    assert "demo" in result.next_best_action.lower() or "call" in result.next_best_action.lower()
    assert result.do_not_contact is False


def test_case_d_customer_opt_out(client):
    payload = {
        "tenant_id": "tenant_eval",
        "lead_id": "lead_eval_d",
        "customer": {"name": "Rohan Das", "phone": "+919000111222"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "STOP. Don't message me again."}
        ]
    }
    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    analysis = data["analysis"]
    assert analysis["do_not_contact"] is True
    assert analysis["follow_up_message"] is None
    assert analysis["lead_score"] == 0

    follow_up_res = client.post(
        f"/api/v1/leads/lead_eval_d/follow-up",
        headers={"X-Tenant-ID": "tenant_eval"}
    )
    assert follow_up_res.status_code == 400
    assert "opted out" in follow_up_res.json()["detail"].lower()


def test_case_e_webhook_idempotency(client):
    event_payload = {
        "event_id": "evt_test_unique_idempotency_101",
        "tenant_id": "tenant_eval",
        "lead_id": "lead_webhook_test",
        "customer": {"name": "Ananya Roy", "phone": "+919555666777"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Interested in 10 user plan."}
        ]
    }

    first_call = client.post("/api/v1/webhooks/leads", json=event_payload)
    assert first_call.status_code == 202
    assert first_call.json()["status"] == "accepted"

    second_call = client.post("/api/v1/webhooks/leads", json=event_payload)
    assert second_call.status_code == 202
    assert second_call.json()["status"] == "duplicate_ignored"


def test_multi_tenant_isolation(client):
    payload = {
        "tenant_id": "tenant_alpha",
        "lead_id": "shared_lead_id",
        "customer": {"name": "Alpha Customer"},
        "lead": {"source": "whatsapp", "status": "new"},
        "conversation": [{"role": "customer", "message": "Hello from Alpha"}]
    }
    create_res = client.post("/api/v1/leads/analyze", json=payload)
    assert create_res.status_code == 200

    alpha_get = client.get("/api/v1/leads/shared_lead_id/analysis", headers={"X-Tenant-ID": "tenant_alpha"})
    assert alpha_get.status_code == 200

    beta_get = client.get("/api/v1/leads/shared_lead_id/analysis", headers={"X-Tenant-ID": "tenant_beta"})
    assert beta_get.status_code == 404