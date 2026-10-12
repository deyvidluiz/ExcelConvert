import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from modelos.models import DocumentTemplate, TemplateField


class Command(BaseCommand):
    help = "Salva regiões normalizadas revisadas de campos de um modelo de ficha."

    def add_arguments(self, parser):
        parser.add_argument("--template-code", required=True)
        parser.add_argument("--template-version", default="1.0.0")
        parser.add_argument("--mapping", help="JSON com [{field_id, region:{x,y,width,height}}]")
        parser.add_argument("--field-id")
        parser.add_argument("--x", type=float)
        parser.add_argument("--y", type=float)
        parser.add_argument("--width", type=float)
        parser.add_argument("--height", type=float)

    def handle(self, *args, **options):
        template = DocumentTemplate.objects.filter(code=options["template_code"], version=options["template_version"]).first()
        if not template:
            raise CommandError("Modelo/version não encontrado.")
        if options.get("mapping"):
            entries = json.loads(Path(options["mapping"]).read_text(encoding="utf-8"))
        elif options.get("field_id"):
            values = [options.get(name) for name in ("x", "y", "width", "height")]
            if any(value is None for value in values):
                raise CommandError("Informe x, y, width e height para calibrar um campo.")
            entries = [{"field_id": options["field_id"], "region": dict(zip(("x", "y", "width", "height"), values))}]
        else:
            raise CommandError("Informe --mapping ou --field-id com as coordenadas.")

        for entry in entries:
            region = entry["region"]
            if set(region) != {"x", "y", "width", "height"} or any(float(region[key]) < 0 for key in region):
                raise CommandError(f"Região inválida para {entry.get('field_id')}.")
            if float(region["x"]) + float(region["width"]) > 1 or float(region["y"]) + float(region["height"]) > 1:
                raise CommandError(f"Região fora dos limites normalizados para {entry.get('field_id')}.")
            field = TemplateField.objects.get(template=template, field_id=entry["field_id"])
            field.region = {key: round(float(region[key]), 6) for key in ("x", "y", "width", "height")}
            field.save(update_fields=["region"])

        total = template.fields.count()
        calibrated = template.fields.exclude(region=None).count()
        template.calibration_status = "calibrated" if calibrated == total else "partial"
        template.save(update_fields=["calibration_status", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"{len(entries)} região(ões) salva(s); {calibrated}/{total} campos calibrados."))
