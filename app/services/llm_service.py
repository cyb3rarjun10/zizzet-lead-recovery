import abc
import json
import httpx
from app.core.config import settings
from app.schemas.analysis import LeadAnalysisOutput


class BaseLLMService(abc.ABC):
    @abc.abstractmethod
    def analyze_lead(self, prompt: str) -> LeadAnalysisOutput:
        pass


class GeminiService(BaseLLMService):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.api_key}"

    def analyze_lead(self, prompt: str) -> LeadAnalysisOutput:
        system_instruction = (
            "You are an expert CRM revenue intelligence and lead recovery AI. "
            "Analyze the lead context, status, and full conversation history. "
            "Evaluate intent, assign a score from 0 to 100, categorize priority, "
            "and craft a concise, professional follow-up message tailored to the conversation. "
            "You MUST output valid JSON matching this schema: "
            "{"
            "'lead_score': int, "
            "'priority': 'high'|'medium'|'low', "
            "'intent': str, "
            "'stage': str, "
            "'summary': str, "
            "'next_best_action': str, "
            "'follow_up_channel': 'whatsapp'|'email'|'sms'|'call', "
            "'follow_up_message': str or null, "
            "'do_not_contact': bool"
            "}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(self.url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Gemini API returned error {resp.status_code}: {resp.text}"
                )
            data = resp.json()

        raw_json_str = data["candidates"][0]["content"]["parts"][0]["text"]
        return LeadAnalysisOutput.model_validate_json(raw_json_str)


def get_llm_service() -> BaseLLMService:
    if settings.LLM_PROVIDER == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in environment variables.")
        return GeminiService(api_key=settings.GEMINI_API_KEY)
    raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")