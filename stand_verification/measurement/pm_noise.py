"""
Измерение СКЗ шума в режиме ФМ (PM).

Логика из старого скрипта Freq_Level_Noise_.py, блок 'PM noise':
  - Измеряется только на частотах, которые НЕ 0.01, 0.1, 100, 1500, 2500.
  - ФВЧ всегда 0.3 кГц.
  - Полосы ФНЧ: 0.3–20, 0.3–60, 0.3–200 кГц.
  - Допуски: 0.003×(f/1e9) + 0.003 / +0.004 / +0.005 рад.
"""

from stand_verification.config import (
    NOISE_SETTLE_DELAY, PM_LFILT_LIST_KHZ, SKIP_FOR_FM_PM_MHZ,
)
from stand_verification.models import NoiseResult
from stand_verification.measurement.tolerances import (
    pm_noise_tolerance, evaluate, require_finite,
)


def measure_pm_noise(gen, sk3, stop_event, log, freq_mhz,
                     confirm_callback=None):
    """
    Измерение ФМ шума на одной частоте.
    Возвращает список NoiseResult (3 точки).
    """
    results = []
    f_val = float(freq_mhz)

    if f_val in SKIP_FOR_FM_PM_MHZ:
        return results

    if stop_event.is_set():
        return results
    sk3.set_mode_pm()
    if stop_event.wait(2.0):
        return results

    # --- ФВЧ 0.3 кГц ---
    try:
        sk3.set_filter_hp_khz(0.3)
        if stop_event.wait(1.0):
            return results
    except Exception as e:
        log(f"   ❌ Ошибка ФМ шума (setup): {e}")
        results.append(NoiseResult(f_val, 0.3, 0.0, None, None, 'рад',
                                   'error', str(e)))
        return results

    # --- Полосы 0.3–20 / 0.3–60 / 0.3–200 ---
    for high_khz in PM_LFILT_LIST_KHZ:
        if stop_event.is_set():
            break

        try:
            sk3.set_filter_lp_khz(high_khz)
            if stop_event.wait(NOISE_SETTLE_DELAY):
                break

            value = sk3.read_rms()
            require_finite(value, 'СКЗ ФМ шума')
            tolerance = pm_noise_tolerance(f_val, high_khz)
            status, emoji = evaluate(value, tolerance)

            log(f"   pm    : полоса 0.3-{high_khz:g} кГц, шум {value:.3f} рад, "
                f"допуск ±{tolerance:.3f} рад → {emoji}")

            row = NoiseResult(
                frequency_mhz=f_val,
                band_low_khz=0.3,
                band_high_khz=high_khz,
                noise_value=round(value, 3),
                tolerance=round(tolerance, 3),
                unit='рад',
                status=status,
                comment=emoji,
            )

            # --- Диалог при fail ---
            if status == 'fail' and confirm_callback is not None:
                try:
                    decision = confirm_callback(
                        freq_mhz=f_val,
                        level_dbm=None,
                        error_value=round(value, 3),
                        tolerance_value=round(tolerance, 3),
                        stage='pm_noise',
                    )
                except Exception:
                    decision = True
                if decision is False:
                    row = NoiseResult(
                        frequency_mhz=f_val,
                        band_low_khz=0.3,
                        band_high_khz=high_khz,
                        noise_value=round(value, 3),
                        tolerance=round(tolerance, 3),
                        unit='рад',
                        status='fail',
                        comment=emoji + ' (остановлено оператором)',
                    )

            results.append(row)
            if row.status == 'fail' and 'остановлено' in (row.comment or ''):
                break

        except Exception as e:
            log(f"   ❌ Ошибка ФМ шума (0.3-{high_khz:g}): {e}")
            results.append(NoiseResult(f_val, 0.3, high_khz, None, None,
                                       'рад', 'error', str(e)))
            break

    return results