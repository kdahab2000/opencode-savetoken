#!/usr/bin/env python3
"""Is a model a SaveToken MLX model, an Ollama package, or unknown?

Provenance: extracted 2026-08-28 from the SaveToken repository's
tools/mlx_import_check.py, made standalone (queries the live SaveToken
service instead of importing the manager). Read-only; loopback only.

Usage: python3 tools/import_check.py <model> [--json]
"""

import argparse
import json
import sys
import urllib.request

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _norm(name):
    name = name.strip().lower()
    base, _, tag = name.rpartition(":")
    return base if tag == "latest" and base else name


def _get(url, timeout=2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def report(name, host="127.0.0.1", st_port=8321, oc_port=11434):
    if host not in _LOOPBACK_HOSTS:
        raise ValueError("loopback hosts only")
    out = {"query": name, "verdict": "", "how_to_use": "",
           "savetoken_match": None, "ollama_package": None}

    models = (_get(f"http://{host}:{st_port}/v1/models") or {}).get("data")
    if models is not None:
        for m in models:
            if _norm(m.get("id", "")) == _norm(name):
                out["savetoken_match"] = {
                    "id": m["id"], "tool_support": m.get("tool_support"),
                    "active": m.get("active")}
                out["verdict"] = (f"{m['id']} IS a registered SaveToken MLX "
                                  "model on the running service "
                                  "(checksum-verified manifest).")
                out["how_to_use"] = (
                    f"Pick savetoken/{m['id']} in OpenCode (switch the "
                    "service to it first if inactive).")
                return out

    tags = (_get(f"http://{host}:{oc_port}/api/tags") or {}).get("models",
                                                                [])
    for m in tags:
        if isinstance(m, dict) and _norm(m.get("name", "")) == _norm(name):
            out["ollama_package"] = {
                "name": m.get("name"),
                "quantization": (m.get("details") or {}).get(
                    "quantization_level")}
            out["verdict"] = (
                f"{name!r} is an Ollama runtime package "
                f"({out['ollama_package']['quantization'] or 'unknown'} "
                "quantization, private content-addressed blob store). A "
                "':mlx' tag only means Ollama's runtime is "
                "MLX-accelerated — it is NOT a standalone mlx-lm directory "
                "and cannot be registered as SaveToken MLX.")
            out["how_to_use"] = (
                f"Use it through OpenCode as ollama/{m.get('name')} after "
                "running tools/generate_config.py --write.")
            return out

    out["verdict"] = (f"{name!r} is neither registered on the SaveToken "
                      "service nor present in the local Ollama catalog.")
    out["how_to_use"] = (
        "SaveToken MLX models come only from its manifest (pinned https "
        "sources + checksums); Ollama models come from ollama pull.")
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("model")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--json", action="store_true", dest="as_json")
    args = p.parse_args(argv)
    try:
        result = report(args.model, args.host)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["verdict"])
        print(result["how_to_use"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
