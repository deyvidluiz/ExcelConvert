# ExcelConvert

Plataforma Django para transformar tabelas de PDFs e imagens em dados editáveis, com revisão manual e exportação para Excel, Word e PDF.

## Estado atual

O fluxo principal está funcional: criação de conta/login; upload múltiplo validado; extração local de PDFs digitais; Gemini opcional com JSON estruturado; cache por hash/modelo/prompt; editor de células; exportação XLSX/DOCX/PDF; dashboard, histórico, custos, exclusão e isolamento por usuário.

PDFs escaneados e imagens exigem `GEMINI_API_KEY`. O sistema pede confirmação explícita antes de chamar a IA. Sem chave ou confirmação, nenhum request pago é iniciado.

## Requisitos

- Python 3.11+ (testado com Python 3.13)
- SQLite para desenvolvimento
- PostgreSQL opcional para produção
- chave Gemini apenas para extração visual

## Instalação local — Linux

```bash
git clone https://github.com/deyvidluiz/ExcelConvert.git
cd ExcelConvert
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/` e crie uma conta.

## Configuração do Gemini

Crie uma chave no [Google AI Studio](https://aistudio.google.com/app/apikey) e edite `.env`:

```dotenv
GEMINI_API_KEY=sua-chave-aqui
GEMINI_MODEL=gemini-2.5-flash-lite
```

Nunca versione `.env`. O modelo pode ser alterado por variável, mas o padrão é `gemini-2.5-flash-lite`. O token count retornado pela API é salvo no documento. A estimativa inicial usa US$ 0,10 por milhão de tokens e o câmbio configurável em `USD_TO_BRL`; revise os preços do seu contrato antes de usar os valores para faturamento.

## Variáveis principais

| Variável | Uso |
| --- | --- |
| `SECRET_KEY` | segredo Django; obrigatório em produção |
| `DEBUG` | `True` localmente, `False` em produção |
| `ALLOWED_HOSTS` | hosts autorizados separados por vírgula |
| `DATABASE_URL` | PostgreSQL; vazio usa SQLite |
| `GEMINI_API_KEY` | habilita extração visual |
| `GEMINI_MODEL` | modelo Gemini configurável |
| `MAX_UPLOAD_SIZE_MB` | limite por arquivo |
| `MAX_DOCUMENT_PAGES` | limite de páginas |
| `MAX_MONTHLY_ESTIMATED_USD` | trava preventiva de orçamento por usuário |
| `USD_TO_BRL` | câmbio usado na exibição |
| `MEDIA_ROOT` | diretório privado dos uploads |

## Testes e checks

```bash
python manage.py check
python manage.py check --deploy
python -m pytest -q
```

Os testes mockam a chamada do Gemini; a suíte padrão não consome tokens pagos. `check --deploy` pode alertar quando `DEBUG=True`, padrão de desenvolvimento. Em produção use `DEBUG=False`, `SECRET_KEY` longo, HTTPS e `SECURE_SSL_REDIRECT=True` quando o proxy estiver preparado.

## Deploy

Para um servidor Linux com Gunicorn:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn excelconvert.wsgi:application --bind 0.0.0.0:8000
```

Use Nginx ou outro proxy TLS, mantenha `MEDIA_ROOT` privado com backup e configure `DATABASE_URL` para PostgreSQL. Em produção, substitua o armazenamento local de mídia por volume privado ou storage compatível antes de escalar horizontalmente.

## Arquitetura

- `core`: autenticação, dashboard, histórico e configurações;
- `documentos`: upload, validação, armazenamento, status e cache;
- `extracao`: schemas Pydantic, prompt, PDF local e Gemini;
- `validacao`: regras determinísticas e editor de células;
- `exportacao`: XLSX, DOCX e PDF.

## Limitações conhecidas e próximos passos

- O processamento é síncrono; grandes lotes podem evoluir para Celery/RQ com progresso persistido.
- A visualização do original abre o arquivo privado em nova aba; um viewer por página pode ser acrescentado.
- A exportação é por documento. Exportação unificada, paginação avançada e preços por modelo são evoluções futuras.
- PDFs digitais sem tabelas estruturadas podem precisar do Gemini.
- A estimativa de preço não substitui a tabela oficial do provedor.
