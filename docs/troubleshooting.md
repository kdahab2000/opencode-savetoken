# Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| OpenCode: `Model not found: savetoken/...` | Provider entry missing — run `python3 tools/generate_config.py --config ~/.config/opencode/opencode.json --write` |
| Wrong model answers under `savetoken/<id>` | The service serves ONE active model; switch it: `curl -s -X POST http://127.0.0.1:8321/v1/models/switch -H 'Content-Type: application/json' -d '{"model":"<id>"}'` |
| `400 tools_not_supported` | Active model is chat/review only (e.g. healthcare). Switch to a verified tool-capable model. |
| `generation failed: can only concatenate str (not "list") to str` | FIXED: assistant `reasoning` echoed as a list hit a Gemma template concat. Update the SaveToken repo past 2026-08-28. |
| Generation dies on first request after model switch | Older SaveToken builds lacked the Metal warm-up; update the repo (Engine.load warms up on the loading thread). |
| Switching large↔large models hangs | Known limitation — restart with `SAVETOKEN_MODEL=<id>` instead of /v1/models/switch. |
| Pulled an Ollama model, OpenCode doesn't list it | Re-run `generate_config.py --write` (adds missing entries, never clobbers). |
| Is `ollama/foo:mlx` the same as `savetoken/foo`? | No — run `python3 tools/import_check.py foo:mlx` for the evidence-based verdict. |
| Smoke fails with no tools executed | Check `sh tools/doctor.sh`; the smoke model must be the ACTIVE service model with tool_support=true. |
