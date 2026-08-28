# Privacy and local-only guarantees

- **Loopback only.** Every tool in this repo talks to `127.0.0.1` (Ollama
  11434, SaveToken 8321) or to nothing at all. Non-loopback hosts are
  refused in code, not by convention. The doctor actively probes that the
  SaveToken service does NOT answer on a non-loopback address.
- **No telemetry, no prompt logging.** The integration tools log
  operational errors only. The SaveToken server logs method/path/status
  without bodies by design (audited in that repo's tests).
- **Config writes are surgical.** `generate_config.py --write` adds only
  missing entries under `provider.savetoken.models` /
  `provider.ollama.models`, preserves every unrelated key and hand-tuned
  entry, writes atomically, and keeps a timestamped backup.
- **No credentials.** No API keys are needed or stored; the `apiKey`
  fields in generated configs are placeholders required by the client
  library and carry no secret.
- **One-time model fetches are the only network egress** in the whole
  setup: SaveToken's manager pulls pinned https URLs with checksum
  verification. After setup, no cloud network is required for inference.
- **Ollama cloud models stay out.** Discovery never adds `:cloud` /
  `-cloud` models, and nothing in this repo ever auto-selects a remote
  model.
- **Never included here:** model weights, Ollama private blobs, your
  OpenCode config or its backups, personal absolute paths, credentials.
  The packaging test enforces this on every run.
