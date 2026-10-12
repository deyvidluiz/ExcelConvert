import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from exportacao.services import build_xlsx
from extracao.gemini_service import GeminiExtractor
from modelos.controlled_test import prepare_page_preflight
from modelos.models import DocumentTemplate


class Command(BaseCommand):
    help = "Prepara uma página CEMIG para revisão e só chama Gemini com autorização explícita."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True, help="PDF de referência ou documento a testar")
        parser.add_argument("--page", type=int, default=1, help="Página 1-based; padrão: 1")
        parser.add_argument("--template-code", default="cemig-tc-comissionamento")
        parser.add_argument("--output-dir", help="Diretório dos artefatos; padrão: media/preflight/<modelo>/page-N")
        parser.add_argument(
            "--authorize-real-call",
            action="store_true",
            help="Autoriza uma única chamada real, sem retry automático, após o preflight.",
        )

    def handle(self, *args, **options):
        template = DocumentTemplate.objects.filter(code=options["template_code"], is_active=True).first()
        if not template:
            raise CommandError("Modelo de ficha não encontrado; execute register_cemig_template antes.")
        pdf_path = Path(options["pdf"])
        output_dir = Path(options["output_dir"] or settings.MEDIA_ROOT / "preflight" / template.code / f"page-{options['page']}")
        try:
            manifest, processed_data = prepare_page_preflight(
                pdf_path=pdf_path,
                template=template,
                page_number=options["page"],
                output_dir=output_dir,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Preflight criado em: {output_dir}"))
        self.stdout.write(f"Qualidade: {manifest['preprocessing']['quality_score']}")
        self.stdout.write(
            f"Campos da página: {manifest['fields_total']}; "
            f"regiões calibradas: {manifest['fields_calibrated']}; "
            f"pendentes: {len(manifest['fields_pending_calibration'])}"
        )
        estimate = manifest["estimated_usage"]
        self.stdout.write(
            f"Estimativa heurística: ~{estimate['total_tokens']} tokens "
            f"(US$ {estimate['estimated_cost_usd']:.8f}; R$ {estimate['estimated_cost_brl']:.6f})."
        )
        self.stdout.write("Nenhuma chamada Gemini foi feita durante o preflight.")
        if not options["authorize_real_call"]:
            self.stdout.write("Para autorizar uma chamada única, repita o comando com --authorize-real-call após revisar pagina-regioes.png.")
            return

        self.stdout.write(self.style.WARNING("Autorização explícita recebida: iniciando uma única chamada Gemini, sem retry automático."))
        extractor = GeminiExtractor()
        payload, _ = extractor.extract_template(
            data=processed_data,
            mime_type="image/png",
            document_name=f"{pdf_path.name} — página {options['page']}",
            template=template,
        )
        metrics = extractor.last_metrics
        payload_path = output_dir / "extracao-real.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        workbook_path = output_dir / "extracao-real.xlsx"
        workbook_path.write_bytes(build_xlsx(payload).read())
        manifest["real_api_call"] = True
        manifest["real_usage"] = metrics
        (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Extração real salva em: {payload_path}"))
        self.stdout.write(self.style.SUCCESS(f"Excel editável salvo em: {workbook_path}"))
        self.stdout.write(f"Tokens reais: entrada={metrics['input_tokens']}, saída={metrics['output_tokens']}, total={metrics['total_tokens']}.")
