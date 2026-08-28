# The model matrix

OpenCode is the UI. Every model below is served locally over loopback.
Capability flags are evidence-based: `tool_call: true` exists only where a
live tool round-trip was verified; `reasoning`/`attachment` stay false
until verified (they are false for everything documented here).

## SaveToken MLX (provider `savetoken/...`, port 8321)

Standalone `mlx-lm` checkpoints registered in SaveToken's checksum-verified
manifest. The service serves ONE active model at a time; switching is
explicit.

| Model | Flags | Memory | Notes |
|---|---|---|---|
| `qwen3-coder-30b-a3b-4bit` | tool_call ✅ | 17.2 GB resident | MoE (~3B active); the coding default; slow first-token on huge prompts (~1–2 min prefill for OpenCode's system prompt) |
| `gemma4-e2b-mlx` | tool_call ✅ | 2.6 GB resident | loads in ~2 s; KV 36 KB/token; text-only (multimodal upstream — attachments not served); see quirks below |
| `qwen3.5-healthcare-bf16` / `-4bit` | all ❌ | 3.8 / 1.2 GB | research base models: chat/review only; tools requests get `400 tools_not_supported` |

### gemma4 quirks (verified live, encoded in the engine/manifest)

1. **Tool-call syntax** — `<|tool_call>call:NAME{key:value}<tool_call|>`
   per its official chat template; parsed with no-guessing guarantees
   (truncated calls degrade to text).
2. **Thought channels** — `<|channel>thought … <channel|>` is stripped
   from user-visible output.
3. **Continuation policy** (`drop_tools_on_continuation`) — the checkpoint
   eos's when tool declarations are re-rendered on a turn that only
   appends tool results, so the server drops declarations there; chained
   calls still work.
4. **The list-content bug (fixed)** — clients echo assistant `reasoning`
   back as a *list* of parts; the Gemma template string-concatenates that
   field when `tool_calls` are present, which raised
   `generation failed: can only concatenate str (not "list") to str`.
   Fixed server-side by flattening list/part shapes before rendering
   (regression-tested in the SaveToken repo, mirrored in
   SaveToken-GemmaMLX).

### Switching and rollback

```sh
curl -s -X POST http://127.0.0.1:8321/v1/models/switch \
     -H 'Content-Type: application/json' -d '{"model": "gemma4-e2b-mlx"}'
```

Known limitation: one observed stall switching from gemma (2.6 GB
resident) directly to the 17 GB coder — for large-to-large changes restart
with `SAVETOKEN_MODEL=<id> tools/savetoken_service.sh start` in the
SaveToken repo. Rollback for any model: switch back (above) or restart the
service on the default; OpenCode keeps working with either provider.

## Ollama (provider `ollama/...`, port 11434)

Ollama runtime packages — a private, content-addressed blob store. They
are a different runtime and are **never imported** into SaveToken's
manifest. `ollama/gemma4:e2b-mlx` and `savetoken/gemma4-e2b-mlx` are
different artifacts sharing a name (see
`python3 tools/import_check.py gemma4:e2b-mlx`).

- Discovery: `python3 tools/generate_config.py --config ... --write` adds
  missing local models with every capability `false`; cloud
  (`:cloud`/`-cloud`) and embedding models are never added.
- `--verify-tools MODEL` enables `tool_call` only after a real round trip
  against the live model — never from names, families, or Ollama's
  advertised capabilities.

## Expected performance (36 GB Apple-silicon reference)

| | first token | steady generation | notes |
|---|---|---|---|
| qwen3-coder 30B A3B | ~1–2 min on a ~10k-token agent prompt (prefill-bound) | fast (MoE) | 17 GB resident |
| gemma4 E2B | seconds | fast | 2.6 GB resident; great for quick loops |
| healthcare 4-bit | seconds | moderate | chat/review only |
