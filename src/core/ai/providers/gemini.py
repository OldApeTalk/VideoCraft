"""Gemini provider (type='gemini').

Phase 1: extracted verbatim from ai_router.py; exceptions still bubble as
RuntimeError. Phase 7 will wrap google.api_core.exceptions into AIError with
the appropriate Kind (quota, rate limit, safety refusal, etc.).
"""

from core.ai.providers._json_utils import parse_json_response


def call(api_key: str, model_id: str, prompt: str) -> str:
    """Plain text completion via google-generativeai SDK."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_id)
    response = model.generate_content(prompt)
    return response.text.strip()


def call_json(api_key: str, model_id: str, prompt: str, schema: dict) -> dict:
    """Structured JSON completion via Gemini's native response_schema flag."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_id,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": schema,
        },
    )
    response = model.generate_content(prompt)
    raw = (response.text or "").strip()
    return parse_json_response(raw, provider_hint="Gemini")
