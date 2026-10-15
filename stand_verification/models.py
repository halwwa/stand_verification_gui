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
    direction: str
    value_plus: Optional[float]
    value_minus: Optional[float]
    coefficient: Optional[float]
    tolerance: Optional[float]
    unit: str
    status: str
    comment: str


@dataclass(frozen=True)
class ThdAmResult:
    mod_freq_hz: float
    set_depth: float
    meas_depth: Optional[float]
    thd_sk3: Optional[float]
    thd_c6: Optional[float]
    tolerance: Optional[float]
    mod_freq_c6: str
    band_str: str
    status: str
    comment: str


@dataclass(frozen=True)
class ThdFmResult:
    mod_freq_hz: float
    set_deviation_hz: float
    meas_deviation_hz: Optional[float]
    thd_sk3: Optional[float]
    thd_c6: Optional[float]
    tolerance: Optional[float]
    mod_freq_c6: str
    band_str: str
    status: str
    comment: str


@dataclass(frozen=True)
class DeviationResult:
    """
    Результат Теста 10 (погрешность измерения пиковых значений девиации ЧМ).
    Все значения — в кГц (как в скрипте папы, где числа делятся на 1000).
      mod_freq_khz:        Fm в кГц
      set_deviation_khz:   заданная девиация
      peak_plus_khz:       измеренная девиация +
      peak_minus_khz:      измеренная девиация −
      delta_plus_khz:      погрешность +
      delta_minus_khz:     погрешность −
      tolerance_khz:       допуск
      band_str:            полоса фильтра (например '0.02-20')
    """
    mod_freq_khz: float
    set_deviation_khz: float
    peak_plus_khz: Optional[float]
    peak_minus_khz: Optional[float]
    delta_plus_khz: Optional[float]
    delta_minus_khz: Optional[float]
    tolerance_khz: Optional[float]
    band_str: str
    status: str
    comment: str


@dataclass(frozen=True)
class RunSnapshot:
    active_tests: tuple
    results: Dict[str, List[Union[
        FrequencyResult, LevelResult, NoiseResult,
        TransitionResult, ThdAmResult, ThdFmResult, DeviationResult]]]
    final_status: str
    termination_reason: str
    shutdown_success: object
    shutdown_error: str
    diagnostics: tuple
    summary: dict