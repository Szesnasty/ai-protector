"""Run Engine — orchestrates benchmark runs.

Public API:
    RunEngine(http_client, normalizer, persistence, progress)
    RunConfig, RunState, BenchmarkRun
    compute_target_fingerprint()
    Errors: ConfigValidationError, ConcurrencyConflictError, InvalidStateError
    Protocols: HttpClientProtocol, NormalizerProtocol, PersistenceProtocol, ProgressEmitterProtocol
"""

from src.red_team.engine.protocols import (
    HttpClientProtocol,
    HttpResponse,
    NormalizerProtocol,
    PersistenceProtocol,
    ProgressEmitterProtocol,
)
from src.red_team.engine.run_engine import (
    BenchmarkRun,
    ConcurrencyConflictError,
    ConfigValidationError,
    InvalidStateError,
    RunConfig,
    RunEngine,
    RunState,
    compute_target_fingerprint,
)

__all__ = [
    # Engine
    "BenchmarkRun",
    "RunConfig",
    "RunEngine",
    "RunState",
    "compute_target_fingerprint",
    # Errors
    "ConcurrencyConflictError",
    "ConfigValidationError",
    "InvalidStateError",
    # Protocols
    "HttpClientProtocol",
    "HttpResponse",
    "NormalizerProtocol",
    "PersistenceProtocol",
    "ProgressEmitterProtocol",
]
