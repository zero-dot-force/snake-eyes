---
tag: snake-eyes-architecture
author: jay-flowers
category: decision
created_at: 2026-05-17T16:29:16Z
identity: snake-eyes-architecture-20260517T162916-jay-flowers
tier: draft
---

Snake Eyes architecture decision: Hybrid Go core + Python analyzer. Gaze (unbound-force/gaze) becomes the universal core providing CLI, TUI, taxonomy, classification scoring, CRAP computation, reports, and AI pipeline. Snake Eyes (zero-dot-force/snake-eyes) is a Python package implementing gaze's external analyzer protocol via JSON-RPC 2.0 over stdin/stdout. This creates a platform pattern where future language analyzers (TypeScript, Rust, etc.) plug into the same core. Filed as gaze issues #95 (protocol) and #96 (taxonomy). Zero-dot-force is the labs org for unbound-force (v0.x experiments).
