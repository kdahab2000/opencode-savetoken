# Security policy

## Threat model

This repository contains integration tooling for local-only inference.
The assets it manages are OpenCode provider configs (user-owned) and
read-only queries to loopback services. Model weights, credentials, and
private runtime blobs are explicitly out of scope and must never be
committed (enforced by tests/test_packaging.py).

- All network access in tools is loopback-only and hard-fails on
  non-loopback hosts.
- Config writes are atomic, backed up, and restricted to the two provider
  model lists; unrelated settings are never touched.
- Discovered models enter with every capability disabled; enabling
  tool_call requires an explicit, user-requested live round trip.
- The inference engine (SaveToken) enforces its own manifest
  verification, loopback binding, and no-content logging — see that
  repository's SECURITY.md.

## Reporting

Open a private advisory in the SaveToken repository for engine issues, or
contact the maintainer of this integration repo directly. Do not open
public issues containing prompts, paths, or config contents you consider
sensitive.
