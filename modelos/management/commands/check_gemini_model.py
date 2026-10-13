from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from extracao.gemini_service import GeminiExtractionError, check_model_availability


class Command(BaseCommand):
    help = "Verifica os metadados do modelo Gemini configurado sem gerar conteúdo."

    def handle(self, *args, **options):
        try:
            info = check_model_availability(model=settings.GEMINI_MODEL)
        except GeminiExtractionError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Modelo disponível: {info.get('name')} — {info.get('display_name')}"))
        if info.get("input_token_limit"):
            self.stdout.write(f"Limite de entrada: {info['input_token_limit']} tokens")
        if info.get("output_token_limit"):
            self.stdout.write(f"Limite de saída: {info['output_token_limit']} tokens")
        self.stdout.write(f"Suporte a generateContent: {'sim' if info.get('generation_supported') else 'não'}")
        self.stdout.write("Consulta de metadados concluída; nenhuma geração foi executada.")
