"""
Тест 12: Погрешность измерения пиковых значений индекса ФМ.

Логика из скрипта AM_FM_PM_.py (блок «PM»):

  1. Генератор: 20 МГц, 0 dBm, ЧМ (FM:STAT ON), 1 кГц, девиация 100 кГц.
  2. СК3-50: MODE PM, CAL:CURR? (калибровка 20 сек).
  3. Ожидание '0'. Если не пришёл — тест останавливается (RuntimeError).
  4. Цикл по Fm ∈ [300, 6000, 60000]:
       - свои Dpm_k (множители):
           300   → [100, 10, 1]
           6000  → [100, 10, 1]
           60000 → [10, 1]
       - фильтр СК3-50 по Fm.
       - delnoise по Fm (0.003*0.02 + смещение).
       - для каждого Dpm_k:
           * девиация = Dpm_k × Fm (Гц).
           * установить FM:DEV.
           * PEAK+ / PEAK− → Pmp / Pmm.
           * Δ+ = Pmp − Dpm_k, Δ− = Pmm − Dpm_k.
           * допуск = 0.02 × Dpm_k + 3 × delnoise.
           * max(|Δ+|, |Δ−|) сравнить с допуском.
  5. Всего 8 точек: 3 + 3 + 2.
"""

from stand_verification.config import (
    PM_PEAKS_START_CARRIER_MHZ, PM_PEAKS_START_POWER_DBM,
    PM_PEAKS_START_MOD_FREQ_HZ, PM_PEAKS_START_DEVIATION_HZ,
    PM_PEAKS_FM_LIST_HZ, PM_PEAKS_DPM_LIST_DEFAULT, PM_PEAKS_DPM_LIST_60K,
    PM_PEAKS_FILTER_MAP_KHZ, PM_PEAKS_DELNOISE_MAP_RAD,
    PM_PEAKS_WAIT_AFTER_SET_CARRIER_S, PM_PEAKS_WAIT_AFTER_SET_MOD_FREQ_S,
    PM_PEAKS_WAIT_AFTER_SET_DEV_S, PM_PEAKS_WAIT_BEFORE_PEAK_S,
    PM_PEAKS_WAIT_AFTER_PEAK_POS_S, PM_PEAKS_WAIT_BEFORE_PEAK_NEG_S,
    PM_PEAKS_WAIT_AFTER_PEAK_NEG_S, PM_PEAKS_CALIBRATION_WAIT_S,
    PM_PEAKS_CALIBRATION_ATTEMPTS, PM_PEAKS_CALIBRATION_ATTEMPT_WAIT_S,
)
from stand_verification.models import PmResult
from stand_verification.measurement.tolerances import evaluate, require_finite


def run_pm_peaks(gen, sk3, stop_event, log, confirm_callback=None):
    """
    Прогон Теста 12.
    :return: список PmResult (8 строк).
    """
    results = []

    log("─── Тест 12: Погрешность пиковых значений индекса ФМ ───")

    # --- 1. Настройка генератора ---
    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(PM_PEAKS_START_CARRIER_MHZ)
        stop_event.wait(PM_PEAKS_WAIT_AFTER_SET_CARRIER_S)
        gen.set_power_dbm(PM_PEAKS_START_POWER_DBM)
        stop_event.wait(1.0)
        gen.set_fm_on()
        stop_event.wait(1.0)
        gen.set_fm_source_int()
        stop_event.wait(1.0)
        gen.set_lfo_freq_hz(PM_PEAKS_START_MOD_FREQ_HZ)
        stop_event.wait(PM_PEAKS_WAIT_AFTER_SET_MOD_FREQ_S)
        gen.set_fm_deviation_hz(PM_PEAKS_START_DEVIATION_HZ)
        stop_event.wait(PM_PEAKS_WAIT_AFTER_SET_DEV_S)
    except Exception as e:
        log(f"   ❌ Ошибка настройки генератора: {e}")
        return results

    # --- 2. Настройка СК3-50 ---
    try:
        sk3.set_mode_pm()
        stop_event.wait(5.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки СК3-50: {e}")
        return results

    # --- 3. Калибровка СК3-50 ---
    log("   Калибровка СК3-50 (CAL:CURR?)…")
    try:
        calibrated = sk3.cal_current(
            timeout_s=PM_PEAKS_CALIBRATION_WAIT_S,
            attempts=PM_PEAKS_CALIBRATION_ATTEMPTS,
            attempt_wait_s=PM_PEAKS_CALIBRATION_ATTEMPT_WAIT_S,
        )
    except Exception as e:
        log(f"   ❌ Ошибка калибровки: {e}")
        return results

    if not calibrated:
        log("   ❌ Калибровка не удалась — тест остановлен.")
        raise RuntimeError("Калибровка СК3-50 (CAL:CURR?) не удалась")

    log("   ✅ Калибровка успешна (получен '0').")

    # Включаем выход генератора
    try:
        gen.output_on()
        stop_event.wait(5.0)
    except Exception as e:
        log(f"   ❌ Ошибка включения выхода: {e}")
        return results

    # --- 4. Цикл по Fm ---
    try:
        for fm_hz in PM_PEAKS_FM_LIST_HZ:
            if stop_event.is_set():
                break

            lp_khz = PM_PEAKS_FILTER_MAP_KHZ.get(fm_hz, 200.0)
            delnoise = PM_PEAKS_DELNOISE_MAP_RAD.get(fm_hz, 0.005)

            log(f"─── Fm = {fm_hz} Гц (фильтр 0.3-{lp_khz:g} кГц) ───")

            # Установка Fm
            try:
                gen.set_lfo_freq_hz(fm_hz)
            except Exception as e:
                log(f"   ❌ Ошибка Fm: {e}")
                continue
            stop_event.wait(PM_PEAKS_WAIT_AFTER_SET_MOD_FREQ_S)

            # Фильтр СК3-50: HPAS 0.3 кГц, LPAS по Fm
            try:
                sk3.set_filter_hp_khz(0.3)
                stop_event.wait(1.0)
                sk3.set_filter_lp_khz(lp_khz)
                stop_event.wait(1.0)
            except Exception as e:
                log(f"   ❌ Ошибка фильтра: {e}")

            # Список Dpm_k
            if fm_hz == 60000:
                dpm_list = PM_PEAKS_DPM_LIST_60K
            else:
                dpm_list = PM_PEAKS_DPM_LIST_DEFAULT

            for dpm_k in dpm_list:
                if stop_event.is_set():
                    break

                # Девиация = Dpm_k × Fm
                deviation_hz = int(dpm_k) * fm_hz
                tolerance = 0.02 * dpm_k + 3 * delnoise
                require_finite(tolerance, 'Допуск')

                # Установка девиации
                try:
                    gen.set_fm_deviation_hz(deviation_hz)
                except Exception as e:
                    log(f"   ❌ Ошибка девиации: {e}")
                    continue
                stop_event.wait(PM_PEAKS_WAIT_AFTER_SET_DEV_S)

                # --- PEAK + ---
                peak_plus = None
                delta_plus = None
                try:
                    sk3.set_polarity_pos()
                    stop_event.wait(PM_PEAKS_WAIT_BEFORE_PEAK_S)
                    peak_plus = round(sk3.read_peak(), 3)
                    delta_plus = peak_plus - dpm_k
                    log(f"      +P: {peak_plus} рад, Δ+ = {delta_plus:+.3f}")
                except Exception as e:
                    log(f"   ❌ Ошибка PEAK+ : {e}")

                stop_event.wait(PM_PEAKS_WAIT_AFTER_PEAK_POS_S)

                # --- PEAK − ---
                peak_minus = None
                delta_minus = None
                try:
                    sk3.set_polarity_neg()
                    stop_event.wait(PM_PEAKS_WAIT_BEFORE_PEAK_NEG_S)
                    peak_minus = round(sk3.read_peak(), 3)
                    delta_minus = peak_minus - dpm_k
                    log(f"      −P: {peak_minus} рад, Δ− = {delta_minus:+.3f}")
                except Exception as e:
                    log(f"   ❌ Ошибка PEAK− : {e}")

                stop_event.wait(PM_PEAKS_WAIT_AFTER_PEAK_NEG_S)

                # --- Оценка ---
                if delta_plus is None or delta_minus is None:
                    status, emoji = 'error', '⚪ нет данных'
                else:
                    max_dev = max(abs(delta_plus), abs(delta_minus))
                    status, emoji = evaluate(max_dev, tolerance)
                    log(f"      Допуск: ±{tolerance:.3f} рад, "
                        f"max|Δ| = {max_dev:.3f} рад → {emoji}")

                row = PmResult(
                    mod_freq_hz=float(fm_hz),
                    set_index=float(dpm_k),
                    peak_plus_rad=peak_plus,
                    peak_minus_rad=peak_minus,
                    delta_plus_rad=round(delta_plus, 3) if delta_plus is not None else None,
                    delta_minus_rad=round(delta_minus, 3) if delta_minus is not None else None,
                    tolerance_rad=round(tolerance, 3),
                    band_str=f'0.3-{lp_khz:g}',
                    status=status,
                    comment=emoji,
                )

                # --- Диалог ---
                if status == 'fail' and confirm_callback is not None:
                    try:
                        decision = confirm_callback(
                            freq_mhz=PM_PEAKS_START_CARRIER_MHZ,
                            level_dbm=None,
                            error_value=round(max_dev, 3),
                            tolerance_value=round(tolerance, 3),
                            stage='pm_peaks',
                        )
                    except Exception:
                        decision = True
                    if decision is False:
                        row = PmResult(
                            mod_freq_hz=row.mod_freq_hz,
                            set_index=row.set_index,
                            peak_plus_rad=row.peak_plus_rad,
                            peak_minus_rad=row.peak_minus_rad,
                            delta_plus_rad=row.delta_plus_rad,
                            delta_minus_rad=row.delta_minus_rad,
                            tolerance_rad=row.tolerance_rad,
                            band_str=row.band_str,
                            status='fail',
                            comment=emoji + ' (остановлено оператором)',
                        )
                        results.append(row)
                        return results

                results.append(row)

    except Exception as e:
        log(f"   ❌ Неожиданная ошибка Теста 12: {e}")

    # --- 5. Сброс ---
    try:
        gen.output_off()
        gen.reset()
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ⚠ Ошибка выключения: {e}")

    return results