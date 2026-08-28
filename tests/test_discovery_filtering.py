"""Tests for Ollama discovery filtering and capability defaults."""

import importlib.util
import json
import os
import unittest
from io import BytesIO
from unittest import mock

import test_config_generation as _t  # module already loaded with gen
gen = _t.gen


class _FakeResponse:
    def __init__(self, body):
        self._body = BytesIO(body if isinstance(body, bytes)
                             else json.dumps(body).encode())
        self.status = 200

    def read(self):
        return self._body.read()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestFiltering(unittest.TestCase):
    def test_policy_mirrors_saveToken_swift_rules(self):
        for cid in ("a:cloud", "b-cloud", "C:0813-CLOUD"):
            self.assertTrue(gen.is_cloud_id(cid), cid)
        for cid in ("cloudy:day", "my-cloud-model", "gemma4:e2b-mlx"):
            self.assertFalse(gen.is_cloud_id(cid), cid)
        for cid in ("qwen3-embedding:4b", "nomic-embed-text", "x-embed-y"):
            self.assertTrue(gen.is_embedding_id(cid), cid)

    def test_entries_all_capabilities_false_and_colon_ids_kept(self):
        payload = {"models": [
            {"name": "gemma4:e2b-mlx",
             "capabilities": ["completion", "tools", "thinking"]},
            {"name": "x:cloud", "capabilities": ["completion"]},
            {"name": "qwen3-embedding:4b", "capabilities": ["embedding"]},
            {"name": "vec-only:1b", "capabilities": ["embedding"]},
            {"name": "dup", "capabilities": ["completion"]},
            {"name": "dup", "capabilities": ["completion"]},
        ]}
        with mock.patch.object(gen.urllib.request, "urlopen",
                               return_value=_FakeResponse(payload)):
            entries = gen.ollama_entries("127.0.0.1", 11434)
        self.assertEqual(list(entries), ["dup", "gemma4:e2b-mlx"])
        for entry in entries.values():
            self.assertFalse(entry["tool_call"])
            self.assertFalse(entry["reasoning"])
            self.assertFalse(entry["attachment"])

    def test_advertised_tools_capability_is_ignored(self):
        # capabilities are NEVER trusted — the flag stays false regardless
        payload = {"models": [{"name": "m", "capabilities": ["tools"]}]}
        with mock.patch.object(gen.urllib.request, "urlopen",
                               return_value=_FakeResponse(payload)):
            entries = gen.ollama_entries("127.0.0.1", 11434)
        self.assertFalse(entries["m"]["tool_call"])

    def test_pretty_name(self):
        self.assertEqual(gen.pretty_name("gemma4:e2b-mlx"),
                         "Gemma 4 E2B MLX — local")

    def test_offline_is_clean_error(self):
        import urllib.error
        with mock.patch.object(
                gen.urllib.request, "urlopen",
                side_effect=urllib.error.URLError("refused")):
            with self.assertRaises(gen.GenError):
                gen.ollama_entries("127.0.0.1", 11434)


class TestVerifyTools(unittest.TestCase):
    def test_verified_only_on_real_tool_call(self):
        ok = {"message": {"tool_calls": [{"function": {
            "name": "multiply", "arguments": {"a": 21, "b": 2}}}]}}
        with mock.patch.object(gen.urllib.request, "urlopen",
                               return_value=_FakeResponse(ok)):
            self.assertTrue(gen.verify_tools("127.0.0.1", 11434, "m"))

        plain = {"message": {"content": "42"}}
        with mock.patch.object(gen.urllib.request, "urlopen",
                               return_value=_FakeResponse(plain)):
            self.assertFalse(gen.verify_tools("127.0.0.1", 11434, "m"))

    def test_loopback_only(self):
        with self.assertRaises(gen.GenError):
            gen.verify_tools("0.0.0.0", 11434, "m")


if __name__ == "__main__":
    unittest.main()
