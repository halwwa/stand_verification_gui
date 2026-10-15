"""
Тест 10: Погрешность измерения пиковых значений девиации ЧМ.

Логика из скрипта AM_FM_PM_.py (блок «FM погрешность»):

  1. Генератор: 20 МГц, 0 dBm, ЧМ, 1 кГц, девиация 100 кГц.
  2. СК3-50: CONF:MODE FM, CONF:RANG:FM AUTO, CAL:CURR? (калибровка 20 сек).
  3. Ожидание ответа '0' (успех калибровки). Если не пришёл за 3 попытки — тест стоп.
  4. Цикл по Fm ∈ [20, 60, 90, 1000, 20000, 30000, 60000]:
       - свои девиации (см. DEV_DEVIATION_MAP_HZ);
       - фильтр СК3-50 по Fm;
       - для каждой девиации:
           * установить FM:DEV;
           * PEAK? с POL POS → измеренная девиация +;
           * PEAK? с POL NEG → измеренная девиация −;
           * погрешности delta_plus = peak_plus − set, delta_minus = peak_minus − set;
           * max_dev = max(|delta_plus|, |delta_minus|);
           * допуск tolerdFm = AN × set + 3 × delnoise;
           * сравнить max_dev с допуском.
  5. Все числа делятся на 1000 — в кГц (как в Excel-листе скрипта).
"""

from stand_verification.config import (
    DEV_CARRIER_MHZ, DEV_POWER_DBM,
    DEV_START_MOD_FREQ_HZ, DEV_START_DEVIATION_HZ,
    DEV_FM_LIST_HZ, DEV_DEVIATION_MAP_HZ, DEV_FILTER_MAP_KHZ,
    DEV_DELNOISE_MAP_HZ, DEV_AN_MAP,
    DEV_WAIT_AFTER_SET_FREQ_S, DEV_WAIT_AFTER_SET_DEV_S,
    DEV_WAIT_BEFORE_PEAK_S, DEV_WAIT_AFTER_PEAK_POS_S,
    DEV_WAIT_BEFORE_PEAK_NEG_S, DEV_WAIT_AFTER_PEAK_NEG_S,
    DEV_CALIBRATION_WAIT_S, DEV_CALIBRATION_ATTEMPTS,
    DEV_CALIBRATION_ATTEMPT_WAIT_S,
)
from stand_verification.models import DeviationResult
from stand_verification.measurement.tolerances import evaluate, require_finite


def run_fm_deviation(gen, sk3, stop_event, log, confirm_callback=None):
    """
    Прогон Теста 10.
    :return: список DeviationResult (28 строк).
    """
    results = []

    log("─── Тест 10: Погрешность измерения пиковых значений девиации (ЧМ) ───")

    # --- 1. Настройка генератора ---
    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(DEV_CARRIER_MHZ)
        stop_event.wait(1.0)
        gen.set_power_dbm(DEV_POWER_DBM)
        stop_event.wait(1.0)
        gen.set_fm_on()
        stop_event.wait(1.0)
        gen.set_fm_source_int()
        stop_event.wait(1.0)
        gen.set_lfo_freq_hz(DEV_START_MOD_FREQ_HZ)
        stop_event.wait(1.0)
        gen.set_fm_deviation_hz(DEV_START_DEVIATION_HZ)
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки генератора: {e}")
        return results

    # --- 2. Настройка СК3-50 ---
    try:
        sk3.set_mode_fm()
        stop_event.wait(5.0)
        sk3.set_range_fm_auto()
        stop_event.wait(5.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки СК3-50: {e}")
        return results

    # --- 3. Калибровка СК3-50 ---
    log("   Калибровка СК3-50 (CAL:CURR?)…")
    try:
        calibrated = sk3.cal_current(
            timeout_s=DEV_CALIBRATION_WAIT_S,
            attempts=DEV_CALIBRATION_ATTEMPTS,
            attempt_wait_s=DEV_CALIBRATION_ATTEMPT_WAIT_S,
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
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка включения выхода: {e}")
        return results

    # --- 4. Цикл по Fm ---
    try:
        for fm_hz in DEV_FM_LIST_HZ:
            if stop_event.is_set():
                break

            lp_khz = DEV_FILTER_MAP_KHZ.get(fm_hz, 200.0)
            delnoise = DEV_DELNOISE_MAP_HZ.get(fm_hz, 44.0)
            an = DEV_AN_MAP.get(fm_hz, 0.01)

            log(f"─── Fm = {fm_hz} Гц (фильтр 0.02-{lp_khz:g} кГц) ───")

            # Установка Fm
            try:
                gen.set_lfo_freq_hz(fm_hz)
            except Exception as e:
                log(f"   ❌ Ошибка установки Fm: {e}")
                break
            stop_event.wait(DEV_WAIT_AFTER_SET_FREQ_S)

            # Фильтр СК3-50: HPAS 0.02 кГц (20 Гц) + LPAS по Fm
            try:
                sk3.set_filter_hp_hz(20)
                stop_event.wait(1.0)
                sk3.set_filter_lp_khz(lp_khz)
                stop_event.wait(1.0)
            except Exception as e:
                log(f"   ❌ Ошибка установки фильтра: {e}")

            dev_list = DEV_DEVIATION_MAP_HZ.get(fm_hz, [1000000, 500000, 100000])

            for dev_hz in dev_list:
                if stop_event.is_set():
                    break

                # Допуск
                tolerance = an * dev_hz + 3 * delnoise
                require_finite(tolerance, 'Допуск')

                # Установка девиации
                try:
                    gen.set_fm_deviation_hz(dev_hz)
                except Exception as e:
                    log(f"   ❌ Ошибка установки девиации: {e}")
                    continue
                stop_event.wait(DEV_WAIT_AFTER_SET_DEV_S)

                # --- PEAK + ---
                peak_plus = None
                delta_plus = None
                try:
                    sk3.set_polarity_pos()
                    stop_event.wait(DEV_WAIT_BEFORE_PEAK_S)
                    peak_plus = round(sk3.read_peak(), 1)
                    delta_plus = peak_plus - dev_hz
                    log(f"      +F: {peak_plus} Гц, Δ+ = {delta_plus:+.1f}")
                except Exception as e:
                    log(f"   ❌ Ошибка PEAK+ : {e}")

                stop_event.wait(DEV_WAIT_AFTER_PEAK_POS_S)

                # --- PEAK − ---
                peak_minus = None
                delta_minus = None
                try:
                    sk3.set_polarity_neg()
                    stop_event.wait(DEV_WAIT_BEFORE_PEAK_NEG_S)
                    peak_minus = round(sk3.read_peak(), 1)
                    delta_minus = peak_minus - dev_hz
                    log(f"      −F: {peak_minus} Гц, Δ− = {delta_minus:+.1f}")
                except Exception as e:
                    log(f"   ❌ Ошибка PEAK− : {e}")

                stop_event.wait(DEV_WAIT_AFTER_PEAK_NEG_S)

                # --- Оценка ---
                if delta_plus is None or delta_minus is None:
                    status, emoji = 'error', '⚪ нет данных'
                else:
                    max_dev = max(abs(delta_plus), abs(delta_minus))
                    status, emoji = evaluate(max_dev, tolerance)
                    log(f"      Допуск: ±{tolerance:.1f} Гц, "
                        f"max|Δ| = {max_dev:.1f} Гц → {emoji}")

                # Перевод в кГц (как в Excel-листе скрипта)
                row = DeviationResult(
                    mod_freq_khz=round(fm_hz / 1000.0, 3),
                    set_deviation_khz=round(dev_hz / 1000.0, 3),
                    peak_plus_khz=round(peak_plus / 1000.0, 3) if peak_plus is not None else None,
                    peak_minus_khz=round(peak_minus / 1000.0, 3) if peak_minus is not None else None,
                    delta_plus_khz=round(delta_plus / 1000.0, 3) if delta_plus is not None else None,
                    delta_minus_khz=round(delta_minus / 1000.0, 3) if delta_minus is not None else None,
                    tolerance_khz=round(tolerance / 1000.0, 3),
                    band_str=f'0.02-{lp_khz:g}',
                    status=status,
                    comment=emoji,
                )

                # --- Диалог при fail ---
                if status == 'fail' and confirm_callback is not None:
                    try:
                        decision = confirm_callback(
                            freq_mhz=DEV_CARRIER_MHZ,
                            level_dbm=None,
                            error_value=round(max_dev / 1000.0, 3),
                            tolerance_value=round(tolerance / 1000.0, 3),
                            stage='fm_deviation',
                        )
                    except Exception:
                        decision = True
                    if decision is False:
                        row = DeviationResult(
                            mod_freq_khz=row.mod_freq_khz,
                            set_deviation_khz=row.set_deviation_khz,
                            peak_plus_khz=row.peak_plus_khz,
                            peak_minus_khz=row.peak_minus_khz,
                            delta_plus_khz=row.delta_plus_khz,
                            delta_minus_khz=row.delta_minus_khz,
                            tolerance_khz=row.tolerance_khz,
                            band_str=row.band_str,
                            status='fail',
                            comment=emoji + ' (остановлено оператором)',
                        )
                        results.append(row)
                        return results

                results.append(row)

    except Exception as e:
        log(f"   ❌ Неожиданная ошибка Теста 10: {e}")

    # --- 5. Отключение ---
    try:
        gen.output_off()
        sk3.set_range_fm_auto()
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ⚠ Ошибка выключения: {e}")

    return results