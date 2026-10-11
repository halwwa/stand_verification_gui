from dataclasses import dataclass
from typing import Dict, List, Optional, Union


@dataclass(frozen=True)
class FrequencyResult:
    reference_frequency_hz: float
    measured_frequency_hz: Optional[float]
    error_hz: Optional[float]
    tolerance_hz: Optional[float]
    if_frequency_khz: Optional[float]
    status: str
    comment: str


@dataclass(frozen=True)
class LevelResult:
    frequency_mhz: float
    set_level_dbm: float
    measured_level_dbm: Optional[float]
    error_db: Optional[float]
    tolerance_db: float
    status: str
    comment: str


@dataclass(frozen=True)
class NoiseResult:
    frequency_mhz: float
    band_low_khz: float
    band_high_khz: float
    noise_value: Optional[float]
    tolerance: Optional[float]
    unit: str
    status: str
    comment: str


@dataclass(frozen=True)
class TransitionResult:
    """
    Результат измерения перехода АМ↔ЧМ (Тест 6).
      direction: 'AM→FM' или 'FM→AM'
      value_plus:  +значение (пик+)
      value_minus: -значение (пик−)
      coefficient: вычисленный коэффициент перехода
      tolerance: допуск
      unit: 'Гц' или '%'
      status: 'ok' | 'warn' | 'fail' | 'error'
      comment: emoji / текст
    """
    direction: str
    value_plus: Optional[float]
    value_minus: Optional[float]
    coefficient: Optional[float]
    tolerance: Optional[float]
    unit: str
    status: str
    comment: str


@dataclass(frozen=True)
class RunSnapshot:
    active_tests: tuple
    results: Dict[str, List[Union[FrequencyResult, LevelResult,
                                  NoiseResult, TransitionResult]]]
    final_status: str
    termination_reason: str
    shutdown_success: object
    shutdown_error: str
    diagnostics: tuple
    summary: dict