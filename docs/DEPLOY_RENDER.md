# Deploy do ExcelConvert no Render

## Recursos

O blueprint cria:

- um Web Service Django servido por Gunicorn;
- PostgreSQL para os dados transacionais;
- disco persistente privado montado em `/var/data`;
- WhiteNoise para os arquivos estáticos;
- inicialização idempotente do modelo CEMIG com 32 campos, sem copiar PDF de cliente para o Git.

O disco contém `MEDIA_ROOT=/var/data/media`. As rotas de documentos exigem login e filtram sempre pelo usuário proprietário; o projeto não publica `MEDIA_ROOT` como URL estática. O disco deve receber backup e não é compartilhado automaticamente com múltiplas instâncias.

## Configuração

1. Crie o serviço a partir de `render.yaml`.
2. Preencha `ALLOWED_HOSTS` com o domínio Render, por exemplo `excelconvert.onrender.com`.
3. Preencha `CSRF_TRUSTED_ORIGINS` com a origem HTTPS completa, por exemplo `https://excelconvert.onrender.com`.
4. Mantenha `DEBUG=False`, `SECURE_SSL_REDIRECT=True` e aceite a `SECRET_KEY` gerada pelo Render.
5. Adicione `GEMINI_API_KEY` somente como secret do serviço, se a extração visual for habilitada. Nunca coloque essa chave em `.env.example`, no Git ou no log.
6. Confirme que `DATABASE_URL` aponta para o PostgreSQL criado e que `MEDIA_ROOT` aponta para o disco persistente.
7. Faça um deploy e verifique `/health/`, login, upload, editor, exportação e histórico.

O `build.sh` executa migrações, coleta estáticos e roda `register_cemig_template`. Isso cria o catálogo do modelo no banco sem precisar versionar o PDF de referência. Regiões de campos permanecem pendentes até a revisão humana do PDF real.

## Variáveis

| Variável | Produção |
| --- | --- |
| `DEBUG` | `False` |
| `SECRET_KEY` | segredo longo gerado pelo Render |
| `ALLOWED_HOSTS` | hosts separados por vírgula |
| `CSRF_TRUSTED_ORIGINS` | origens HTTPS completas separadas por vírgula |
| `DATABASE_URL` | URL do PostgreSQL |
| `MEDIA_ROOT` | `/var/data/media` no disco persistente |
| `GEMINI_API_KEY` | opcional; segredo do provedor |
| `GEMINI_MODEL` | padrão `gemini-3.1-flash-lite` |
| `MAX_UPLOAD_SIZE_MB` | limite por arquivo |
| `MAX_UPLOAD_FILES` | limite de arquivos por envio |
| `MAX_DOCUMENT_PAGES` | limite de páginas por arquivo |
| `MAX_MONTHLY_API_CALLS` | limite preventivo por usuário |
| `MAX_MONTHLY_ESTIMATED_USD` | trava preventiva de custo |
| `DOCUMENT_RETENTION_DAYS` | padrão de 90 dias |
| `SECURE_SSL_REDIRECT` | `True` |
| `SECURE_HSTS_SECONDS` | HSTS após confirmar HTTPS estável |

## Retenção e privacidade

A política padrão exclui documentos, derivados e previews após 90 dias. Para executar a limpeza:

```bash
python manage.py purge_documents --days 90
```

Agende esse comando em um job operacional compatível com o seu plano Render. Antes de reduzir o prazo, confirme os requisitos contratuais de retenção. A exclusão pelo histórico também remove os arquivos armazenados.

Não use o filesystem efêmero do serviço para `MEDIA_ROOT`. O banco guarda metadados e payloads; os arquivos enviados ficam no disco privado. Para escalar horizontalmente, substitua o backend por storage privado compatível com os requisitos de acesso e backup.

## Validação antes do tráfego

Execute com variáveis representativas:

```bash
DEBUG=False \
SECRET_KEY='uma-chave-local-longa-e-aleatoria' \
ALLOWED_HOSTS='localhost' \
CSRF_TRUSTED_ORIGINS='https://localhost' \
SECURE_SSL_REDIRECT=True \
python manage.py check --deploy
python manage.py migrate --plan
python -m pytest -q
```

O teste padrão não chama a Gemini. O check de disponibilidade do modelo consulta metadados, mas também requer chave e pode fazer uma chamada de rede. A geração de conteúdo real só deve ser executada após autorização explícita e orçamento aprovado.
