#!/usr/bin/env sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py register_cemig_template --template-version "${CEMIG_TEMPLATE_VERSION:-1.0.0}"
