from dataclasses import dataclass


@dataclass(frozen=True)
class RunSnapshot:
    active_tests: tuple
    results: dict
    final_status: str
    termination_reason: str
    shutdown_success: object
    shutdown_error: str
    diagnostics: tuple
    summary: dict
