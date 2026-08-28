#!/bin/sh
# Doctor: check the whole local OpenCode + SaveToken + Ollama stack.
# Read-only; loopback only; prints the exact fix for anything it finds.
#
#   sh tools/doctor.sh
#
# Environment: SAVETOKEN_PORT (8321), OLLAMA_PORT (11434),
# SAVETOKEN_REPO (../SaveToken), OPENCODE_CONFIG (~/.config/opencode/opencode.json)

set -u

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ST_PORT="${SAVETOKEN_PORT:-8321}"
OC_PORT="${OLLAMA_PORT:-11434}"
ST_BASE="http://127.0.0.1:${ST_PORT}"
OC_BASE="http://127.0.0.1:${OC_PORT}"
SAVETOKEN_REPO="${SAVETOKEN_REPO:-$(dirname "$HERE")/SaveToken}"
OPENCODE_CONFIG="${OPENCODE_CONFIG:-${HOME}/.config/opencode/opencode.json}"

pass=0; fail=0; warn=0

ok()   { echo "  ok    $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL  $1"; fail=$((fail+1)); }
warn() { echo "  warn  $1"; warn=$((warn+1)); }
fix()  { echo "        fix: $1"; }

echo "== OpenCode (the only coding UI)"
if command -v opencode >/dev/null 2>&1; then
    ok "opencode CLI on PATH ($(opencode --version 2>/dev/null | head -1))"
else
    bad "opencode CLI not found"
    fix "install OpenCode (https://opencode.ai) — it is the UI; this repo never bundles it"
fi

echo "== SaveToken backend (loopback ${ST_BASE})"
if [ -d "${SAVETOKEN_REPO}/freetoken" ]; then
    ok "SaveToken checkout at ${SAVETOKEN_REPO}"
else
    warn "SaveToken checkout not found at ${SAVETOKEN_REPO}"
    fix "set SAVETOKEN_REPO=/path/to/SaveToken (the savetoken/* provider needs it)"
fi
if curl -sf --max-time 3 "${ST_BASE}/health" >/dev/null 2>&1; then
    ok "service healthy"
    curl -sf --max-time 3 "${ST_BASE}/health" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("        model=%s resident=%.2fGB" % (d.get("active_model_id"), d.get("weights_resident_gb") or 0))
' 2>/dev/null || true
    # loopback-only proof: the service must refuse to answer elsewhere
    if curl -sf --max-time 2 "http://localhost:${ST_PORT}/health" >/dev/null 2>&1 \
        && ! curl -sf --max-time 2 "http://$(ipconfig getifaddr en0 2>/dev/null):${ST_PORT}/health" >/dev/null 2>&1; then
        ok "loopback-only binding confirmed (non-loopback refused)"
    else
        warn "could not confirm loopback-only binding"
    fi
else
    bad "SaveToken service not healthy on ${ST_BASE}"
    fix "cd ${SAVETOKEN_REPO} && tools/savetoken_service.sh start"
fi
if curl -sf --max-time 3 "${ST_BASE}/v1/models" 2>/dev/null | grep -q '"tool_support": true'; then
    ok "at least one verified tool-capable savetoken model listed"
else
    warn "no tool-capable savetoken model listed (chat/review only)"
fi

echo "== Ollama backend (loopback ${OC_BASE})"
if curl -sf --max-time 3 "${OC_BASE}/api/tags" >/dev/null 2>&1; then
    ok "ollama reachable"
else
    warn "ollama not reachable on ${OC_BASE} (fine if you only use SaveToken MLX)"
fi

echo "== OpenCode config (${OPENCODE_CONFIG})"
if [ -f "${OPENCODE_CONFIG}" ]; then
    ok "config exists"
    python3 - "${OPENCODE_CONFIG}" <<'EOF' && pass=$((pass+1)) || { fail=$((fail+1)); }
import json, sys
cfg = json.load(open(sys.argv[1]))
st = cfg.get("provider", {}).get("savetoken", {})
oc = cfg.get("provider", {}).get("ollama", {})
assert st.get("options", {}).get("baseURL", "").startswith("http://127.0.0.1"), "savetoken baseURL must be loopback"
assert oc.get("options", {}).get("baseURL", "").startswith("http://127.0.0.1"), "ollama baseURL must be loopback"
bad_models = [f"{p}/{m}" for p, node in (("savetoken", st), ("ollama", oc))
              for m, e in (node.get("models") or {}).items()
              if not isinstance(e, dict) or "name" not in e]
assert not bad_models, f"malformed model entries: {bad_models}"
EOF
    [ $? -eq 0 ] || fix "re-run: python3 tools/generate_config.py --config ${OPENCODE_CONFIG} --write"
else
    warn "no OpenCode config yet"
    fix "python3 tools/generate_config.py --config ${OPENCODE_CONFIG} --write"
fi

echo "== packaging hygiene (this repo)"
# Delegate to the repo's own packaging tests (secrets, weights, personal
# paths, vendoring) — the shell grep kept tripping over its own patterns.
if (cd "${HERE}" && python3 -m unittest tests.test_packaging -q >/dev/null 2>&1); then
    ok "packaging tests pass (no secrets, weights, or personal paths)"
else
    bad "packaging tests failed — see tests/test_packaging.py"
fi
if find "${HERE}" -name "*.safetensors" -o -name "*.gguf" | grep -q .; then
    bad "model weights found in repo"
else
    ok "no model weights in repo"
fi

echo
echo "passed: ${pass}  warnings: ${warn}  failed: ${fail}"
[ "$fail" = "0" ] || exit 1
echo "DOCTOR OK — run sh tools/smoke.sh for the end-to-end agent test"
