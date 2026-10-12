from django.core.management.base import BaseCommand, CommandError

from modelos.services import register_cemig_template


class Command(BaseCommand):
    help = "Cadastra ou atualiza o modelo versionado da ficha CEMIG."

    def add_arguments(self, parser):
        parser.add_argument("--reference", help="PDF de referência para armazenar no modelo")
        parser.add_argument("--template-version", default="1.0.0")

    def handle(self, *args, **options):
        path = options.get("reference")
        if path:
            from pathlib import Path

            if not Path(path).is_file():
                raise CommandError(f"Arquivo de referência não encontrado: {path}")
        template = register_cemig_template(reference_path=path, version=options["template_version"])
        self.stdout.write(self.style.SUCCESS(f"Modelo registrado: {template.code} v{template.version} ({template.page_count} páginas)"))
