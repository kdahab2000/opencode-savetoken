#!/usr/bin/env python3
"""Generate/merge OpenCode provider entries for the two local backends.

Provenance: the merge/backup/atomic-write mechanics and the Ollama
visibility policy are extracted (2026-08-28) from the SaveToken
repository's tools/ollama_discover.py; this copy drops the freetoken
import so the integration repo works standalone.

What it does:
- savetoken provider: entries from the live service's /v1/models when
  reachable (capability flags come from the server's verified manifest —
  never guessed), else from templates/savetoken.models.json.
- ollama provider: discovered local models via loopback /api/tags, cloud
  (:cloud / -cloud) and embedding models excluded, every capability false
  by default. (--verify-tools MODEL can enable tool_call after a real
  round trip.)
- Existing config is preserved: only MISSING entries are added; hand-tuned
  entries are never clobbered (a hand entry "foo" covers "foo:latest");
  unrelated keys are untouched; timestamped backup; atomic write.

Dry-run by default (prints the merge-ready JSON). --write to apply.

Usage:
  python3 tools/generate_config.py --config ~/.config/opencode/opencode.json
  python3 tools/generate_config.py --config ... --write
  python3 tools/generate_config.py --config ... --write --no-ollama
"""

import argparse
import copy
import json
import os
import re
import sys
import time
import urllib.request

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ACRONYMS = {"mlx", "e2b", "a3b", "gguf", "moe", "tts", "cpu", "gpu"}

SAVETOKEN_DEFAULT_PORT = 8321
OLLAMA_DEFAULT_PORT = 11434

SAVETOKEN_PROVIDER = {
    "npm": "@ai-sdk/openai-compatible",
    "name": "SaveToken MLX (local)",
    "options": {"baseURL": "http://127.0.0.1:8321/v1", "apiKey": "local"},
}
OLLAMA_PROVIDER = {
    "npm": "@ai-sdk/openai-compatible",
    "name": "Ollama (local)",
    "options": {"baseURL": "http://127.0.0.1:11434/v1", "apiKey": "local"},
}


class GenError(Exception):
    pass


def _loopback(host):
    if host not in _LOOPBACK_HOSTS:
        raise GenError(f"loopback hosts only, got {host!r}")
    return host


def _get_json(url, timeout):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            if r.status != 200:
                raise GenError(f"HTTP {r.status} from {url}")
            return json.loads(r.read().decode("utf-8"))
    except GenError:
        raise
    except Exception as e:
        raise GenError(f"cannot reach {url}: {e}") from e


# ---- savetoken entries: capability flags come from the verified manifest --

def savetoken_entries(host, port, timeout=2.0, fallback_path=None):
    """Live /v1/models is authoritative (flags recorded after live
    verification in SaveToken's manifest). The bundled fallback template is
    used only when the service is down, and carries all-false flags."""
    _loopback(host)  # refuse non-loopback before any request/fallback
    try:
        data = _get_json(f"http://{host}:{port}/v1/models",
                         timeout)["data"]
        entries = {}
        for m in data:
            entries[m["id"]] = {
                "name": f"{m['id']} — SaveToken MLX local",
                "tool_call": bool(m.get("tool_support")),
                "reasoning": False,
                "attachment": False,
                "limit": {"context": min(m.get("context_limit", 65536)
                                          or 65536, 65536),
                          "output": 8192},
            }
        if entries:
            return entries, "live"
    except (GenError, KeyError, ValueError):
        pass
    if fallback_path and os.path.exists(fallback_path):
        with open(fallback_path) as f:
            loaded = json.load(f)
        # template files may carry a "comment" key; only model objects pass
        return {k: v for k, v in loaded.items()
                if isinstance(v, dict) and "name" in v}, "fallback"
    return {}, "unavailable"


# ---- ollama entries (policy mirrored from SaveToken's Swift app) ----------

def is_cloud_id(model_id):
    n = (model_id or "").lower()
    return n.endswith(":cloud") or n.endswith("-cloud")


def is_embedding_id(model_id):
    n = (model_id or "").lower()
    return "embedding" in n or "embed-" in n


def is_embedding_only_entry(entry):
    caps = entry.get("capabilities")
    return (isinstance(caps, list) and "embedding" in caps
            and "completion" not in caps)


def pretty_name(model_id):
    tokens = []
    for part in re.split(r"[-_]", model_id.replace(":", "-")):
        if part in _ACRONYMS:
            tokens.append(part.upper())
        elif re.fullmatch(r"[a-z]+[0-9][0-9a-z.]*", part):
            m = re.match(r"([a-z]+)([0-9].*)", part)
            tokens.append(m.group(1).capitalize() + " " + m.group(2))
        elif re.fullmatch(r"[0-9]+[a-z]+", part):
            tokens.append(part.upper())
        else:
            tokens.append(part.capitalize())
    return " ".join(t for t in tokens if t) + " — local"


def ollama_entries(host, port, timeout=3.0):
    tags = _get_json(f"http://{_loopback(host)}:{port}/api/tags",
                     timeout).get("models", [])
    entries, seen = {}, set()
    for e in tags:
        if not isinstance(e, dict):
            continue
        name = e.get("name")
        if not isinstance(name, str) or not name:
            continue
        if is_cloud_id(name) or is_embedding_id(name) \
                or is_embedding_only_entry(e) or name in seen:
            continue
        seen.add(name)
        # capabilities are NEVER inferred from Ollama metadata or names
        entries[name] = {
            "name": pretty_name(name),
            "tool_call": False,
            "reasoning": False,
            "attachment": False,
            "limit": {"context": 32768, "output": 8192},
        }
    return dict(sorted(entries.items()))


def verify_tools(host, port, model_id, timeout=180.0):
    """The only way a discovered Ollama model gets tool_call=true: one real
    tool-call round trip against the live model."""
    body = json.dumps({
        "model": model_id, "stream": False, "think": False,
        "messages": [{"role": "user",
                      "content": "Use the multiply tool to compute 21 times "
                                 "2. Call the tool; do not answer in plain "
                                 "text."}],
        "tools": [{"type": "function", "function": {
            "name": "multiply", "description": "Multiply two integers.",
            "parameters": {"type": "object",
                           "properties": {"a": {"type": "integer"},
                                          "b": {"type": "integer"}},
                           "required": ["a", "b"]}}}],
        "options": {"num_predict": 256},
    }).encode()
    req = urllib.request.Request(
        f"http://{_loopback(host)}:{port}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception:
        return False
    msg = payload.get("message") if isinstance(payload, dict) else None
    calls = msg.get("tool_calls") if isinstance(msg, dict) else None
    for call in calls or []:
        fn = call.get("function") if isinstance(call, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            return True
    return False


# ---- merge (preserve everything, add only missing) -------------------------

def _covers(existing_keys, model_id):
    if model_id in existing_keys:
        return True
    base, sep, tag = model_id.rpartition(":")
    if sep and tag == "latest":
        return base in existing_keys
    return model_id + ":latest" in existing_keys


def merge(config, provider_key, provider_meta, entries, force=False):
    if not isinstance(config, dict):
        raise GenError("config root must be a JSON object")
    provider = config.setdefault("provider", {})
    node = provider.get(provider_key)
    if not isinstance(node, dict):
        node = copy.deepcopy(provider_meta)
        provider[provider_key] = node
    if not isinstance(node.get("models"), dict):
        node.setdefault("models", {})
    out = copy.deepcopy(config)
    target = out["provider"][provider_key]["models"]
    for model_id, entry in entries.items():
        if _covers(node["models"], model_id) and not force:
            continue
        target[model_id] = copy.deepcopy(entry)
    return out


def atomic_write_with_backup(path, config):
    backup = None
    if os.path.exists(path):
        backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        with open(path) as src, open(backup, "w") as dst:
            dst.write(src.read())
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        f.write(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return backup


def main(argv=None):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", required=True)
    p.add_argument("--write", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-ollama", action="store_true")
    p.add_argument("--no-savetoken", action="store_true")
    p.add_argument("--savetoken-port", type=int, default=SAVETOKEN_DEFAULT_PORT)
    p.add_argument("--ollama-port", type=int, default=OLLAMA_DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--verify-tools", default=None, metavar="OLLAMA_MODEL")
    args = p.parse_args(argv)

    try:
        _loopback(args.host)
        st_entries, st_source = ({"placeholder": None}, "skipped") \
            if args.no_savetoken else savetoken_entries(
                args.host, args.savetoken_port,
                fallback_path=os.path.join(here, "templates",
                                           "savetoken.models.json"))
        st_entries = {k: v for k, v in st_entries.items() if v}
        oc_entries = {} if args.no_ollama else ollama_entries(
            args.host, args.ollama_port)
    except GenError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.verify_tools:
        model_id = args.verify_tools
        print(f"verifying tool calling for {model_id!r} with a real round "
              "trip...", file=sys.stderr)
        if model_id in oc_entries and verify_tools(
                args.host, args.ollama_port, model_id):
            oc_entries[model_id]["tool_call"] = True
            print(f"verified: {model_id} tool_call will be enabled",
                  file=sys.stderr)
        else:
            print(f"not verified; leaving tool_call=false", file=sys.stderr)

    merged = {"savetoken": st_entries, "ollama": oc_entries}
    if not args.write:
        print(json.dumps(merged, indent=2, ensure_ascii=False))
        print(f"savetoken source: {st_source}; dry run — nothing written",
              file=sys.stderr)
        return 0

    try:
        config = json.load(open(args.config))
    except (OSError, ValueError) as e:
        print(f"error: cannot read {args.config}: {e}", file=sys.stderr)
        return 1
    try:
        config = merge(config, "savetoken", SAVETOKEN_PROVIDER, st_entries,
                       force=args.force)
        config = merge(config, "ollama", OLLAMA_PROVIDER, oc_entries,
                       force=args.force)
        backup = atomic_write_with_backup(args.config, config)
    except (GenError, OSError) as e:
        print(f"error: {e}; original config untouched", file=sys.stderr)
        return 1
    if backup:
        print(f"backup: {backup}", file=sys.stderr)
    print(f"config updated: {args.config}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
