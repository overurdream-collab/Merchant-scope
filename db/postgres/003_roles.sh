#!/bin/sh
set -eu
: "${POSTGRES_USER:?}"
: "${POSTGRES_DB:?}"
: "${MS_AUTH_PASSWORD:?Set auth role password in your local env file}"
: "${MS_DATA_PASSWORD:?Set data role password in your local env file}"
psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v auth_password="$MS_AUTH_PASSWORD" \
  -v data_password="$MS_DATA_PASSWORD" <<'SQL'
CREATE ROLE ms_auth_api LOGIN PASSWORD :'auth_password';
CREATE ROLE ms_data_api LOGIN PASSWORD :'data_password';
GRANT merchant_auth TO ms_auth_api;
GRANT merchant_runtime TO ms_data_api;
SQL
