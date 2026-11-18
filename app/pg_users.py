"""Offline provisioning of per-user PostgreSQL accounts.
Not a public registration endpoint: requires an admin connection and explicit org ID.
"""
import re
from uuid import UUID
from .pg_identity import hash_password

ROLES={"admin","analyst","reviewer","viewer"}

def create_user(admin_dsn, org_id, email, password, role):
    import psycopg
    from psycopg.rows import dict_row
    if not admin_dsn:
        raise ValueError("Admin database connection required")
    try:
        UUID(str(org_id))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid organization UUID") from exc
    if role not in ROLES:
        raise ValueError("Role must be admin, analyst, reviewer or viewer")
    email=email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email) or len(email)>254:
        raise ValueError("A valid email address is required")
    digest=hash_password(password)
    with psycopg.connect(admin_dsn,row_factory=dict_row) as db:
        existing=db.execute("SELECT 1 FROM ms.organizations WHERE id=%s",(str(org_id),)).fetchone()
        if not existing:
            raise ValueError("Organization does not exist")
        account=db.execute("SELECT id FROM ms.user_accounts WHERE email=%s",(email,)).fetchone()
        if account:
            raise ValueError("Email already has an account; explicit membership management required")
        row=db.execute("INSERT INTO ms.user_accounts(email,password_hash) VALUES(%s,%s) RETURNING id",(email,digest)).fetchone()
        db.execute("INSERT INTO ms.memberships(org_id,user_id,role) VALUES(%s,%s,%s::ms.member_role)",
                   (str(org_id),row["id"],role))
        return {"org_id":str(org_id),"user_id":str(row["id"]),"role":role,"email":email}
