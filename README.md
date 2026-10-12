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

Para consultar a disponibilidade do modelo sem gerar conteúdo:

```bash
python manage.py check_gemini_model
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

## Modelos de fichas e Excel

Registre a ficha CEMIG usando o PDF de referência local:

```bash
python manage.py register_cemig_template --reference TCs_Curvelo_2.pdf --template-version 1.0.0
```

O comando cria uma versão com 9 páginas, catálogo de `field_id`s estáveis e o PDF original armazenado como referência privada. As regiões normalizadas ficam com status `pending` até uma calibração manual; isso evita inventar coordenadas a partir de um scan não legível automaticamente.

Para cadastrar outra ficha, crie um comando/serviço equivalente em `modelos/catalog.py` com novos `field_id`s, seções, páginas, tipo esperado e regras. Registre cada alteração como nova versão (`1.1.0`, por exemplo), sem alterar os campos da versão anterior. O admin permite revisar regiões, obrigatoriedade e mapeamentos.

Para importar um Excel de destino:

```bash
python manage.py import_excel_template \
  --template-code cemig-tc-comissionamento \
  --file modelo_cliente.xlsx \
  --name "Planilha CEMIG" \
  --template-version 1.0.0 \
  --mapping mapeamento.json
```

`mapeamento.json` usa objetos no formato `{"field_id":"numero_serie","sheet_name":"Dados","cell_or_range":"B4"}`. O preenchimento mantém estilos, células mescladas, larguras e fórmulas não mapeadas.

Referências humanas podem ser cadastradas no admin em `ReferenceValue` e avaliadas por página/campo com `evaluate_document`. A saída do Gemini nunca é usada como verdade absoluta.

## Limitações conhecidas e próximos passos

- O processamento é síncrono; grandes lotes podem evoluir para Celery/RQ com progresso persistido.
- A visualização do original abre o arquivo privado em nova aba; um viewer por página pode ser acrescentado.
- A exportação é por documento. Exportação unificada, paginação avançada e preços por modelo são evoluções futuras.
- PDFs digitais sem tabelas estruturadas podem precisar do Gemini.
- A estimativa de preço não substitui a tabela oficial do provedor.
