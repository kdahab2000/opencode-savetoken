"""Tests for OpenCode config generation (merge/backup/atomic/preserve).

Run: python3 -m unittest discover -s tests -v   (from the repo root)
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "generate_config",
    os.path.join(_HERE, "tools", "generate_config.py"))
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)


def _base_config():
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": "savetoken/qwen3-coder-30b-a3b-4bit",
        "provider": {
            "savetoken": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "SaveToken MLX (local)",
                "options": {"baseURL": "http://127.0.0.1:8321/v1"},
                "models": {
                    "hand-tuned": {"name": "keep me", "tool_call": True},
                },
            },
        },
    }


class TestMerge(unittest.TestCase):
    def test_adds_only_missing_and_preserves_everything_else(self):
        cfg = _base_config()
        entries = {
            "gemma4-e2b-mlx": {"name": "x", "tool_call": True,
                               "reasoning": False, "attachment": False,
                               "limit": {"context": 65536, "output": 8192}},
            "hand-tuned": {"name": "regenerated", "tool_call": False},
        }
        merged = gen.merge(cfg, "savetoken", gen.SAVETOKEN_PROVIDER,
                           entries)
        models = merged["provider"]["savetoken"]["models"]
        self.assertEqual(models["hand-tuned"]["name"], "keep me")
        self.assertIn("gemma4-e2b-mlx", models)
        self.assertEqual(merged["model"], cfg["model"])
        # input untouched
        self.assertNotIn("gemma4-e2b-mlx",
                         cfg["provider"]["savetoken"]["models"])

    def test_untagged_entry_covers_latest(self):
        cfg = _base_config()
        merged = gen.merge(cfg, "ollama", gen.OLLAMA_PROVIDER,
                           {"ornith-9b:latest": {"name": "n"}})
        # not added because hand-tuned 'ornith-9b' exists
        self.assertNotIn("ornith-9b:latest",
                         cfg["provider"].setdefault("ollama", {})
                         .setdefault("models", {}))

    def test_invents_provider_node_when_absent(self):
        cfg = _base_config()
        merged = gen.merge(cfg, "ollama", gen.OLLAMA_PROVIDER,
                           {"x:y": {"name": "n"}})
        node = merged["provider"]["ollama"]
        self.assertEqual(node["options"]["baseURL"],
                         "http://127.0.0.1:11434/v1")
        self.assertIn("x:y", node["models"])


class TestAtomicWrite(unittest.TestCase):
    def test_backup_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "opencode.json")
            with open(path, "w") as f:
                f.write('{"a": 1}')
            before = open(path).read()
            backup = gen.atomic_write_with_backup(path, {"a": 2})
            self.assertTrue(backup and os.path.exists(backup))
            self.assertEqual(open(backup).read(), before)
            self.assertEqual(json.load(open(path)), {"a": 2})
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_new_file_no_backup(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "new.json")
            self.assertIsNone(gen.atomic_write_with_backup(path, {"a": 1}))


class TestSavetokenEntries(unittest.TestCase):
    def test_flags_come_from_live_service_not_guesses(self):
        payload = {"data": [
            {"id": "qwen3-coder-30b-a3b-4bit", "tool_support": True,
             "context_limit": 262144},
            {"id": "qwen3.5-healthcare-bf16", "tool_support": False,
             "context_limit": 262144},
        ]}

        def fake_get(url, timeout):
            return payload

        with mock.patch.object(gen, "_get_json", side_effect=fake_get):
            entries, source = gen.savetoken_entries("127.0.0.1", 8321)
        self.assertEqual(source, "live")
        self.assertTrue(entries["qwen3-coder-30b-a3b-4bit"]["tool_call"])
        self.assertFalse(entries["qwen3.5-healthcare-bf16"]["tool_call"])

    def test_fallback_template_all_false(self):
        entries, source = gen.savetoken_entries(
            "127.0.0.1", 59999,  # nothing listens here
            fallback_path=os.path.join(_HERE, "templates",
                                       "savetoken.models.json"))
        self.assertEqual(source, "fallback")
        for entry in entries.values():
            self.assertFalse(entry["tool_call"])
            self.assertFalse(entry["reasoning"])
            self.assertFalse(entry["attachment"])

    def test_non_loopback_refused(self):
        with self.assertRaises(gen.GenError):
            gen.savetoken_entries("example.com", 8321)


if __name__ == "__main__":
    unittest.main()
