import uuid

from django.core.management.base import BaseCommand, CommandError

from documentos.models import Document


class Command(BaseCommand):
    help = "Redefine as tentativas de um documento específico após corrigir a configuração."

    def add_arguments(self, parser):
        parser.add_argument("document_id", help="UUID do documento a redefinir.")
        parser.add_argument(
            "--keep-status",
            action="store_true",
            help="Mantém o status atual em vez de devolver o documento para 'uploaded'.",
        )

    def handle(self, *args, **options):
        document_id = options["document_id"]
        try:
            document_id = uuid.UUID(str(document_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise CommandError(f"'{options['document_id']}' não é um UUID válido.") from exc
        document = Document.objects.filter(pk=document_id).first()
        if document is None:
            raise CommandError(f"Documento {document_id} não encontrado.")
        if document.status == Document.Status.PROCESSING:
            raise CommandError(
                f"Documento {document_id} está em processamento; aguarde a conclusão antes de redefinir."
            )

        previous_attempts = document.retry_count
        document.retry_count = 0
        document.error_message = ""
        update_fields = ["retry_count", "error_message", "updated_at"]
        if not options["keep_status"] and document.status == Document.Status.FAILED:
            document.status = Document.Status.UPLOADED
            update_fields.append("status")
        # save() com update_fields toca apenas este registro e apenas estes campos.
        document.save(update_fields=update_fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"Documento {document_id}: tentativas {previous_attempts} -> 0, status '{document.status}'."
            )
        )
