"""Produce a human-review packet from operator supplied JSON and optional local Ollama."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.pilot_runner import prepare_review_packet

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input",help="JSON file with merchant, evidence, mode; DO NOT use directory manifest as posts")
    parser.add_argument("--out",required=True,help="local destination for draft review packet")
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    packet=prepare_review_packet(data["merchant"],data["evidence"],data.get("mode","content"))
    path=Path(args.out)
    if path.exists():parser.error("Output already exists; never overwrite reviews silently")
    path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Draft written for independent review: "+str(path))
if __name__=="__main__":main()
