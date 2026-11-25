"""Create a NOT-SENT quote draft. Human supplies explicitly priced approved service lines."""
import argparse,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.commercial import build_quote

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input",help="JSON with merchant, services, currency, terms")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    src=json.loads(Path(args.input).read_text(encoding="utf-8"))
    result=build_quote(src["merchant"],src["services"],src.get("currency","USD"),
                       src.get("valid_until"),src.get("terms"))
    out=Path(args.out)
    if out.exists():p.error("Refusing to overwrite an existing draft")
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("UNSENT quote draft saved: "+str(out))
if __name__=="__main__":main()
