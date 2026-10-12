from django.db import transaction

from .models import DocumentTemplate, EvaluationField, EvaluationRun, ReferenceValue


@transaction.atomic
def evaluate_payload(*, template: DocumentTemplate, payload: dict, document=None):
    """Compara apenas com referências humanas cadastradas; nunca trata saída da IA como verdade."""
    references = {item.field.field_id: item for item in ReferenceValue.objects.filter(template=template).select_related("field")}
    predicted = {item.get("field_id"): item for item in payload.get("template_fields", [])}
    run = EvaluationRun.objects.create(
        template=template,
        document=document,
        fields_identified=sum(1 for item in predicted.values() if item.get("value") not in (None, "")),
        input_tokens=getattr(document, "input_token_count", 0) if document else 0,
        output_tokens=getattr(document, "output_token_count", 0) if document else 0,
        estimated_cost_usd=getattr(document, "estimated_cost_usd", 0) if document else 0,
    )
    correct = numeric_errors = unreadable = positioning = 0
    for field_id, reference in references.items():
        item = predicted.get(field_id, {})
        predicted_value = item.get("value")
        is_unreadable = bool(item.get("ambiguous"))
        is_correct = predicted_value == reference.value
        is_numeric_error = reference.field.expected_type in {"number", "decimal"} and not is_correct and not is_unreadable
        is_positioning_error = item.get("page_number") not in (None, reference.field.page_number)
        correct += int(is_correct)
        numeric_errors += int(is_numeric_error)
        unreadable += int(is_unreadable)
        positioning += int(is_positioning_error)
        EvaluationField.objects.create(
            run=run,
            field=reference.field,
            page_number=item.get("page_number") or reference.page_number,
            predicted_value=predicted_value,
            reference_value=reference.value,
            is_correct=is_correct,
            is_unreadable=is_unreadable,
            numeric_error=is_numeric_error,
            positioning_error=is_positioning_error,
        )
    run.fields_correct = correct
    run.numeric_errors = numeric_errors
    run.unreadable_fields = unreadable
    run.positioning_errors = positioning
    run.save(update_fields=["fields_correct", "numeric_errors", "unreadable_fields", "positioning_errors"])
    return run
