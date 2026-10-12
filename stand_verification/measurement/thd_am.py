"""
Тест 7: КГ АМ.

Логика из скрипта AM_FM.py (блок «КГ АМ»):
  1. Генератор: 20 МГц, 0 dBm, режим АМ, 1 кГц, 10%.
  2. СК3-50: MODE AM, CONF:FREQ:MAN ON, CONF:THD ON.
  3. С6-22: MODE DFM, LIMitD AUTO.
  4. Цикл по Fm ∈ [20, 90, 6000, 60000] Гц × Кам ∈ [30, 95] %:
     - установить Fm;
     - установить фильтры СК3-50 (HPAS 0.02kHz, LPAS зависит от Fm);
     - CONF:AMT ON для 20/90 Гц, OFF для остальных;
     - установить AM:DEPT Кам;
     - PEAK? (POS) → измеренный Кам;
     - MEASure:THD? С6-22 → КГ_C6;
     - MEASure:FREQuency? С6-22 → частота модуляции;
     - THD? СК3-50 → КГ_СК3;
     - допуск по правилам скрипта.
  5. По завершении: CONF:THD OFF, CONF:FREQ:MAN OFF.
"""

import time

from stand_verification.config import (
    THD_AM_CARRIER_MHZ, THD_AM_POWER_DBM,
    THD_AM_START_MOD_FREQ_HZ, THD_AM_START_DEPTH,
    THD_AM_FM_LIST_HZ, THD_AM_KAM_LIST, THD_AM_FILTER_MAP,
    THD_AM_WAIT_AFTER_FREQ_MAN_S, THD_AM_WAIT_AFTER_SET_DEPTH_S,
    THD_AM_WAIT_BEFORE_PEAK_S, THD_AM_WAIT_AFTER_PEAK_S,
    THD_AM_WAIT_BEFORE_C6_THD_S, THD_AM_WAIT_AFTER_C6_CMD_S,
    THD_AM_WAIT_BEFORE_SK3_THD_S,
    THD_AM_TOL_DEFAULT, THD_AM_TOL_20_90_KAM30,
    THD_AM_TOL_6000_KAM30, THD_AM_TOL_60000_KAM95,
)
from stand_verification.models import ThdAmResult
from stand_verification.measurement.tolerances import evaluate, require_finite


def _thd_am_tolerance(freq_hz, kam):
    """Выбор допуска для Теста 7 по правилам скрипта."""
    if kam == 30 and freq_hz in (20, 90):
        return THD_AM_TOL_20_90_KAM30
    elif kam == 30 and freq_hz == 6000:
        return THD_AM_TOL_6000_KAM30
    elif kam == 95 and freq_hz == 60000:
        return THD_AM_TOL_60000_KAM95
    return THD_AM_TOL_DEFAULT


def run_thd_am(gen, sk3, c6, stop_event, log, confirm_callback=None):
    """
    Прогон Теста 7.
    :param gen: SMB100A
    :param sk3: SK350
    :param c6:  C622 (может быть None, если С6-22 не подключён — тест пропущен)
    :return: список ThdAmResult (8 строк)
    """
    results = []

    if c6 is None:
        log("⚠ С6-22 не подключён — Тест 7 (КГ АМ) пропущен.")
        return results

    log("─── Тест 7: КГ АМ ───")

    # --- 1. Настройка генератора ---
    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(THD_AM_CARRIER_MHZ)
        stop_event.wait(1.0)
        gen.set_power_dbm(THD_AM_POWER_DBM)
        stop_event.wait(1.0)
        gen.set_am_on()
        stop_event.wait(1.0)
        gen.set_am_source_int()
        stop_event.wait(1.0)
        gen.set_lfo_freq_hz(THD_AM_START_MOD_FREQ_HZ)
        stop_event.wait(1.0)
        gen.set_am_depth_percent(THD_AM_START_DEPTH)
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки генератора: {e}")
        return results

    # --- 2. Настройка СК3-50 ---
    try:
        sk3.set_mode_am()
        stop_event.wait(1.0)
        gen.output_on()
        # Задержка, чтобы СК3-50 успел измерить частоту
        stop_event.wait(5.0)
        sk3.set_freq_manual_on()   # фиксируем последнюю измеренную частоту
        stop_event.wait(THD_AM_WAIT_AFTER_FREQ_MAN_S)
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
        # Продолжаем — попробуем измерить
    # --------------------------------------------------------

    # --- 4. Двойной цикл: Fm × Кам ---
    flag_amt = False
    try:
        for fm_hz in THD_AM_FM_LIST_HZ:
            if stop_event.is_set():
                break

            log(f"─── Fm = {fm_hz} Гц ───")

            # Установка модулирующей частоты на генераторе
            try:
                gen.set_lfo_freq_hz(fm_hz)
            except Exception as e:
                log(f"   ❌ Ошибка установки Fm: {e}")
                break
            stop_event.wait(1.0)

            # Полоса фильтра для этой Fm
            lp_khz = THD_AM_FILTER_MAP.get(fm_hz, 200.0)

            # Установка фильтров СК3-50: HPAS 0.02 кГц, LPAS зависит от Fm
            try:
                sk3.set_filter_hp_hz(20)     # 20 Гц
                stop_event.wait(1.0)
                sk3.set_filter_lp_khz(lp_khz)
                stop_event.wait(1.0)
            except Exception as e:
                log(f"   ❌ Ошибка установки фильтра: {e}")

            # CONF:AMT — ON для 20/90 Гц, OFF для остальных
            try:
                if fm_hz in (20, 90):
                    if not flag_amt:
                        sk3.set_amt_on()
                        flag_amt = True
                        stop_event.wait(5.0)
                else:
                    if flag_amt:
                        sk3.set_amt_off()
                        flag_amt = False
                        stop_event.wait(1.0)
            except Exception as e:
                log(f"   ⚠ Ошибка CONF:AMT: {e}")

            # --- Внутренний цикл по Кам ---
            for kam in THD_AM_KAM_LIST:
                if stop_event.is_set():
                    break

                log(f"   Кам = {kam} %")

                # Установка глубины АМ
                try:
                    gen.set_am_depth_percent(kam)
                except Exception as e:
                    log(f"   ❌ Ошибка установки Кам: {e}")
                    continue
                stop_event.wait(THD_AM_WAIT_AFTER_SET_DEPTH_S)

                # PEAK? POS → измеренный Кам
                meas_depth = None
                try:
                    sk3.set_polarity_pos()
                    stop_event.wait(THD_AM_WAIT_BEFORE_PEAK_S)
                    meas_depth = round(sk3.read_peak(), 2)
                    log(f"      +Кам (СК3-50): {meas_depth}")
                except Exception as e:
                    log(f"   ❌ Ошибка чтения PEAK?: {e}")

                # --- С6-22: THD ---
                thd_c6 = None
                mod_freq_c6 = ""
                try:
                    stop_event.wait(THD_AM_WAIT_BEFORE_C6_THD_S)
                    if stop_event.is_set():
                        break
                    thd_c6 = round(c6.read_thd(), 3)
                    log(f"      КГ (С6-22): {thd_c6} %")
                    stop_event.wait(THD_AM_WAIT_AFTER_C6_CMD_S)

                    mod_freq_c6 = c6.read_mod_frequency()
                    log(f"      Fmod (С6-22): {mod_freq_c6}")
                except Exception as e:
                    log(f"   ❌ Ошибка С6-22: {e}")

                # --- СК3-50: THD ---
                thd_sk3 = None
                try:
                    stop_event.wait(THD_AM_WAIT_BEFORE_SK3_THD_S)
                    thd_sk3 = round(sk3.read_thd(), 3)
                    log(f"      КГ (СК3-50): {thd_sk3} %")
                except Exception as e:
                    log(f"   ❌ Ошибка чтения THD с СК3-50: {e}")

                # --- Допуск ---
                tolerance = _thd_am_tolerance(fm_hz, kam)

                # --- Оценка: сравниваем КГ_C6 с допуском ---
                if thd_c6 is None:
                    status, emoji = 'error', '⚪ нет данных'
                else:
                    status, emoji = evaluate(thd_c6, tolerance)
                    log(f"      Допуск: ±{tolerance:.2f} %, КГ_С6 = {thd_c6:.3f} % → {emoji}")

                band_str = f"0.02-{lp_khz:g}"
                row = ThdAmResult(
                    mod_freq_hz=float(fm_hz),
                    set_depth=float(kam),
                    meas_depth=meas_depth,
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
                            freq_mhz=THD_AM_CARRIER_MHZ,
                            level_dbm=None,
                            error_value=round(thd_c6, 3),
                            tolerance_value=tolerance,
                            stage='thd_am',
                        )
                    except Exception:
                        decision = True
                    if decision is False:
                        row = ThdAmResult(
                            mod_freq_hz=float(fm_hz),
                            set_depth=float(kam),
                            meas_depth=meas_depth,
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
        log(f"   ❌ Неожиданная ошибка Теста 7: {e}")

    # --- 5. Отключение режимов ---
    try:
        gen.output_off()
        sk3.set_thd_off()
        stop_event.wait(1.0)
        sk3.set_freq_manual_off()
        stop_event.wait(1.0)
        if flag_amt:
            try:
                sk3.set_amt_off()
                stop_event.wait(1.0)
            except Exception:
                pass
    except Exception as e:
        log(f"   ⚠ Ошибка выключения режимов: {e}")

    return results