"""
Тест 8: КГ ЧМ.

Логика из скрипта AM_FM.py (блок «КГ ЧМ»):
  1. Генератор: 20 МГц, 0 dBm, режим ЧМ, 1 кГц, девиация 100 кГц.
  2. СК3-50: MODE FM, CONF:THD ON.
  3. С6-22: MODE DFM, LIMitD AUTO.
  4. Цикл по Fm из [20, 1000, 6000, 20000, 60000, 16650, 9810, 6970] Гц:
     - установить Fm;
     - установить фильтры СК3-50 (HPAS 0.02kHz, LPAS по Fm);
     - выбрать форму модуляции: SIN (по умолчанию) / SQU (для 16650/9810/6970);
     - для каждой девиации из [300000, 500000, 1000000] (или [500000] для SQU):
         * установить FM:DEV;
         * PEAK? (POS) → измеренная девиация;
         * MEASure:THD? С6-22 → КГ_C6;
         * MEASure:FREQuency? С6-22 → частота модуляции;
         * THD? СК3-50 → КГ_СК3;
         * допуск = 0.1 % для 20/1000/6000 Гц, 0.2 % для 20000/60000 Гц;
           для остальных частот = 0.1 × |thd_c6| + 0.03.
  5. По завершении: CONF:THD OFF.
"""

import time

from stand_verification.config import (
    THD_FM_CARRIER_MHZ, THD_FM_POWER_DBM,
    THD_FM_START_MOD_FREQ_HZ, THD_FM_START_DEVIATION_HZ,
    THD_FM_FM_LIST_HZ, THD_FM_DEV_LIST_HZ_STD, THD_FM_DEV_LIST_HZ_SQU,
    THD_FM_FILTER_MAP,
    THD_FM_WAIT_AFTER_FREQ_MAN_S, THD_FM_WAIT_AFTER_SET_DEV_S,
    THD_FM_WAIT_BEFORE_PEAK_S, THD_FM_WAIT_AFTER_PEAK_S,
    THD_FM_WAIT_BEFORE_C6_THD_S, THD_FM_WAIT_AFTER_C6_CMD_S,
    THD_FM_WAIT_BEFORE_SK3_THD_S,
)
from stand_verification.models import ThdFmResult
from stand_verification.measurement.tolerances import evaluate, require_finite


# Особые частоты — там меандр (SQU) и одна девиация
_THD_FM_SQU_FREQS = {16650, 9810, 6970}


def _thd_fm_tolerance(fm_hz, thd_c6):
    """Допуск (%) по частоте модуляции; для меандра сохранена формула."""
    if thd_c6 is None:
        return None
    if fm_hz in (20, 1000, 6000):
        return 0.1
    if fm_hz in (20000, 60000):
        return 0.2
    return 0.1 * abs(thd_c6) + 0.03


def run_thd_fm(gen, sk3, c6, stop_event, log, confirm_callback=None):
    """
    Прогон Теста 8.
    :param c6: сессия С6-22 или None (если не подключён — тест пропущен).
    :return: список ThdFmResult (переменное число, обычно 18).
    """
    results = []

    if c6 is None:
        log("⚠ С6-22 не подключён — Тест 8 (КГ ЧМ) пропущен.")
        return results

    log("─── Тест 8: КГ ЧМ ───")

    # --- 1. Настройка генератора ---
    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(THD_FM_CARRIER_MHZ)
        stop_event.wait(1.0)
        gen.set_power_dbm(THD_FM_POWER_DBM)
        stop_event.wait(1.0)
        gen.set_fm_on()
        stop_event.wait(1.0)
        gen.set_fm_source_int()
        stop_event.wait(1.0)
        gen.set_lfo_freq_hz(THD_FM_START_MOD_FREQ_HZ)
        stop_event.wait(1.0)
        gen.set_fm_deviation_hz(THD_FM_START_DEVIATION_HZ)
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки генератора: {e}")
        return results

    # --- 2. Настройка СК3-50 ---
    try:
        sk3.set_mode_fm()
        stop_event.wait(1.0)
        gen.output_on()
        stop_event.wait(1.0)
        sk3.set_thd_on()
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки СК3-50: {e}")
        return results

    # --- 3. Настройка С6-22 ---
    try:
        c6.set_thd_mode()   # MODE DFM, LIMitD AUTO
    except Exception as e:
        log(f"   ❌ Ошибка настройки С6-22: {e}")

    # --- 4. Цикл по Fm ---
    try:
        for fm_hz in THD_FM_FM_LIST_HZ:
            if stop_event.is_set():
                break

            log(f"─── Fm = {fm_hz} Гц ───")

            # Установка Fm
            try:
                gen.set_lfo_freq_hz(fm_hz)
            except Exception as e:
                log(f"   ❌ Ошибка установки Fm: {e}")
                break
            stop_event.wait(1.0)

            # Полоса фильтра
            lp_khz = THD_FM_FILTER_MAP.get(fm_hz, 200.0)

            # Фильтры СК3-50
            try:
                sk3.set_filter_hp_hz(20)
                stop_event.wait(1.0)
                sk3.set_filter_lp_khz(lp_khz)
                stop_event.wait(1.0)
            except Exception as e:
                log(f"   ❌ Ошибка установки фильтра: {e}")

            # Форма модуляции: SIN по умолчанию, SQU для 16650/9810/6970
            is_square = fm_hz in _THD_FM_SQU_FREQS
            try:
                if is_square:
                    gen.set_lfo_shape_square()
                else:
                    gen.set_lfo_shape_sin()
            except Exception as e:
                log(f"   ⚠ Ошибка установки формы ЛФО: {e}")

            # Список девиаций
            dev_list = THD_FM_DEV_LIST_HZ_SQU if is_square else THD_FM_DEV_LIST_HZ_STD

            # --- Внутренний цикл по девиациям ---
            for dev_hz in dev_list:
                if stop_event.is_set():
                    break

                log(f"   Девиация = {dev_hz} Гц")

                try:
                    gen.set_fm_deviation_hz(dev_hz)
                except Exception as e:
                    log(f"   ❌ Ошибка установки девиации: {e}")
                    continue
                stop_event.wait(THD_FM_WAIT_AFTER_SET_DEV_S)

                # PEAK? POS → измеренная девиация
                meas_dev = None
                try:
                    sk3.set_polarity_pos()
                    stop_event.wait(THD_FM_WAIT_BEFORE_PEAK_S)
                    meas_dev = round(sk3.read_peak(), 2)
                    log(f"      Изм. девиация: {meas_dev}")
                except Exception as e:
                    log(f"   ❌ Ошибка чтения PEAK?: {e}")

                # --- С6-22: THD ---
                thd_c6 = None
                mod_freq_c6 = ""
                try:
                    stop_event.wait(THD_FM_WAIT_BEFORE_C6_THD_S)
                    if stop_event.is_set():
                        break
                    thd_c6 = round(c6.read_thd(), 3)
                    log(f"      КГ (С6-22): {thd_c6} %")
                    stop_event.wait(THD_FM_WAIT_AFTER_C6_CMD_S)

                    mod_freq_c6 = c6.read_mod_frequency()
                    log(f"      Fmod (С6-22): {mod_freq_c6}")
                except Exception as e:
                    log(f"   ❌ Ошибка С6-22: {e}")

                # --- СК3-50: THD ---
                thd_sk3 = None
                try:
                    stop_event.wait(THD_FM_WAIT_BEFORE_SK3_THD_S)
                    thd_sk3 = round(sk3.read_thd(), 3)
                    log(f"      КГ (СК3-50): {thd_sk3} %")
                except Exception as e:
                    log(f"   ❌ Ошибка THD с СК3-50: {e}")

                # --- Допуск по частоте модуляции ---
                tolerance = _thd_fm_tolerance(fm_hz, thd_c6)

                # --- Оценка: сравниваем КГ_C6 - КГ_СК3 с допуском ---
                if thd_c6 is None or thd_sk3 is None:
                    status, emoji = 'error', '⚪ нет данных'
                else:
                    delta = thd_sk3 - thd_c6
                    if tolerance is None or tolerance <= 0:
                        status, emoji = 'error', '⚪ нет допуска'
                    else:
                        status, emoji = evaluate(delta, tolerance)
                        log(f"      ΔКГ = {delta:.3f} %, "
                            f"допуск ±{tolerance:.3f} % → {emoji}")

                band_str = f"0.02-{lp_khz:g}"
                row = ThdFmResult(
                    mod_freq_hz=float(fm_hz),
                    set_deviation_hz=float(dev_hz),
                    meas_deviation_hz=meas_dev,
                    thd_sk3=thd_sk3,
                    thd_c6=thd_c6,
                    tolerance=tolerance,
                    mod_freq_c6=str(mod_freq_c6),
                    band_str=band_str,
                    status=status,
                    comment=emoji,
                )

                # --- Диалог при fail ---
                if status == 'fail' and confirm_callback is not None:
                    try:
                        decision = confirm_callback(
                            freq_mhz=THD_FM_CARRIER_MHZ,
                            level_dbm=None,
                            error_value=round(thd_sk3 - thd_c6, 3) if (thd_sk3 is not None and thd_c6 is not None) else 0.0,
                            tolerance_value=tolerance if tolerance else 0.0,
                            stage='thd_fm',
                        )
                    except Exception:
                        decision = True
                    if decision is False:
                        row = ThdFmResult(
                            mod_freq_hz=float(fm_hz),
                            set_deviation_hz=float(dev_hz),
                            meas_deviation_hz=meas_dev,
                            thd_sk3=thd_sk3,
                            thd_c6=thd_c6,
                            tolerance=tolerance,
                            mod_freq_c6=str(mod_freq_c6),
                            band_str=band_str,
                            status='fail',
                            comment=emoji + ' (остановлено оператором)',
                        )
                        results.append(row)
                        return results

                results.append(row)

    except Exception as e:
        log(f"   ❌ Неожиданная ошибка Теста 8: {e}")

    # --- 5. Отключение режимов ---
    try:
        gen.output_off()
        sk3.set_thd_off()
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ⚠ Ошибка выключения режимов: {e}")

    return results
