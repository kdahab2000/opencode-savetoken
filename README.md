# OpenCode-SaveToken

The public integration project that makes **OpenCode the single coding UI**
on your Mac with **local-only inference**: SaveToken (MLX) and Ollama as two
explicitly labeled local backends. This repository is an integration and
orchestration layer — not a second coding UI, and not a fork of SaveToken.

```
OpenCode (the only UI: chat, agent, file edits, tests, git)
    │ OpenAI-compatible HTTP, loopback only
    ├─► SaveToken MLX   127.0.0.1:8321   verified manifest models
    └─► Ollama          127.0.0.1:11434  ollama-managed models
```

## What this repo is (and is not)

**Is:** config generation for OpenCode providers (preserving your settings,
with backups), model discovery/import tooling, a doctor that checks the
whole local stack, a one-command smoke test, documentation for the models
and the privacy model, and tests for all of it.

**Is not:** the inference engine. The engine is your local
[SaveToken](https://github.com/kdahab2000/savetoken) checkout (pinned
dependency — see below). OpenCode itself is an external dependency and is
never copied or wrapped. No model weights and no Ollama blobs are included
or ever imported.

### Why an orchestration layer instead of a full fork

Duplicating the engine would fork security-sensitive code (manifest
verification, loopback binding, admission control) that already exists and
is tested in SaveToken. This repo instead pins the backend and owns only
the integration surface: provider config, discovery, verification, and
docs. Trade-off: you need a local SaveToken checkout for the
`savetoken/...` provider to serve; everything else (Ollama discovery,
config generation, doctor) works standalone.

## The two providers, honestly labeled

| Provider | What belongs there | Capability rules |
|---|---|---|
| `savetoken/<id>` | Standalone MLX checkpoints registered in SaveToken's checksum-verified manifest (e.g. `qwen3-coder-30b-a3b-4bit`, `gemma4-e2b-mlx`) | `tool_call: true` only after a live round-trip verification recorded in the manifest |
| `ollama/<tag>` | Ollama runtime packages (e.g. `gemma4:e2b-mlx`) | discovered with every capability `false` until verified; cloud (`:cloud`/`-cloud`) and embedding models are never added |

**Never** assume an Ollama `:mlx` tag is a SaveToken MLX model — it only
means Ollama's runtime is MLX-accelerated. Run
`python3 tools/import_check.py gemma4:e2b-mlx` for the evidence-based
verdict on any model.

## Quick start

```sh
# 0) prerequisites: opencode CLI on PATH; SaveToken checkout; Ollama (optional)
python3 tools/generate_config.py --config ~/.config/opencode/opencode.json --write
sh tools/doctor.sh
sh tools/smoke.sh
```

- `generate_config.py` adds missing provider entries (preserving everything
  else, hand-tuned models included; timestamped backup; atomic write).
  Dry-run by default.
- `doctor.sh` checks Ollama, the SaveToken service health + model catalog,
  model availability, OpenCode presence, config sanity, and loopback-only
  behavior — and prints the exact fix for anything it finds.
- `smoke.sh` runs a real agent read/edit/test loop through OpenCode over
  loopback against the active SaveToken model.

## Documentation

- [docs/models.md](docs/models.md) — the model matrix: savetoken/gemma4-e2b-mlx vs
  ollama/gemma4:e2b-mlx, the Qwen coder default, switching, the Gemma
  list-content bug fix, memory/performance expectations.
- [docs/privacy.md](docs/privacy.md) — local-only guarantees and what the
  tools will never do.
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/release.md](docs/release.md) — how to publish this repo later.
- [SECURITY.md](SECURITY.md) — threat model and reporting.

## Support the project

If this project helps you run coding models locally or reduce hosted-AI costs, you can support maintenance through [GitHub Sponsors](https://github.com/sponsors/kdahab2000). Sponsorship funds compatibility testing, MLX model support, security maintenance, and documentation. See [the sponsorship brief](docs/sponsorship.md) for the project mission, screenshots, and sponsorship tiers.

![SaveToken local inference](docs/assets/savetoken-local-inference.png)

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Covers config generation (preserve/backup/atomic), Ollama discovery and
cloud/embedding filtering with safe-default capabilities, the tool-call
protocol probe, packaging hygiene (no secrets, no weights, no personal
absolute paths), and — via [SaveToken-GemmaMLX](../SaveToken-GemmaMLX)
mirrors — the Gemma parser.

## License

MIT + attribution in [LICENSE](LICENSE)/[NOTICE](NOTICE). Model weights are
governed by their own upstream licenses (Apache-2.0 for the models
referenced in docs) and are never part of this repository.
