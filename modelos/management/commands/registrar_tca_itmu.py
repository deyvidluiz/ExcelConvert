import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from modelos import tca_itmu
from modelos import tca_itmu_catalog as catalog


class Command(BaseCommand):
    help = (
        "Cadastra o modelo CEMIG — TCA ITMU a partir do pacote de referência, "
        "gerando a cópia limpa do Excel e mapeando só os campos já confirmados."
    )

    def add_arguments(self, parser):
        parser.add_argument("--directory", required=True, help="Pasta do pacote com modelo_tca.xlsx")
        parser.add_argument("--template-version", default="1.0.0")
        parser.add_argument("--activate", action="store_true", help="Ativa o modelo e a cópia Excel no cadastro")
        parser.add_argument("--dry-run", action="store_true", help="Só confere o pacote e relata, sem gravar nada")
        parser.add_argument("--write-review", help="Grava a revisão das candidatas em um JSON")
        parser.add_argument("--save-clean-copy", help="Grava a cópia limpa do Excel em um arquivo para inspeção")

    def handle(self, *args, **options):
        directory = options["directory"]
        try:
            if options["dry_run"]:
                report = tca_itmu.audit(directory)
            else:
                report = tca_itmu.register_tca_itmu(
                    package_dir=directory,
                    version=options["template_version"],
                    activate=options["activate"],
                )
            if options.get("write_review"):
                path = Path(options["write_review"])
                path.write_text(
                    json.dumps(tca_itmu.reviewed_candidates(directory), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                self.stdout.write("Revisão das candidatas: {}".format(path))
            if options.get("save_clean_copy"):
                path = Path(options["save_clean_copy"])
                workbook, _ = tca_itmu.clean_copy(directory)
                path.write_bytes(workbook)
                self.stdout.write("Cópia limpa: {}".format(path))
        except tca_itmu.PackageError as exc:
            raise CommandError(str(exc)) from exc

        self._report(report, dry_run=options["dry_run"])

    def _report(self, report, *, dry_run):
        write = self.stdout.write
        if report["problems"]:
            write(self.style.ERROR("Pendências no catálogo:"))
            for problem in report["problems"]:
                write("  - {}".format(problem))
        write(
            "Planilha {}: {} fórmulas, {} mesclagens, área de impressão {}.".format(
                report["sheet"], report["formulas"], report["merges"], report["print_area"]
            )
        )
        write(
            "Candidatas do pacote: {} | campos confirmados: {} | em confirmação: {} | descartadas: {}.".format(
                report["candidates"],
                report["candidates_confirmed"],
                report["candidates_pending"],
                report["candidates_discarded"],
            )
        )
        write(
            "Textos fixos preservados: {} células. Entradas sem campo: {}.".format(
                report["preserved"], len(report["unmapped_inputs"])
            )
        )
        if not dry_run:
            write(
                "Cadastrado: {} (ativo: {}); Excel: {} (ativo: {}); {} células esvaziadas na cópia limpa.".format(
                    report["template"],
                    report["template"].is_active,
                    report["excel_template"],
                    report["excel_template"].is_active,
                    len(report["cleared_cells"]),
                )
            )
        write(self.style.WARNING("Precisam de confirmação humana antes de virar mapeamento:"))
        for item in catalog.PENDING:
            write("  - {} ({}): {}".format(item["field_id"], item["cell"], item["doubt"]))
        for block in catalog.PENDING_BLOCKS:
            write("  - bloco {} ({}): {}".format(block["name"], ", ".join(block["ranges"]), block["doubt"]))
        if not dry_run and not report["template"].is_active:
            write(
                self.style.SUCCESS(
                    "Modelo inativo: revise os campos no admin e ative DocumentTemplate e ExcelTemplate quando aprovar."
                )
            )
