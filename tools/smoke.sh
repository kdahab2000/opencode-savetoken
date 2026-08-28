#!/bin/sh
# One-command end-to-end smoke: a real agent read/edit/test loop through
# OpenCode over loopback against the active SaveToken model.
#
# Provenance: adapted 2026-08-28 from the SaveToken repository's
# tools/smoke_opencode.sh; this copy lives in the integration repo and
# uses a self-contained fixture.
#
#   sh tools/smoke.sh
#
# Environment: SAVETOKEN_MODEL (default qwen3-coder-30b-a3b-4bit — must be
# the ACTIVE model on the service), SAVETOKEN_PORT, SMOKE_TIMEOUT (600),
# SMOKE_KEEP=1 to keep the fixture.

set -eu

HERE="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${SAVETOKEN_PORT:-8321}"
BASE="http://127.0.0.1:${PORT}"
MODEL="${SAVETOKEN_MODEL:-qwen3-coder-30b-a3b-4bit}"
TIMEOUT="${SMOKE_TIMEOUT:-600}"

step() { printf '\n=== %s\n' "$1"; }

step "1/4 SaveToken service"
curl -sf --max-time 5 "${BASE}/health" || {
    echo "service not healthy on ${BASE}; start it in the SaveToken repo" >&2
    exit 1
}
echo "healthy"

step "2/4 model availability"
TMP_MODELS="$(mktemp)"
curl -sf --max-time 5 "${BASE}/v1/models" > "$TMP_MODELS"
python3 - "$TMP_MODELS" "$MODEL" <<'EOF'
import json, sys
models = {m["id"]: m for m in json.load(open(sys.argv[1]))["data"]}
model, want = models, sys.argv[2]
if want not in models:
    sys.exit(f"model {want} not listed; active is "
             f"{[m['id'] for m in models.values() if m.get('active')]}")
if not models[want].get("tool_support"):
    sys.exit(f"model {want} has tool_support=false; smoke needs a "
             "tool-capable model")
print("model ok:", want)
EOF
rm -f "$TMP_MODELS"

step "3/4 fixture project"
FIXTURE="$(mktemp -d /tmp/ocsave-smoke.XXXXXX)"
cleanup() {
    if [ "${SMOKE_KEEP:-0}" = "1" ]; then echo "fixture kept: ${FIXTURE}";
    else rm -rf "${FIXTURE}"; fi
}
trap cleanup EXIT
cat > "${FIXTURE}/.opencode.json" <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    "savetoken": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "SaveToken MLX (local)",
      "options": { "baseURL": "${BASE}/v1", "apiKey": "local" },
      "models": {
        "${MODEL}": {
          "name": "smoke model", "tool_call": true,
          "reasoning": false, "attachment": false,
          "limit": { "context": 65536, "output": 16384 }
        }
      }
    }
  }
}
EOF
cat > "${FIXTURE}/hello.py" <<'EOF'
def greet():
    return "hello"
EOF
cat > "${FIXTURE}/test_hello.py" <<'EOF'
from hello import greet
def test_greet():
    assert greet() == "hello"
    print("TEST OK")
if __name__ == "__main__":
    test_greet()
EOF
echo "fixture: ${FIXTURE}"

step "4/4 OpenCode agent loop (read + edit + test)"
cd "${FIXTURE}"
( sleep "${TIMEOUT}"; pkill -f "opencode run.*savetoken" 2>/dev/null || true ) &
WATCHDOG=$!
set +e
OPENCODE_CONFIG="${FIXTURE}/.opencode.json" \
    opencode run -m "savetoken/${MODEL}" --format json \
    "Do exactly this: 1) read hello.py. 2) create note.txt containing exactly: integration ok. 3) run 'python3 test_hello.py' with the bash tool. Reply with a one-line summary." \
    > events.jsonl 2> opencode.err
RC=$?
set -e
kill "${WATCHDOG}" 2>/dev/null || true

python3 - "${FIXTURE}" "${RC}" <<'EOF'
import json, os, sys
fixture, rc = sys.argv[1], int(sys.argv[2])
if rc != 0:
    sys.exit(f"opencode exited {rc}; see {fixture}/opencode.err")
tools, texts, outputs = [], [], []
for line in open(os.path.join(fixture, "events.jsonl")):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    p = d.get("part", {})
    if d.get("type") in ("tool", "tool_use") and p.get("tool"):
        tools.append(p["tool"])
        outputs.append(str((p.get("state") or {}).get("output", "")))
    if d.get("type") == "text":
        texts.append(p.get("text", ""))
print("tools executed:", sorted(set(tools)))
print("final text:", (texts[-1] if texts else "")[:200])
ok = True
if not tools:
    ok = False; print("FAIL: no tools executed", file=sys.stderr)
note = os.path.join(fixture, "note.txt")
if not os.path.isfile(note) or "integration ok" not in open(note).read():
    ok = False; print("FAIL: note.txt wrong/missing", file=sys.stderr)
if "TEST OK" not in " ".join(texts + outputs):
    ok = False; print("FAIL: test result not reported", file=sys.stderr)
sys.exit(0 if ok else 1)
EOF
echo "SMOKE PASS: local-only agent loop verified end to end"
