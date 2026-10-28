"""
Измерение СКЗ шума в режиме АМ.

Логика из старого скрипта Freq_Level_Noise_.py, блок 'AM noise':
  - Для 0.01 МГц: полоса 0.02–1.5 кГц, допуск 0.01%.
  - Для 0.1 МГц: полоса 0.02–3.4 кГц, допуск 0.01%.
  - Для остальных частот:
      1. Полоса 0.3–3.4 кГц, допуск 0.008%.
      2. Затем для верхних срезов [3.4, 20, 60, 200] кГц:
         полосы 0.02–3.4 / 0.02–20 / 0.02–60 / 0.02–200,
         допуски 0.01 / 0.03 / 0.05 / 0.1%.
"""

from stand_verification.config import (
    NOISE_SETTLE_DELAY,
    AM_BAND_LOW_KHZ, AM_BAND_HIGH_MAIN_KHZ,
    AM_BAND_LOW_KHZ_20, AM_LFILT_LIST_KHZ,
    AM_BAND_001_MHZ_LOW_KHZ, AM_BAND_001_MHZ_HIGH_KHZ,
    AM_BAND_01_MHZ_LOW_KHZ, AM_BAND_01_MHZ_HIGH_KHZ,
    AM_TOL_BAND_03_34, NOISE_SETTLE_DELAY_EXTENDED,
)
from stand_verification.models import NoiseResult
from stand_verification.measurement.tolerances import (
    am_noise_tolerance, evaluate, require_finite,
)


def _set_hp(sk3, low_khz):
    """Правильная установка ФВЧ по значению полосы в кГц."""
    if low_khz <= 0.02:
        sk3.set_filter_hp_hz(20)          # 20 Гц: 'HPAS 20'
    elif low_khz <= 0.3:
        sk3.set_filter_hp_khz(low_khz)    # 0.3 кГц: 'HPAS 0.3kHz'
    else:
        sk3.set_filter_hp_hz(low_khz * 1000)


def measure_am_noise(gen, sk3, stop_event, log, freq_mhz,
                     confirm_callback=None):
    """
    Измерение АМ шума на одной частоте.
    Возвращает список NoiseResult (1 или 5 точек).
    """
    results = []
    f_val = float(freq_mhz)

    # --- Режим AM ---
    if stop_event.is_set():
        return results
    sk3.set_mode_am()
    if stop_event.wait(2.0):
        return results

    def _measure_band(low_khz, high_khz, label):
        """Измерить одну полосу, вернуть NoiseResult или None."""
        try:
            _set_hp(sk3, low_khz)
            if stop_event.wait(1.0):
                return None

                        # Задержка: 20 сек для полос 0.3-3.4 и 0.02-3.4, иначе 15
            if high_khz in (1.5, 3.4):
                wait_s = NOISE_SETTLE_DELAY_EXTENDED
            else:
                wait_s = NOISE_SETTLE_DELAY
            
            sk3.set_filter_lp_khz(high_khz)
            if stop_event.wait(wait_s):
                return None

            value = sk3.read_rms()
            require_finite(value, 'СКЗ АМ шума')
            tolerance = am_noise_tolerance(high_khz)
            status, emoji = evaluate(value, tolerance)

            log(f"   am    : полоса {label} кГц, шум {value:.3f} %, "
                f"допуск ±{tolerance:.3f} % → {emoji}")

            row = NoiseResult(
                frequency_mhz=f_val,
                band_low_khz=low_khz,
                band_high_khz=high_khz,
                noise_value=round(value, 3),
                tolerance=tolerance,
                unit='%',
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
                        tolerance_value=tolerance,
                        stage='am_noise',
                    )
                except Exception:
                    decision = True
                if decision is False:
                    return NoiseResult(
                        frequency_mhz=f_val,
                        band_low_khz=low_khz,
                        band_high_khz=high_khz,
                        noise_value=round(value, 3),
                        tolerance=tolerance,
                        unit='%',
                        status='fail',
                        comment=emoji + ' (остановлено оператором)',
                    )
            return row

        except Exception as e:
            log(f"   ❌ Ошибка АМ шума (полоса {label}): {e}")
            return NoiseResult(
                frequency_mhz=f_val,
                band_low_khz=low_khz,
                band_high_khz=high_khz,
                noise_value=None, tolerance=None, unit='%',
                status='error', comment=str(e),
            )

    # --- Особые случаи ---
    if f_val == 0.01:
        row = _measure_band(AM_BAND_001_MHZ_LOW_KHZ,
                            AM_BAND_001_MHZ_HIGH_KHZ,
                            f'{AM_BAND_001_MHZ_LOW_KHZ:g}-{AM_BAND_001_MHZ_HIGH_KHZ:g}')
        if row:
            results.append(row)
        return results

    if f_val == 0.1:
        row = _measure_band(AM_BAND_01_MHZ_LOW_KHZ,
                            AM_BAND_01_MHZ_HIGH_KHZ,
                            f'{AM_BAND_01_MHZ_LOW_KHZ:g}-{AM_BAND_01_MHZ_HIGH_KHZ:g}')
        if row:
            results.append(row)
        return results

    # --- Стандартный случай: 0.3–3.4, потом 0.02–3.4/20/60/200 ---
    try:
        # 1) Полоса 0.3–3.4
        sk3.set_filter_hp_khz(AM_BAND_LOW_KHZ)
        if stop_event.wait(1.0):
            return results
        sk3.set_filter_lp_khz(AM_BAND_HIGH_MAIN_KHZ)  # 3.4
        if stop_event.wait(NOISE_SETTLE_DELAY_EXTENDED):
            return results

        value = sk3.read_rms()
        require_finite(value, 'СКЗ АМ шума')
        tolerance = AM_TOL_BAND_03_34
        status, emoji = evaluate(value, tolerance)
        log(f"   am    : полоса 0.3-3.4 кГц, шум {value:.3f} %, "
            f"допуск ±{tolerance:.3f} % → {emoji}")

        row = NoiseResult(f_val, AM_BAND_LOW_KHZ, AM_BAND_HIGH_MAIN_KHZ,
                          round(value, 3), tolerance, '%', status, emoji)

        if status == 'fail' and confirm_callback is not None:
            try:
                if confirm_callback(f_val, None, round(value, 3), tolerance,
                                    'am_noise') is False:
                    row = NoiseResult(f_val, AM_BAND_LOW_KHZ,
                                      AM_BAND_HIGH_MAIN_KHZ,
                                      round(value, 3), tolerance, '%', 'fail',
                                      emoji + ' (остановлено оператором)')
            except Exception:
                pass
        results.append(row)

    except Exception as e:
        log(f"   ❌ Ошибка АМ шума (0.3-3.4): {e}")
        results.append(NoiseResult(f_val, AM_BAND_LOW_KHZ,
                                   AM_BAND_HIGH_MAIN_KHZ,
                                   None, None, '%', 'error', str(e)))
        return results

    # 2) Полосы 0.02–3.4 / 0.02–20 / 0.02–60 / 0.02–200
    for high_khz in AM_LFILT_LIST_KHZ:
        if stop_event.is_set():
            break
        row = _measure_band(AM_BAND_LOW_KHZ_20, high_khz,
                            f'{AM_BAND_LOW_KHZ_20:g}-{high_khz:g}')
        if row:
            results.append(row)
            if row.status == 'fail' and 'остановлено' in (row.comment or ''):
                break

    return results