from stand_verification.config import SETTLE_DELAY
from stand_verification.models import LevelResult
from stand_verification.measurement.tolerances import (
    LEVEL_TOLERANCE_DB, LEVEL_TOLERANCE_HIGH_DB, evaluate, require_finite,
)


def measure_level(gen, sk3, stop_event, log, freq_mhz, level_dbm,
                  confirm_callback=None) -> LevelResult:
    """
    Измерение уровня.

    confirm_callback: если задан и результат 'fail' — вызывается
        confirm_callback(freq_mhz, level_dbm, error_value, tolerance_value, stage)
        Возвращает True (продолжить) / False (остановить).

    Жёлтый (warn) — НЕ спрашивает, идём дальше молча.
    """
    tolerance = LEVEL_TOLERANCE_HIGH_DB if float(freq_mhz) >= 2000 else LEVEL_TOLERANCE_DB

    # --- Установка уровня ---
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

    # --- Выдержка ---
    if stop_event.wait(SETTLE_DELAY):
        return LevelResult(
            frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
            measured_level_dbm=None, error_db=None, tolerance_db=tolerance,
            status='error', comment='Остановка запрошена во время выдержки',
        )

    # --- Измерение ---
    try:
        oup = sk3.read_power_dbm()
        require_finite(oup, 'Измеренный уровень')
        ku = oup - level_dbm
        status, emoji = evaluate(ku, tolerance)

        # Лог с указанием заданного уровня
        log(f"   level ({level_dbm:+.0f} dBm): {ku:+.2f} дБ, "
            f"допуск ±{tolerance:.2f} дБ → {emoji}")

        # --- Диалог ТОЛЬКО при fail. ---
        if status == 'fail' and confirm_callback is not None:
            try:
                decision = confirm_callback(
                    freq_mhz=float(freq_mhz),
                    level_dbm=level_dbm,
                    error_value=round(ku, 2),
                    tolerance_value=tolerance,
                    stage='level',
                )
            except Exception:
                decision = True
            if decision is False:
                return LevelResult(
                    frequency_mhz=float(freq_mhz), set_level_dbm=level_dbm,
                    measured_level_dbm=round(oup, 2), error_db=round(ku, 2),
                    tolerance_db=tolerance, status='fail',
                    comment=emoji + ' (остановлено оператором)',
                )

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