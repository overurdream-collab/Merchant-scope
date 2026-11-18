"""PostgreSQL-backed per-user identity and tenant context (independent of the SQLite pilot).
Only the trusted FastAPI server may use these connection strings; never expose them to browsers.
"""
from contextlib import contextmanager
from datetime import timedelta
from hashlib import pbkdf2_hmac, sha256
import base64
import binascii
import hmac
import os
import secrets
from uuid import UUID

ITERATIONS=600_000
SESSION_HOURS=8

def hash_password(password:str)->str:
    if len(password)<12:
        raise ValueError("Password must be at least 12 characters")
    salt=secrets.token_bytes(16)
    digest=pbkdf2_hmac("sha256",password.encode("utf-8"),salt,ITERATIONS)
    return f"pbkdf2-sha256:{ITERATIONS}:{base64.urlsafe_b64encode(salt).decode()}:{base64.urlsafe_b64encode(digest).decode()}"

def verify_password(password:str,encoded:str)->bool:
    try:
        kind,iterations,salt,digest=encoded.split(":")
        if kind!="pbkdf2-sha256" or int(iterations)>1_000_000 or int(iterations)<200_000:
            return False
        expected=base64.urlsafe_b64decode(digest)
        actual=pbkdf2_hmac("sha256",password.encode("utf-8"),base64.urlsafe_b64decode(salt),int(iterations))
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError,IndexError,binascii.Error):
        return False

def token_hash(token:str)->bytes:
    return sha256(token.encode("ascii")).digest()

def _db(dsn:str,role:str):
    import psycopg
    if not dsn: raise RuntimeError("PostgreSQL connection is not configured")
    c=psycopg.connect(dsn,connect_timeout=10)
    c.execute("SET LOCAL ROLE "+role)
    return c

def bootstrap_admin(admin_dsn:str,org_name:str,email:str,password:str):
    """Offline one-time CLI operation only; requires privileged migration role."""
    import psycopg
    from psycopg.rows import dict_row
    encoded=hash_password(password)
    with psycopg.connect(admin_dsn,row_factory=dict_row) as c:
        org=c.execute("INSERT INTO ms.organizations(name) VALUES(%s) RETURNING id",(org_name,)).fetchone()["id"]
        user=c.execute("INSERT INTO ms.user_accounts(email,password_hash) VALUES(%s,%s) RETURNING id",(email.strip().lower(),encoded)).fetchone()["id"]
        c.execute("INSERT INTO ms.memberships(org_id,user_id,role) VALUES(%s,%s,'admin')",(org,user))
        return {"org_id":str(org),"user_id":str(user)}

def login(auth_dsn:str,email:str,password:str,org_id:str):
    """Opaque random bearer; only SHA256(token) is stored, not the raw credential."""
    import psycopg
    from psycopg.rows import dict_row
    try: UUID(org_id)
    except (TypeError,ValueError): return None
    email=email.strip().lower()
    with psycopg.connect(auth_dsn,row_factory=dict_row) as c:
        c.execute("SET LOCAL ROLE merchant_auth")
        row=c.execute("""
          SELECT a.id,a.password_hash FROM ms.user_accounts a
          JOIN ms.memberships m ON m.user_id=a.id
          WHERE a.email=%s AND a.disabled_at IS NULL AND m.org_id=%s
        """,(email,org_id)).fetchone()
        # Avoid a distinct fast path for nonexistent accounts.
        if row is None:
            pbkdf2_hmac("sha256",password.encode("utf-8"),b"missing-account-salt",ITERATIONS)
            return None
        if not verify_password(password,row["password_hash"]):return None
        token=secrets.token_urlsafe(48)
        c.execute("INSERT INTO ms.sessions(user_id,org_id,token_hash,expires_at) VALUES(%s,%s,%s,now()+(%s || ' hours')::interval)",
                  (row["id"],org_id,token_hash(token),SESSION_HOURS))
        return token

def resolve_session(auth_dsn:str,token:str):
    import psycopg
    from psycopg.rows import dict_row
    if not token or len(token)>256:return None
    try:digest=token_hash(token)
    except UnicodeEncodeError:return None
    with psycopg.connect(auth_dsn,row_factory=dict_row) as c:
        c.execute("SET LOCAL ROLE merchant_auth")
        row=c.execute("""
          SELECT s.id,s.user_id,s.org_id,m.role FROM ms.sessions s
          JOIN ms.user_accounts a ON a.id=s.user_id
          JOIN ms.memberships m ON m.user_id=s.user_id AND m.org_id=s.org_id
          WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>now()
            AND a.disabled_at IS NULL
        """,(digest,)).fetchone()
        return dict(row) if row else None

def revoke_session(auth_dsn:str,token:str)->bool:
    import psycopg
    if not token or len(token)>256:return False
    try:digest=token_hash(token)
    except UnicodeEncodeError:return False
    with psycopg.connect(auth_dsn) as c:
        c.execute("SET LOCAL ROLE merchant_auth")
        r=c.execute("UPDATE ms.sessions SET revoked_at=now() WHERE token_hash=%s AND revoked_at IS NULL",(digest,))
        return r.rowcount==1

@contextmanager
def tenant_transaction(data_dsn:str,identity:dict):
    """Verified identity only. Scope runtime role + tenant settings to one DB transaction."""
    import psycopg
    if not identity or not identity.get("user_id") or not identity.get("org_id"):
        raise PermissionError("Verified identity is required")
    with psycopg.connect(data_dsn) as c:
        with c.transaction():
            c.execute("SET LOCAL ROLE merchant_runtime")
            c.execute("SELECT set_config('app.user_id',%s,true)",(str(identity["user_id"]),))
            c.execute("SELECT set_config('app.org_id',%s,true)",(str(identity["org_id"]),))
            yield c
