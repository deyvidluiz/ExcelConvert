import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from modelos.models import DocumentTemplate, ExcelFieldMapping, ExcelTemplate, TemplateField


class Command(BaseCommand):
    help = "Cadastra um arquivo XLSX como modelo de destino e opcionalmente seus mapeamentos."

    def add_arguments(self, parser):
        parser.add_argument("--template-code", required=True)
        parser.add_argument("--file", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--template-version", default="1.0.0")
        parser.add_argument("--mapping", help="JSON com [{field_id, sheet_name, cell_or_range}]")

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError("Arquivo XLSX não encontrado.")
        template = DocumentTemplate.objects.filter(code=options["template_code"], is_active=True).first()
        if not template:
            raise CommandError("Modelo de ficha não encontrado; registre-o antes.")
        workbook = ExcelTemplate.objects.filter(
            document_template=template,
            name=options["name"],
            version=options["template_version"],
        ).first()
        if workbook is None:
            with path.open("rb") as workbook_file:
                workbook = ExcelTemplate.objects.create(
                    document_template=template,
                    name=options["name"],
                    version=options["template_version"],
                    workbook=File(workbook_file, name=path.name),
                )
        if options.get("mapping"):
            for item in json.loads(Path(options["mapping"]).read_text(encoding="utf-8")):
                field = TemplateField.objects.get(template=template, field_id=item["field_id"])
                ExcelFieldMapping.objects.update_or_create(
                    excel_template=workbook,
                    field=field,
                    defaults={
                        "sheet_name": item["sheet_name"],
                        "cell_or_range": item["cell_or_range"],
                        "expected_type": item.get("expected_type", field.expected_type),
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"Modelo Excel registrado: {workbook}"))
