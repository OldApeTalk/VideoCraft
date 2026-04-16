"""OpenAI-compatible provider (type='openai_compatible').

Covers DeepSeek and the user-defined Custom provider — any endpoint that
speaks the OpenAI chat.completions protocol.

Phase 1: extracted verbatim from ai_router.py; exceptions still bubble as
RuntimeError. Phase 7 will wrap openai.APIError / openai.RateLimitError /
openai.AuthenticationError into AIError with the appropriate Kind.
"""

import json

from core.ai.providers._json_utils import parse_json_response


def call(api_key: str, base_url: str, model_id: str, prompt: str) -> str:
    """Plain text completion via OpenAI-compatible chat.completions."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def call_json(api_key: str, base_url: str, model_id: str,
              prompt: str, schema: dict) -> dict:
    """Structured JSON completion.

    OpenAI-compat endpoints accept `response_format={"type":"json_object"}`
    but do NOT accept a schema directly — we inject the schema as a system
    hint to steer the model, then validate by parsing.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    schema_hint = (
        "You must respond with a single JSON object that strictly matches "
        "this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
        "Return only the JSON object. No markdown fences. No prose. No explanations."
    )
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": schema_hint},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    raw = (response.choices[0].message.content or "").strip()
    return parse_json_response(raw, provider_hint="OpenAI-compatible")
