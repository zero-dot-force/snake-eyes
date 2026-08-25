---
tag: gaze-python-backend
author: jay-flowers
category: decision
created_at: 2026-08-25T19:45:56Z
identity: gaze-python-backend-20260825T194556-jay-flowers
tier: draft
---

Gaze now ships two expansion models: (1) JSON-RPC 2.0 analyzer protocol v1.1.0 (docs/protocol.md) — 5 required methods initialize/analyze/complexity/coverage/shutdown, optional discover/test_mapping/classify_signals/analyze-stream; Go Gaze owns scoring/CLI/reports; (2) full language ports bound by docs/porting/contracts.md. snake-eyes (zero-dot-force) is the intended protocol backend but has ZERO Python code — spec-only scaffold from May 2026, and the spec is stale vs protocol 1.1.0 (treats discover as required; defers complexity/coverage which are now required; P0 missing SentinelError; analyze expected file lists not root_path+patterns). gaze-py (mpeter) is a complete Python-native port (v0.5.0, ~7.2k LOC, 85% coverage, Apache 2.0, ast+astroid) that reimplements detection, 5-signal classification, CRAP, GazeCRAP, quality pipeline, CLI — NOT a protocol backend. Taxonomy already drifted: gaze-py has 38 Go-era types, Gaze now has 48 (missing GeneratorYield, MonkeyPatch, DescriptorEffect, ErrorSignal, etc.). Recommended third way: harvest gaze-py's detector/quality/complexity as a library, wrap as gaze-analyzer-python JSON-RPC backend, keep scoring in Go Gaze; invite mpeter; do not dual-maintain CRAP formulas.
