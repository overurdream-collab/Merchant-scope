# MerchantScope secure local PostgreSQL stack

This Docker Compose stack is **local development and acceptance testing only**, not a production deployment. It uses PostgreSQL 16, per-user authenticated sessions, organization RLS and a one-time privileged bootstrap. It never exposes the database on the host network and binds the web UI only to `127.0.0.1:8788`.

## Windows 11 / PowerShell

1. Clone the reviewed branch. Install Docker Desktop.
2. In the repository root, generate *three different random URL-safe secrets* once:

```powershell
python -c "from pathlib import Path; import secrets; keys=['MS_POSTGRES_SUPERUSER_PASSWORD','MS_AUTH_PASSWORD','MS_DATA_PASSWORD']; Path('.env.secure').write_text(''.join(k+'='+secrets.token_urlsafe(36)+'\\n' for k in keys))"
```

3. Start database and authenticated app:

```powershell
docker compose --env-file .env.secure -f compose.secure.yml up --build -d --wait
```

4. Offline, interactive, one-time admin/account bootstrap:

```powershell
docker compose --env-file .env.secure -f compose.secure.yml --profile setup run --rm bootstrap
```

Enter organization name, email, and a strong password at the prompts. Keep the printed **Organization ID** locally; never send passwords or database credentials in chat.

5. Open `http://127.0.0.1:8788`. Enter email, password and Organization ID. Data is scoped to the signed-in organization. A second user with `reviewer` role must be provisioned through an audited, privileged administrator operation before independent approval can be used. Do not use the creator's account to self-approve.

6. Stop with `docker compose --env-file .env.secure -f compose.secure.yml down`. Preserve the PostgreSQL data volume. Do **NOT** use `down -v` unless intentionally deleting all data.

## Architecture and threat boundaries

- `db` runs PostgreSQL with restricted `merchant_auth` and `merchant_runtime` role membership; no host-exposed database port.
- `web` uses separate auth/data DB credentials and a read-only root filesystem, no Linux capabilities, a loopback-only host port and no privileged admin DB credentials.
- `bootstrap` is an optional `setup` profile; it is not running in normal operation and is the only service receiving the privileged `MERCHANTSCOPE_ADMIN_DSN`.
- `MERCHANTSCOPE_LOCAL_CONTAINER_MODE=1` allows HTTP inside the local Docker network. **Never use this mode on a public deployment, and never change the host port from 127.0.0.1.**
- Credentials are supplied through the ignored `.env.secure`, and Docker environment variables can be inspected by local administrators. For production use managed secrets, HTTPS, network isolation, MFA and complete security assessment.
- The PostgreSQL migrations run only when a **new empty Docker volume** is initialized. Do not expect schema upgrades when starting an existing volume. Create versioned migrations with backup and rehearsal for upgrades.

## Not yet production ready

Live authorization API connectors, tested model inference, monitored ingestion workers, invitation/recovery/MFA, rate limits, deployment and independent penetration testing remain required. The old SQLite pilot's OSM/AI features are separate from the new secured PostgreSQL API until integrated and tested.

## CI acceptance

`.github/workflows/secure-compose.yml` boots this stack using synthetic disposable credentials, verifies the sign-in screen and refusal of unauthenticated API access, bootstraps a disposable user, and checks authenticated API calls. This is an automated smoke test, not authorization for open internet release.
