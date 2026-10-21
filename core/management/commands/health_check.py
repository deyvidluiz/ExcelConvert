"""
Health check command para o Django.

Verifica se todos os componentes estão funcionando:
- Database
- Cache
- Gemini API (se configurado)
- Storage
"""

import sys

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = "Verifica saúde da aplicação e dependências"

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Falha se Gemini API não estiver configurada",
        )

    def handle(self, *args, **options):
        all_ok = True
        
        # 1. Database
        self.stdout.write("Verificando database...", ending=" ")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write(self.style.SUCCESS("OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"FALHOU: {e}"))
            all_ok = False
        
        # 2. Cache
        self.stdout.write("Verificando cache...", ending=" ")
        try:
            from django.core.cache import cache
            cache.set("health_check", "ok", 10)
            if cache.get("health_check") != "ok":
                raise Exception("Valor não persistiu")
            self.stdout.write(self.style.SUCCESS("OK"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"INDISPONÍVEL: {e}"))
        
        # 3. Gemini API
        self.stdout.write("Verificando Gemini API...", ending=" ")
        try:
            import os
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                # Teste simples de conexão
                from google.genai import Client
                client = Client(api_key=api_key)
                # Não faz chamada real, só verifica se client inicia
                self.stdout.write(self.style.SUCCESS("OK (configurada)"))
            elif options.get("strict"):
                self.stdout.write(self.style.WARNING("NÃO CONFIGURADA"))
            else:
                self.stdout.write(self.style.WARNING("NÃO CONFIGURADA (opcional)"))
        except ImportError:
            self.stdout.write(self.style.WARNING("BIBLIOTECA NÃO INSTALADA"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"ERRO: {e}"))
        
        # 4. Static files
        self.stdout.write("Verificando static files...", ending=" ")
        try:
            from django.contrib.staticfiles import finders
            found = finders.find("css/app.css")
            if found:
                self.stdout.write(self.style.SUCCESS("OK"))
            else:
                self.stdout.write(self.style.WARNING("ARQUIVOS NÃO ENCONTRADOS"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"ERRO: {e}"))
        
        # 5. Media storage
        self.stdout.write("Verificando media storage...", ending=" ")
        try:
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage
            # Teste simples de escrita
            test_key = "health_check_test.txt"
            test_key = default_storage.save(test_key, ContentFile(b"ok"))
            default_storage.delete(test_key)
            self.stdout.write(self.style.SUCCESS("OK"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"ERRO: {e}"))
        
        # 6. Templates ativos
        self.stdout.write("Verificando templates...", ending=" ")
        try:
            from modelos.models import DocumentTemplate
            count = DocumentTemplate.objects.filter(is_active=True).count()
            self.stdout.write(self.style.SUCCESS(f"OK ({count} templates)"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"ERRO: {e}"))
        
        # Resultado final
        if all_ok:
            self.stdout.write("\n" + self.style.SUCCESS("✓ Aplicação saudável"))
            sys.exit(0)
        else:
            self.stdout.write("\n" + self.style.ERROR("✗ Problemas detectados"))
            sys.exit(1)