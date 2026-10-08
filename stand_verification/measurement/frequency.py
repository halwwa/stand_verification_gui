from stand_verification.config import SETTLE_DELAY
from stand_verification.measurement.tolerances import (
    FREQ_TOLERANCE_FORMULA, evaluate, require_finite,
)
from stand_verification.models import FrequencyResult


def measure_frequency(gen, sk3, stop_event, log, freq_mhz,
                      confirm_callback=None) -> FrequencyResult:
    """
    Измерение частоты.

    confirm_callback: если задан и результат 'fail' (красный) — вызывается
        confirm_callback(freq_mhz, level_dbm, error_value, tolerance_value, stage)
        где для частоты level_dbm=None, а error_value/tolerance_value в Гц.
        Возвращает True (продолжить) / False (остановить).

    Жёлтый (warn) — НЕ спрашивает, идём дальше молча.
    """
    if stop_event.wait(SETTLE_DELAY):
        return FrequencyResult(
            reference_frequency_hz=float(freq_mhz) * 1_000_000,
            measured_frequency_hz=None, error_hz=None, tolerance_hz=None,
            if_frequency_khz=None, status='error',
            comment='Остановка запрошена во время выдержки',
        )
    try:
        inpf1 = gen.read_frequency_hz()
        require_finite(inpf1, 'Частота генератора')
        fiz = sk3.read_frequency_hz()
        require_finite(fiz, 'Измеренная частота')
        kf = fiz - inpf1
        tolerance = FREQ_TOLERANCE_FORMULA(inpf1)
        fph = sk3.read_if_khz()
        require_finite(fph, 'Частота ПЧ')
        status, emoji = evaluate(kf, tolerance)
        log(f"   freq : {kf:+.2f} Гц, допуск ±{tolerance:.2f} Гц → {emoji}")

        # --- Диалог ТОЛЬКО при fail (красный). Жёлтый не трогаем. ---
        if status == 'fail' and confirm_callback is not None:
            try:
                decision = confirm_callback(
                    freq_mhz=float(freq_mhz),
                    level_dbm=None,
                    error_value=round(kf, 2),
                    tolerance_value=round(tolerance, 2),
                    stage='freq',
                )
            except Exception:
                # Если callback сломался — не валим тест, продолжаем.
                decision = True
            if decision is False:
                return FrequencyResult(
                    reference_frequency_hz=inpf1, measured_frequency_hz=fiz,
                    error_hz=round(kf, 2), tolerance_hz=round(tolerance, 2),
                    if_frequency_khz=round(fph, 2), status='fail',
                    comment=emoji + ' (остановлено оператором)',
                )

        return FrequencyResult(
            reference_frequency_hz=inpf1, measured_frequency_hz=fiz,
            error_hz=round(kf, 2), tolerance_hz=round(tolerance, 2),
            if_frequency_khz=round(fph, 2), status=status, comment=emoji,
        )
    except Exception as e:
        return FrequencyResult(
            reference_frequency_hz=float(freq_mhz) * 1_000_000,
            measured_frequency_hz=None, error_hz=None, tolerance_hz=None,
            if_frequency_khz=None, status='error', comment=str(e),
        )