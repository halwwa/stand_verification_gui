"""
Измерение СКЗ шума в режиме ЧМ (FM).

Логика из старого скрипта Freq_Level_Noise_.py, блок 'FM noise':
  - Измеряется ТОЛЬКО на частотах, которые НЕ 0.01, 0.1, 100, 1500, 2500.
  - Полоса 0.3–3.4 кГц — всегда.
  - Полоса 0.02–1.5 кГц — только для 1 МГц.
  - Для остальных частот: полосы 0.02–3.4 / 0.02–20 / 0.02–60 / 0.02–200.
  - Допуски зависят от частоты несущей и полосы.
"""

from stand_verification.config import (
    NOISE_SETTLE_DELAY, FM_LFILT_LIST_KHZ, SKIP_FOR_FM_PM_MHZ,
)
from stand_verification.models import NoiseResult
from stand_verification.measurement.tolerances import (
    fm_noise_tolerance, evaluate, require_finite,
)


def measure_fm_noise(gen, sk3, stop_event, log, freq_mhz,
                     confirm_callback=None):
    """
    Измерение ЧМ шума на одной частоте.
    Возвращает список NoiseResult (5 или 6 точек).
    """
    results = []
    f_val = float(freq_mhz)

    # --- Проверка: не пропущена ли частота ---
    if f_val in SKIP_FOR_FM_PM_MHZ:
        return results

    # --- Режим FM ---
    if stop_event.is_set():
        return results
    sk3.set_mode_fm()
    if stop_event.wait(2.0):
        return results

    def _measure_band(high_khz, label):
        """Измерить одну полосу, вернуть NoiseResult или None."""
        try:
            sk3.set_filter_lp_khz(high_khz)
            if stop_event.wait(NOISE_SETTLE_DELAY):
                return None

            value = sk3.read_rms()
            require_finite(value, 'СКЗ ЧМ шума')
            tolerance = fm_noise_tolerance(f_val, high_khz)
            status, emoji = evaluate(value, tolerance)

            log(f"   fm    : полоса {label} кГц, шум {value:.1f} Гц, "
                f"допуск ±{tolerance:.1f} Гц → {emoji}")

            row = NoiseResult(
                frequency_mhz=f_val,
                band_low_khz=0.3,
                band_high_khz=high_khz,
                noise_value=round(value, 1),
                tolerance=round(tolerance, 1),
                unit='Гц',
                status=status,
                comment=emoji,
            )

            # --- Диалог при fail ---
            if status == 'fail' and confirm_callback is not None:
                try:
                    decision = confirm_callback(
                        freq_mhz=f_val,
                        level_dbm=None,
                        error_value=round(value, 1),
                        tolerance_value=round(tolerance, 1),
                        stage='fm_noise',
                    )
                except Exception:
                    decision = True
                if decision is False:
                    return NoiseResult(
                        frequency_mhz=f_val,
                        band_low_khz=0.3,
                        band_high_khz=high_khz,
                        noise_value=round(value, 1),
                        tolerance=round(tolerance, 1),
                        unit='Гц',
                        status='fail',
                        comment=emoji + ' (остановлено оператором)',
                    )
            return row

        except Exception as e:
            log(f"   ❌ Ошибка ЧМ шума ({label}): {e}")
            return NoiseResult(
                frequency_mhz=f_val,
                band_low_khz=0.3,
                band_high_khz=high_khz,
                noise_value=None, tolerance=None, unit='Гц',
                status='error', comment=str(e),
            )

    # --- 1) Полоса 0.3–3.4 кГц (всегда, кроме пропущенных частот) ---
    try:
        sk3.set_filter_hp_khz(0.3)
        if stop_event.wait(1.0):
            return results
        row = _measure_band(3.4, '0.3-3.4')
        if row:
            results.append(row)
            if row.status == 'fail' and 'остановлено' in (row.comment or ''):
                return results
    except Exception as e:
        log(f"   ❌ Ошибка ЧМ шума (setup): {e}")
        results.append(NoiseResult(f_val, 0.3, 3.4, None, None, 'Гц',
                                   'error', str(e)))
        return results

    # --- 2) Полоса 0.02–1.5 кГц (только для 1 МГц) ---
    if f_val == 1.0:
        try:
            sk3.set_filter_hp_hz(20)
            if stop_event.wait(1.0):
                return results
            sk3.set_filter_lp_khz(1.5)
            if stop_event.wait(NOISE_SETTLE_DELAY):
                return results
            value = sk3.read_rms()
            require_finite(value, 'СКЗ ЧМ шума')
            tolerance = fm_noise_tolerance(f_val, 1.5)
            status, emoji = evaluate(value, tolerance)
            log(f"   fm    : полоса 0.02-1.5 кГц, шум {value:.1f} Гц, "
                f"допуск ±{tolerance:.1f} Гц → {emoji}")
            results.append(NoiseResult(f_val, 0.02, 1.5, round(value, 1),
                                       round(tolerance, 1), 'Гц', status, emoji))
        except Exception as e:
            log(f"   ❌ Ошибка ЧМ шума (0.02-1.5): {e}")
            results.append(NoiseResult(f_val, 0.02, 1.5, None, None, 'Гц',
                                       'error', str(e)))

    # --- 3) Полосы 0.02–3.4 / 0.02–20 / 0.02–60 / 0.02–200 ---
    try:
        sk3.set_filter_hp_hz(20)
        if stop_event.wait(1.0):
            return results
    except Exception as e:
        log(f"   ❌ Ошибка установки HPAS 20: {e}")
        return results

    for high_khz in FM_LFILT_LIST_KHZ:
        if stop_event.is_set():
            break
        row = _measure_band(high_khz, f'0.02-{high_khz:g}')
        if row:
            results.append(row)
            if row.status == 'fail' and 'остановлено' in (row.comment or ''):
                break

    return results