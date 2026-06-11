"""External deterministic attack corpus + CI gate.

See docs/plan/A3a-external-deterministic-attacks.spec.md.

Principle: *generate once (offline) → freeze → replay (in CI, deterministic)*.
This package owns the frozen corpus, its integrity manifest, the loaders that
normalize external sources (promptfoo) into the canonical schema, and the
deterministic obfuscation strategies that double as the A2 regression set.
"""
