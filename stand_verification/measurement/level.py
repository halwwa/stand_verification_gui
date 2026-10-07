from stand_verification.config import SETTLE_DELAY
from stand_verification.measurement.tolerances import (
    LEVEL_TOLERANCE_DB, LEVEL_TOLERANCE_HIGH_DB, evaluate,
)


def measure_level(gen, sk3, stop_event, log, freq_mhz, level_dbm):
    tolerance = LEVEL_TOLERANCE_HIGH_DB if float(freq_mhz) >= 2000 else LEVEL_TOLERANCE_DB
    try:
        if stop_event.is_set():
            return [float(freq_mhz), level_dbm, None, None, tolerance, 'error', 'Остановка запрошена'], 'error'
        gen.set_power_dbm(level_dbm)
    except Exception as e:
        return [float(freq_mhz), level_dbm, None, None, tolerance, 'error',
                f"Ошибка установки уровня {level_dbm} dBm: {e}"], 'error'
    if stop_event.wait(SETTLE_DELAY):
        return [float(freq_mhz), level_dbm, None, None, tolerance, 'error',
                'Остановка запрошена во время выдержки'], 'error'
    try:
        oup = sk3.read_power_dbm()
        ku = oup - level_dbm
        status, emoji = evaluate(ku, tolerance)
        log(f"   level: {ku:+.2f} дБ, допуск ±{tolerance:.2f} дБ → {emoji}")
        return [float(freq_mhz), level_dbm, round(oup, 2), round(ku, 2), tolerance, status, emoji], status
    except Exception as e:
        return [float(freq_mhz), level_dbm, None, None, tolerance, 'error', str(e)], 'error'
