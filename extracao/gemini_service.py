import json
import os

from django.conf import settings

from .prompts import EXTRACTION_PROMPT
from .schemas import DocumentExtraction, payload_from_model


class GeminiExtractionError(RuntimeError):
    pass


class GeminiExtractor:
    def __init__(self, model=None):
        self.model = model or settings.GEMINI_MODEL

    def extract(self, *, data: bytes, mime_type: str, document_name: str) -> tuple[dict, int]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiExtractionError("GEMINI_API_KEY não configurada; a operação paga não foi iniciada.")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=[types.Part.from_bytes(data=data, mime_type=mime_type), EXTRACTION_PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DocumentExtraction,
                    temperature=0,
                ),
            )
        except Exception as exc:
            raise GeminiExtractionError("Não foi possível concluir a extração com o Gemini.") from exc
        try:
            parsed = getattr(response, "parsed", None)
            extraction = parsed if isinstance(parsed, DocumentExtraction) else DocumentExtraction.model_validate(
                parsed if parsed is not None else json.loads(response.text)
            )
        except Exception as exc:
            raise GeminiExtractionError("O Gemini retornou uma estrutura inválida; nada foi exportado.") from exc
        usage = getattr(response, "usage_metadata", None)
        token_count = int(getattr(usage, "total_token_count", 0) or 0)
        payload = payload_from_model(extraction)
        payload["document_name"] = payload.get("document_name") or document_name
        return payload, token_count
