"""Write reproducible fail-closed release report from manually verified evidence."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.release_gates import evaluate_release

def main():
    p=argparse.ArgumentParser()
    p.add_argument("manifest",help="JSON containing exact target_sha and evidence for each gate")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=evaluate_release(json.loads(Path(a.manifest).read_text(encoding="utf-8")))
    out=Path(a.out)
    if out.exists():p.error("Refusing to overwrite release evidence")
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(result["release_decision"]+" | blocked="+str(result["blocked_count"]))
    return 0 if result["release_decision"]=="REQUIRES_FINAL_OWNER_SIGNOFF" else 2
if __name__=="__main__":raise SystemExit(main())
