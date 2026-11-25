"""Fail-closed evidence-based production release gate.
The input must be a signed-off, manually assembled evidence manifest, not model claims.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

GATES={
    "ci_current_commit":"Python, browser and database CI all passed on exact intended release SHA",
    "security_independent_review":"Independent role, RLS and denied-action test evidence",
    "real_model_evaluation":"At least 30 verified real cases with human-reviewed model findings",
    "merchant_uat":"Consented merchant acceptance tests and signed outcomes",
    "provider_permissions":"Permitted access to required social/search platforms",
    "pricing_approval":"Human signoff on scope, fees, currency, terms and taxes",
    "production_https_mfa":"Production HTTPS, secrets rotation, rate limits, MFA",
    "backup_restore":"Encrypted controlled production backup and timed restore rehearsal",
    "threat_review":"Independent security test, threat model and remediations",
    "rollback_monitoring":"Monitored launch, rollback and incident response documented",
}
def evaluate_release(manifest):
    if not isinstance(manifest,dict) or not isinstance(manifest.get("target_sha"),str):
        raise ValueError("Missing release target SHA")
    sha=manifest["target_sha"]
    if len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Full immutable 40-character Git commit SHA required")
    gates=manifest.get("gates",{})
    if not isinstance(gates,dict):
        raise ValueError("Gates must be a map")
    results={};pending=[]
    for key,description in GATES.items():
        item=gates.get(key)
        if not isinstance(item,dict):
            results[key]={"status":"blocked","reason":"No verified evidence provided"}
            pending.append(key);continue
        status=item.get("status")
        refs=item.get("evidence_urls")
        reviewer=item.get("verified_by")
        if status=="passed" and isinstance(refs,list) and refs and all(
            isinstance(u,str) and u.startswith("https://") for u in refs
        ) and isinstance(reviewer,str) and reviewer.strip():
            # Attestation is necessary but must still be externally verified by release owner.
            results[key]={"status":"attested","description":description,"evidence_urls":refs,
                          "verified_by":reviewer}
        else:
            results[key]={"status":"blocked","reason":item.get("reason","Missing human-reviewed evidence")}
            pending.append(key)
    return {"target_sha":sha,"release_decision":"HOLD" if pending else "REQUIRES_FINAL_OWNER_SIGNOFF",
            "gate_count":len(GATES),"blocked_count":len(pending),"blocked":pending,"results":results,
            "scope":"Manifest is a set of human attestations, not automated proof of the underlying external systems.",
            "never_auto_deploy":True}
