#!/bin/sh
set -eu
: "${POSTGRES_USER:?}"
: "${POSTGRES_DB:?}"
: "${MS_AUTH_PASSWORD:?Set auth role password in your local env file}"
: "${MS_DATA_PASSWORD:?Set data role password in your local env file}"
: "${MS_POSTGRES_SUPERUSER_PASSWORD:?Missing database administrator password}"
for secret in "$MS_POSTGRES_SUPERUSER_PASSWORD" "$MS_AUTH_PASSWORD" "$MS_DATA_PASSWORD"; do
  if [ ${#secret} -lt 32 ]; then
    echo "Refusing to initialize with a credential shorter than 32 characters" >&2
    exit 1
  fi
  case "$secret" in
    *REPLACE*|*CHANGE_ME*|*EXAMPLE*) echo "Refusing placeholder credentials" >&2; exit 1 ;;
  esac
done
if [ "$MS_POSTGRES_SUPERUSER_PASSWORD" = "$MS_AUTH_PASSWORD" ] ||
   [ "$MS_POSTGRES_SUPERUSER_PASSWORD" = "$MS_DATA_PASSWORD" ] ||
   [ "$MS_AUTH_PASSWORD" = "$MS_DATA_PASSWORD" ]; then
  echo "All three database credentials must be different" >&2
  exit 1
fi
psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v auth_password="$MS_AUTH_PASSWORD" \
  -v data_password="$MS_DATA_PASSWORD" <<'SQL'
CREATE ROLE ms_auth_api LOGIN PASSWORD :'auth_password';
CREATE ROLE ms_data_api LOGIN PASSWORD :'data_password';
GRANT merchant_auth TO ms_auth_api;
GRANT merchant_runtime TO ms_data_api;
SQL
