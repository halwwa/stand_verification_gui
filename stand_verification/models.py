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
    """
    Результат измерения шумов (АМ / ЧМ / ФМ).
    Единица зависит от режима:
      - AM → шум в % (проценты)
      - FM → шум в Гц (герцы)
      - PM → шум в рад (радианы)
    """
    frequency_mhz: float              # частота несущей, МГц
    band_low_khz: float               # нижняя граница полосы фильтра, кГц
    band_high_khz: float              # верхняя граница полосы фильтра, кГц
    noise_value: Optional[float]      # измеренное СКЗ шума
    tolerance: Optional[float]        # допуск в тех же единицах
    unit: str                         # '%' | 'Гц' | 'рад'
    status: str
    comment: str


@dataclass(frozen=True)
class RunSnapshot:
    active_tests: tuple
    results: Dict[str, List[Union[FrequencyResult, LevelResult, NoiseResult]]]
    final_status: str
    termination_reason: str
    shutdown_success: object
    shutdown_error: str
    diagnostics: tuple
    summary: dict