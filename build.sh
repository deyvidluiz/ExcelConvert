#!/usr/bin/env sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput
CEMIG_VERSION="${CEMIG_TEMPLATE_VERSION:-1.0.0}"
python manage.py register_cemig_template --template-version "$CEMIG_VERSION"
if [ -n "${CEMIG_EXCEL_TEMPLATE_PATH:-}" ] && [ -f "$CEMIG_EXCEL_TEMPLATE_PATH" ]; then
  python manage.py import_excel_template \
    --template-code cemig-tc-comissionamento \
    --file "$CEMIG_EXCEL_TEMPLATE_PATH" \
    --name "${CEMIG_EXCEL_TEMPLATE_NAME:-TCA VÃO 217F - ITMU}" \
    --template-version "${CEMIG_EXCEL_TEMPLATE_VERSION:-$CEMIG_VERSION}" \
    --mapping modelos/data/cemig_excel_mapping.json
fi
