"""Print an offline quality-gate result from independently human-labeled JSONL."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.evaluation import evaluate,load_jsonl,seal_report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("reviews_jsonl",help="reviewer-labelled cases, never raw customer secrets")
    parser.add_argument("--minimum-cases",type=int,default=30)
    parser.add_argument("--out",help="optional output path")
    args=parser.parse_args()
    if args.minimum_cases<30:parser.error("Minimum sample may not be below 30")
    result=seal_report(evaluate(load_jsonl(args.reviews_jsonl),args.minimum_cases))
    serialized=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:Path(args.out).write_text(serialized+"\n",encoding="utf-8")
    print(serialized)
    return 0 if result["report"]["acceptance_pass"] else 2
if __name__=="__main__":raise SystemExit(main())
