"""Offline CLI: add a named user to an existing MerchantScope organization."""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.pg_users import create_user

def main():
    parser=argparse.ArgumentParser(description="Provision MerchantScope PostgreSQL user (admin-only CLI)")
    parser.add_argument("--org",required=True,help="Organization UUID from bootstrap")
    parser.add_argument("--email",required=True,help="User email")
    parser.add_argument("--role",required=True,choices=["admin","analyst","reviewer","viewer"])
    args=parser.parse_args()
    dsn=os.getenv("MERCHANTSCOPE_ADMIN_DSN")
    if not dsn:
        raise SystemExit("MERCHANTSCOPE_ADMIN_DSN is required for this offline action")
    password=getpass.getpass("New user password (12+ chars): ")
    result=create_user(dsn,args.org,args.email,password,args.role)
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":main()
