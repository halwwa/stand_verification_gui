from stand_verification.config import SETTLE_DELAY
from stand_verification.models import LevelResult
from stand_verification.measurement.tolerances import (
    LEVEL_TOLERANCE_DB, LEVEL_TOLERANCE_HIGH_DB, evaluate,
)


def measure_level(gen, sk3, stop_event, log, freq_mhz, level_dbm) -> LevelResult:
    tolerance = LEVEL_TOLERANCE_HIGH_DB if float(freq_mhz) >= 2000 else LEVEL_TOLERANCE_DB
    try:
        if stop_event.is_set():
            return LevelResult(
                frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
                measured_level_dbm=None, error_db=None, tolerance_db=tolerance,
                status='error', comment='Остановка запрошена',
            )
        gen.set_power_dbm(level_dbm)
    except Exception as e:
        return LevelResult(
            frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
            measured_level_dbm=None, error_db=None, tolerance_db=tolerance,
            status='error', comment=f"Ошибка установки уровня {level_dbm} dBm: {e}",
        )
    if stop_event.wait(SETTLE_DELAY):
        return LevelResult(
            frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
            measured_level_dbm=None, error_db=None, tolerance_db=tolerance,
            status='error', comment='Остановка запрошена во время выдержки',
        )
    try:
        oup = sk3.read_power_dbm()
        ku = oup - level_dbm
        status, emoji = evaluate(ku, tolerance)
        log(f"   level: {ku:+.2f} дБ, допуск ±{tolerance:.2f} дБ → {emoji}")
        return LevelResult(
            frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
            measured_level_dbm=round(oup, 2), error_db=round(ku, 2),
            tolerance_db=tolerance, status=status, comment=emoji,
        )
    except Exception as e:
        return LevelResult(
            frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
            measured_level_dbm=None, error_db=None, tolerance_db=tolerance,
            status='error', comment=str(e),
        )
