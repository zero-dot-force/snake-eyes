---
tag: snake-eyes-research
author: jay-flowers
category: reference
created_at: 2026-05-17T16:29:23Z
identity: snake-eyes-research-20260517T162923-jay-flowers
tier: draft
---

Python static analysis tool research for side-effect detection: CodeQL eliminated (license blocks private repos, CLI-only, security-focused). Pyright/mypy eliminated as foundations (wrong problem, no embeddable API). Best approach for Python analyzer: ast + symtable (stdlib, zero deps) for structural detection, Astroid (Pylint's backbone) for inference/name resolution/cross-module imports, coverage.py for coverage data, radon for cyclomatic complexity. Scalpel (academic, 329 stars) has promising CFG/call-graph/SSA but may be fragile. Tree-sitter viable if writing in Go but loses Python semantic analysis. Semgrep good for pattern matching but CLI-only and can't aggregate into function-level verdicts. Pysa's source/sink/sanitizer model is excellent conceptual inspiration for the annotation system.
