# Run MerchantScope local pilot on Windows, Linux or macOS

This is **NOT** a production SaaS. It has shared analyst/reviewer token roles rather than real multi-user identities, and uses SQLite. Do not expose it to the Internet.

## Local Docker quickstart

1. Install Docker Desktop / Docker Engine.
2. In your shell set `MERCHANTSCOPE_ADMIN_TOKEN` to a long random secret and `MERCHANTSCOPE_REVIEWER_TOKEN` to a different random secret (do not commit either).
3. Run `docker compose up --build -d` in the repository directory.
4. Visit http://127.0.0.1:8765. Enter analyst token for data entry and reviewer token for approvals.
5. Stop with `docker compose down`. The `merchant_data` volume persists. **Do not use `down -v` unless you intentionally want to delete pilot data.**

The local port binds only to `127.0.0.1`, not all network interfaces. `MERCHANTSCOPE_LOCAL_ONLY=0` applies inside Docker because of bridge networking, so **never modify the host port bind to `0.0.0.0`**. Do not put an unauthenticated reverse proxy in front.

## Local Ollama
The pilot supports an optional Ollama model endpoint at 127.0.0.1:11434 from inside the running application. Because a container has its own loopback, Docker mode does not directly reach host Ollama. Leave model unset in Docker unless you deliberately configure a reviewed internal-network gateway. Never place an LLM endpoint on the public Internet.

## Pilot backups
Stop containers before copying the SQLite database, or use SQLite's online backup API. Restore only after verifying backup integrity. A production migration to PostgreSQL, tenancy-aware API, account identity, monitoring and recovery tests is required before a public launch.

## Acceptance conditions
Run `python -m pytest -q`, ensure GitHub Actions passes, then run browser smoke. All demo entries must be synthetic; no contact outreach is automated.
