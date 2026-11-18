"""Offline PostgreSQL bootstrap. Never call from a network-exposed endpoint."""
import os
from getpass import getpass
from app.pg_identity import bootstrap_admin

def main():
    dsn=os.environ.get("MERCHANTSCOPE_ADMIN_DSN","")
    if not dsn:
        raise SystemExit("MERCHANTSCOPE_ADMIN_DSN is required for offline bootstrap")
    name=input("Organization name: ").strip()
    email=input("Admin email: ").strip().lower()
    password=getpass("New admin password (12+ characters): ")
    confirm=getpass("Confirm password: ")
    if password!=confirm:raise SystemExit("Passwords do not match")
    result=bootstrap_admin(dsn,name,email,password)
    print("Organization ID:",result["org_id"])
    print("Admin account ID:",result["user_id"])
    print("No password or database secret was printed.")
if __name__=="__main__":main()
