"""Inspect hybrid configuration without sending a request unless --live is supplied."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.hybrid_ai import connection_status, deepseek_json

def main():
    ap=argparse.ArgumentParser(description="MerchantScope DeepSeek + OpenCode readiness")
    ap.add_argument("--live",action="store_true",help="Makes one billable DeepSeek API request")
    args=ap.parse_args()
    status=connection_status()
    print(json.dumps(status,ensure_ascii=False,indent=2))
    if not status["deepseek_configured"]:
        print("DeepSeek not configured: no API request made.")
        return 2 if args.live else 0
    if args.live:
        result=deepseek_json("Return only JSON with the single string field status equal to ok.")
        if result.get("status")!="ok":
            print("Connection made but response did not pass smoke contract.")
            return 2
        print("DeepSeek live contract: OK; API billing may apply.")
    return 0
if __name__=="__main__":raise SystemExit(main())
