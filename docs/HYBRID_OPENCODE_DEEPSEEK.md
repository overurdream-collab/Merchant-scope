# MerchantScope: OpenCode + DeepSeek (Ollama excluded)

## Architecture and automatic task selection
OpenCode is **an agent/tool environment**, not a local AI model. DeepSeek provides the model inference. This is a hybrid *execution architecture*, not two AI models:

| Task | Selected engine | Permissions |
|---|---|---|
| Source-grounded merchant content, audience, competitive analysis, draft recommendations or proposals | DeepSeek official HTTPS API | Draft-only; evidence citations and independent approval |
| Code reviews, test/design reviews of the project | OpenCode CLI with DeepSeek provider | Local developer command; explicit opt-in; `plan` agent, no `--auto` |
| Validate inputs, citations, budgets and release decisions | Local deterministic Python | No model cost or network |
| Missing key/model, provider error, incomplete JSON | **Fail closed** | Never invent output or silently use another provider |

`app/hybrid_ai.py` provides `select_backend(task)`, an HTTPS DeepSeek JSON adapter, and an opt-in OpenCode review runner. It does **not** launch OpenCode in the public API or give source text permission to change project files.

## On a local Windows 8GB laptop
1. Install Python dependencies and install OpenCode CLI using the [official instructions](https://opencode.ai/docs/cli/); run `opencode --help` to check.
2. Connect DeepSeek provider to OpenCode via `opencode auth login` or OpenCode `/connect`. Choose the exact available model ID with `opencode models`.
3. Set `DEEPSEEK_API_KEY` (never commit it), `MERCHANTSCOPE_DEEPSEEK_MODEL` to a currently supported DeepSeek API model ID, and `MERCHANTSCOPE_OPENCODE_MODEL` to a tested `deepseek/<model>` OpenCode model ID. Model availability evolves; verify with `opencode models`.
4. For code reviews only, set `MERCHANTSCOPE_OPENCODE_ENABLED=1` on the developer shell and run:
   `python scripts/opencode_review.py --repo . --task code_review --prompt "Inspect tenant isolation tests"`.
5. Check config safely: `python scripts/check_hybrid.py`; for one **billable** actual DeepSeek request, explicitly run `python scripts/check_hybrid.py --live`.
6. Run `python -m pytest -q tests/test_hybrid_ai.py tests/test_agent.py tests/test_pilot_runner.py`.

### Windows PowerShell environment example
```powershell
$env:DEEPSEEK_API_KEY = (Read-Host "DeepSeek API key")
$env:MERCHANTSCOPE_DEEPSEEK_MODEL = (Read-Host "DeepSeek API model ID")
$env:MERCHANTSCOPE_OPENCODE_MODEL = (Read-Host "OpenCode provider/model ID: deepseek/...")
$env:MERCHANTSCOPE_OPENCODE_ENABLED = "1"
python scripts/check_hybrid.py
opencode models
```

## Security and cost controls
- Do **not** store API keys in source files, Git, browser settings, screenshots, chat messages, or logs.
- DeepSeek endpoint fixed to `https://api.deepseek.com/chat/completions`; request prompt length <=19k characters, output <=1,300 tokens and body <=250k bytes, timeout 45 seconds. No unbounded retry/fallback.
- DeepSeek costs money when called. `--live` sends one intentionally small request; automatic CI uses mocks and makes **zero actual provider calls**.
- Merchant facts, posts and competitors are untrusted. AI output only creates recommendations pending independent human review, with cited existing evidence IDs; no automated outreach.
- OpenCode is launched only by a local operator after enabling it and with an explicit checked-out Git directory. `plan` is intended to be read-only, but actual permissions must be reviewed in the installed OpenCode version; do not treat this as an OS sandbox.
- DeepSeek requires an active API key, billing/credit and accessible network. **The repository tests verify the adapters with mocks, not live credentials.**
- Your previous Ollama setup is not required. Do not expose an Ollama service or proxy into production.

Official documentation: https://opencode.ai/docs/cli/commands/ and https://api-docs.deepseek.com/api/create-chat-completion/.

## Explicit external processing approval
The local-pilot UI requires an unchecked-by-default consent control for each DeepSeek marketing request. API calls to `/api/merchants/{id}/agent-draft` require `allow_external_processing: true`, otherwise return HTTP 403 **before calling any external provider**. Only share permitted business content, and obtain consent when needed; this checkbox is not a substitute for privacy-law compliance or authorization from the data owner.
