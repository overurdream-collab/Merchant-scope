import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app import hybrid_ai

def test_routing_is_deterministic_and_no_ollama():
    assert hybrid_ai.select_backend("content")=="deepseek"
    assert hybrid_ai.select_backend("competition")=="deepseek"
    assert hybrid_ai.select_backend("code_review")=="opencode"
    assert hybrid_ai.select_backend("validate_evidence")=="local_rules"
    with pytest.raises(ValueError):hybrid_ai.select_backend("ollama")

def test_missing_api_key_fails_closed(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    monkeypatch.delenv("MERCHANTSCOPE_DEEPSEEK_MODEL",raising=False)
    with pytest.raises(HTTPException) as ex:hybrid_ai.deepseek_json("draft")
    assert ex.value.status_code==503

def test_deepseek_http_request_and_response_are_bounded(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY","test-key-not-real")
    monkeypatch.setenv("MERCHANTSCOPE_DEEPSEEK_MODEL","test-deepseek-model")
    captured={}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,size):
            assert size==250001
            return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":'{"summary":"مقترح","recommendations":[]}'}}]}).encode()
    def fake_transport(req,timeout):
        captured["url"]=req.full_url
        captured["method"]=req.get_method()
        captured["request"]=json.loads(req.data)
        captured["timeout"]=timeout
        assert req.get_header("Authorization")=="Bearer test-key-not-real"
        return Response()
    result=hybrid_ai.deepseek_json("Analyse source only",transport=fake_transport)
    assert result["summary"]=="مقترح"
    assert captured["url"]=="https://api.deepseek.com/chat/completions"
    assert captured["request"]["model"]=="test-deepseek-model"
    assert captured["request"]["stream"] is False
    assert captured["request"]["max_tokens"]<=1300
    assert captured["timeout"]<=45

def test_truncated_or_non_json_response_rejected(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY","test-key")
    monkeypatch.setenv("MERCHANTSCOPE_DEEPSEEK_MODEL","test-model")
    class Response:
        def __init__(self,finish,content):self.finish,self.content=finish,content
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):
            return json.dumps({"choices":[{"finish_reason":self.finish,"message":{"content":self.content}}]}).encode()
    for data in [("length",'{"summary":"cut"}'),("stop","not JSON")]:
        with pytest.raises(HTTPException) as ex:
            hybrid_ai.deepseek_json("safe",transport=lambda *a,d=data:Response(*d))
        assert ex.value.status_code==502

def test_deepseek_does_not_leak_transport_exception(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY","test-key")
    monkeypatch.setenv("MERCHANTSCOPE_DEEPSEEK_MODEL","test-model")
    def broken(*args,**kwargs):raise OSError("SECRET-DO-NOT-ECHO")
    with pytest.raises(HTTPException) as ex:hybrid_ai.deepseek_json("input",transport=broken)
    assert "SECRET" not in ex.value.detail

def test_opencode_opt_in_and_safe_argv(tmp_path,monkeypatch):
    repo=tmp_path/"repo";repo.mkdir();(repo/".git").mkdir()
    monkeypatch.setenv("MERCHANTSCOPE_OPENCODE_ENABLED","1")
    monkeypatch.setenv("MERCHANTSCOPE_OPENCODE_MODEL","deepseek/test-model")
    used={}
    def runner(argv,**kwargs):
        used["argv"]=argv;used["kwargs"]=kwargs
        return SimpleNamespace(returncode=0,stdout="Review: no changes",stderr="")
    result=hybrid_ai.opencode_review("code_review","Inspect validation only",repo,execute=runner)
    assert result["status"]=="draft_review"
    assert used["argv"][:3]==["opencode","run","--standalone"]
    assert "--agent" in used["argv"] and "plan" in used["argv"]
    assert not any(x in used["argv"] for x in ("--auto","build","sh","bash"))
    assert used["kwargs"]["timeout"]<=120
    monkeypatch.setenv("MERCHANTSCOPE_OPENCODE_ENABLED","0")
    with pytest.raises(HTTPException) as ex:
        hybrid_ai.opencode_review("code_review","Inspect",repo,execute=runner)
    assert ex.value.status_code==503

def test_code_agent_cannot_receive_marketing_requests(tmp_path):
    with pytest.raises(ValueError):
        hybrid_ai.opencode_review("content","Analyse merchants",tmp_path)
