"""Explicit local-only OpenCode read-only development review; never for merchant data."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.hybrid_ai import opencode_review

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True)
    ap.add_argument("--task",choices=["code_review","test_review","design_review"],required=True)
    ap.add_argument("--prompt",required=True,help="Development-only instructions; no merchant data or secrets")
    args=ap.parse_args()
    out=opencode_review(args.task,args.prompt,args.repo)
    print(out["text"])
if __name__=="__main__":main()
