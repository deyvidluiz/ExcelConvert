import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from documentos.models import Document, ExtractionCache
from .services import validate_payload


def _load_payload(document):
    if document.extraction_payload:
        return document.extraction_payload
    cache = ExtractionCache.objects.filter(sha256=document.sha256).order_by("-created_at").first()
    if cache:
        return cache.payload
    return {"document_name": document.original_name, "pages": [], "alerts": []}


@login_required
@require_http_methods(["GET", "POST"])
def editor(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if document.status != Document.Status.READY:
        return redirect("processamento", pk=document.pk)
    payload = _load_payload(document)
    if request.method == "POST":
        try:
            candidate = json.loads(request.POST.get("payload", "{}"))
            candidate["alerts"] = list(dict.fromkeys(candidate.get("alerts", []) + validate_payload(candidate)))
            document.extraction_payload = candidate
            document.save(update_fields=["extraction_payload", "updated_at"])
            payload = candidate
            messages.success(request, "Correções salvas sem nova chamada à IA.")
        except (json.JSONDecodeError, TypeError, AttributeError):
            messages.error(request, "Não foi possível salvar as alterações. Verifique a estrutura da tabela.")
    return render(request, "validacao/editor.html", {"document": document, "payload": payload, "payload_json": json.dumps(payload, ensure_ascii=False)})
