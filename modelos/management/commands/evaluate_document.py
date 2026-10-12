import uuid

from django.core.management.base import BaseCommand, CommandError

from documentos.models import Document
from modelos.avaliacao import evaluate_payload


class Command(BaseCommand):
    help = "Avalia um documento usando referências revisadas manualmente cadastradas no admin."

    def add_arguments(self, parser):
        parser.add_argument("--document-id", required=True)

    def handle(self, *args, **options):
        try:
            document = Document.objects.select_related("template").get(pk=uuid.UUID(options["document_id"]))
        except (ValueError, Document.DoesNotExist) as exc:
            raise CommandError("Documento não encontrado.") from exc
        if not document.template or not document.extraction_payload:
            raise CommandError("O documento precisa de modelo e payload processado.")
        run = evaluate_payload(template=document.template, payload=document.extraction_payload, document=document)
        self.stdout.write(self.style.SUCCESS(f"Avaliação {run.pk}: {run.fields_correct} corretos, {run.numeric_errors} erros numéricos, {run.unreadable_fields} ilegíveis."))
