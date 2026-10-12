from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from documentos.models import Document


class Command(BaseCommand):
    help = "Exclui documentos e arquivos privados mais antigos que o prazo de retenção."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.DOCUMENT_RETENTION_DAYS)

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days deve ser maior que zero.")
        cutoff = timezone.now() - timedelta(days=days)
        documents = Document.objects.filter(created_at__lt=cutoff).only("pk")
        total = documents.count()
        for document in documents.iterator():
            document.delete()
        self.stdout.write(self.style.SUCCESS(f"{total} documento(s) excluído(s) por retenção."))
