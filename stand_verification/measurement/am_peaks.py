"""
Тест 11: Погрешность измерения пиковых значений Кам (АМ).

Логика из скрипта AM_FM_PM_.py (блок «AM погрешность»):

  1. Генератор: 20 МГц, 0 dBm, АМ, 1 кГц, 30%.
  2. СК3-50: MODE AM, CAL:CURR? (калибровка 20 сек).
  3. Ожидание '0'. Если не пришёл — тест останавливается (RuntimeError).
  4. Цикл по 4 несущим: [20, 4, 1, 0.1] МГц.
     Для каждой несущей — свой список Fm модуляции:
       20 МГц → [20, 60, 1000, 30000, 60000]
       4 МГц  → [1000]
       1 МГц  → [20, 60, 1000, 6000]
       0.1 МГц → [400]
     Для каждой Fm — список Кам:
       Fm=1000 и несущая != 4 → [100, 95, 50, 10, 3, 1]
       иначе → [95]
  5. Флаги:
     - flag_Man_f: MAN ON при Кам ≥ 95 (первый раз).
     - flag_AMT: AMT ON для Fm ∈ [20, 60, 90], AMT OFF для остальных.
     - flag_Nex_f: переключение MAN OFF → MAN ON при смене несущей.
  6. Для каждой точки:
     - установить Fm;
     - установить фильтр;
     - управление флагами;
     - установить Кам;
     - PEAK+ и PEAK−;
     - Δ+ = PEAK+ − Кам, Δ− = PEAK− − Кам;
     - max|Δ| сравнить с допуском = Bn × Кам + 3 × delnoise.
  7. Все значения в %.
"""

from stand_verification.config import (
    AM_PEAKS_START_CARRIER_MHZ, AM_PEAKS_START_POWER_DBM,
    AM_PEAKS_START_MOD_FREQ_HZ, AM_PEAKS_START_DEPTH_PERCENT,
    AM_PEAKS_CARRIER_LIST_MHZ, AM_PEAKS_MOD_FREQ_MAP_HZ,
    AM_PEAKS_KAM_LIST_FULL, AM_PEAKS_KAM_LIST_DEFAULT,
    AM_PEAKS_FILTER_MAP_KHZ, AM_PEAKS_BN_MAP,
    AM_PEAKS_DELNOISE_MAP_PERCENT,
    AM_PEAKS_WAIT_AFTER_SET_CARRIER_S, AM_PEAKS_WAIT_AFTER_SET_MOD_FREQ_S,
    AM_PEAKS_WAIT_AFTER_SET_DEPTH_S, AM_PEAKS_WAIT_BEFORE_PEAK_S,
    AM_PEAKS_WAIT_AFTER_PEAK_POS_S, AM_PEAKS_WAIT_BEFORE_PEAK_NEG_S,
    AM_PEAKS_WAIT_AFTER_PEAK_NEG_S, AM_PEAKS_CALIBRATION_WAIT_S,
    AM_PEAKS_CALIBRATION_ATTEMPTS, AM_PEAKS_CALIBRATION_ATTEMPT_WAIT_S,
)
from stand_verification.models import KamResult
from stand_verification.measurement.tolerances import evaluate, require_finite


def _kam_list_for(carrier_mhz, fm_hz):
    """Список Кам для конкретной комбинации (несущая, Fm)."""
    if fm_hz == 1000 and carrier_mhz != 4:
        return AM_PEAKS_KAM_LIST_FULL
    return AM_PEAKS_KAM_LIST_DEFAULT


def _bn_for(fm_hz):
    """Коэффициент Bn (0.03 для 20/60 Гц, иначе 0.01)."""
    return AM_PEAKS_BN_MAP.get(fm_hz, 0.01)


def _delnoise_for(fm_hz):
    """Шумовая добавка delnoise по Fm (%)."""
    return AM_PEAKS_DELNOISE_MAP_PERCENT.get(fm_hz, 0.03)


def run_am_peaks(gen, sk3, stop_event, log, confirm_callback=None):
    """
    Прогон Теста 11.
    :return: список KamResult (переменное число точек, обычно 11–13).
    """
    results = []

    log("─── Тест 11: Погрешность пиковых значений Кам (АМ) ───")

    # --- 1. Настройка генератора ---
    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(AM_PEAKS_START_CARRIER_MHZ)
        stop_event.wait(1.0)
        gen.set_power_dbm(AM_PEAKS_START_POWER_DBM)
        stop_event.wait(1.0)
        gen.set_am_on()
        stop_event.wait(1.0)
        gen.set_am_source_int()
        stop_event.wait(1.0)
        gen.set_lfo_freq_hz(AM_PEAKS_START_MOD_FREQ_HZ)
        stop_event.wait(1.0)
        gen.set_am_depth_percent(AM_PEAKS_START_DEPTH_PERCENT)
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки генератора: {e}")
        return results

    # --- 2. Настройка СК3-50 ---
    try:
        sk3.set_mode_am()
        stop_event.wait(5.0)
    except Exception as e:
        log(f"   ❌ Ошибка настройки СК3-50: {e}")
        return results

    # --- 3. Калибровка СК3-50 ---
    log("   Калибровка СК3-50 (CAL:CURR?)…")
    try:
        calibrated = sk3.cal_current(
            timeout_s=AM_PEAKS_CALIBRATION_WAIT_S,
            attempts=AM_PEAKS_CALIBRATION_ATTEMPTS,
            attempt_wait_s=AM_PEAKS_CALIBRATION_ATTEMPT_WAIT_S,
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

    # --- 4. Цикл по несущим ---
    flag_man_f = False
    flag_amt = False
    flag_nex_f = False

    try:
        for carrier_mhz in AM_PEAKS_CARRIER_LIST_MHZ:
            if stop_event.is_set():
                break

            log(f"─── Несущая {carrier_mhz} МГц ───")

            # Установка несущей
            try:
                gen.set_frequency_mhz(carrier_mhz)
            except Exception as e:
                log(f"   ❌ Ошибка установки несущей: {e}")
                break
            stop_event.wait(AM_PEAKS_WAIT_AFTER_SET_CARRIER_S)

            # Переключение flag_nex_f (как в скрипте)
            flag_nex_f = not flag_nex_f

            mod_freqs = AM_PEAKS_MOD_FREQ_MAP_HZ.get(int(carrier_mhz),
                                                     AM_PEAKS_MOD_FREQ_MAP_HZ.get(carrier_mhz, [1000]))

            for fm_hz in mod_freqs:
                if stop_event.is_set():
                    break

                log(f"   Fm = {fm_hz} Гц")

                # Установка Fm
                try:
                    gen.set_lfo_freq_hz(fm_hz)
                except Exception as e:
                    log(f"   ❌ Ошибка Fm: {e}")
                    continue
                stop_event.wait(AM_PEAKS_WAIT_AFTER_SET_MOD_FREQ_S)

                # Фильтр СК3-50
                lp_khz = AM_PEAKS_FILTER_MAP_KHZ.get(fm_hz, 200.0)
                try:
                    sk3.set_filter_hp_hz(20)
                    stop_event.wait(1.0)
                    sk3.set_filter_lp_khz(lp_khz)
                    stop_event.wait(1.0)
                except Exception as e:
                    log(f"   ❌ Ошибка фильтра: {e}")

                # Управление AMT
                try:
                    if fm_hz in (20, 60, 90):
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
                    log(f"   ⚠ Ошибка AMT: {e}")

                # Список Кам
                kam_list = _kam_list_for(carrier_mhz, fm_hz)
                bn = _bn_for(fm_hz)
                delnoise = _delnoise_for(fm_hz)

                for kam in kam_list:
                    if stop_event.is_set():
                        break

                    # Управление MAN для Кам >= 95
                    try:
                        if kam in (95, 100):
                            if not flag_man_f:
                                gen.set_am_off()
                                stop_event.wait(5.0)
                                sk3.set_freq_manual_on()
                                flag_man_f = True
                                gen.set_am_on()
                                stop_event.wait(5.0)

                            if not flag_nex_f:
                                gen.set_am_off()
                                stop_event.wait(5.0)
                                sk3.set_freq_manual_off()
                                stop_event.wait(5.0)
                                sk3.set_freq_manual_on()
                                stop_event.wait(5.0)
                                gen.set_am_on()
                                stop_event.wait(5.0)
                                flag_nex_f = True
                        else:
                            if flag_man_f:
                                sk3.set_freq_manual_off()
                                stop_event.wait(10.0)
                                flag_man_f = False
                    except Exception as e:
                        log(f"   ⚠ Ошибка MAN: {e}")

                    tolerance = bn * kam + 3 * delnoise
                    require_finite(tolerance, 'Допуск')

                    # Установка Кам
                    try:
                        gen.set_am_depth_percent(kam)
                    except Exception as e:
                        log(f"   ❌ Ошибка Кам: {e}")
                        continue
                    stop_event.wait(AM_PEAKS_WAIT_AFTER_SET_DEPTH_S)

                    # --- PEAK + ---
                    peak_plus = None
                    delta_plus = None
                    try:
                        sk3.set_polarity_pos()
                        stop_event.wait(AM_PEAKS_WAIT_BEFORE_PEAK_S)
                        peak_plus = round(sk3.read_peak(), 2)
                        delta_plus = peak_plus - kam
                        log(f"      +Кам: {peak_plus} %, Δ+ = {delta_plus:+.2f}")
                    except Exception as e:
                        log(f"   ❌ Ошибка PEAK+ : {e}")

                    stop_event.wait(AM_PEAKS_WAIT_AFTER_PEAK_POS_S)

                    # --- PEAK − ---
                    peak_minus = None
                    delta_minus = None
                    try:
                        sk3.set_polarity_neg()
                        stop_event.wait(AM_PEAKS_WAIT_BEFORE_PEAK_NEG_S)
                        peak_minus = round(sk3.read_peak(), 2)
                        delta_minus = peak_minus - kam
                        log(f"      −Кам: {peak_minus} %, Δ− = {delta_minus:+.2f}")
                    except Exception as e:
                        log(f"   ❌ Ошибка PEAK− : {e}")

                    stop_event.wait(AM_PEAKS_WAIT_AFTER_PEAK_NEG_S)

                    # --- Оценка ---
                    if delta_plus is None or delta_minus is None:
                        status, emoji = 'error', '⚪ нет данных'
                    else:
                        max_dev = max(abs(delta_plus), abs(delta_minus))
                        status, emoji = evaluate(max_dev, tolerance)
                        log(f"      Допуск: ±{tolerance:.2f} %, max|Δ| = {max_dev:.2f} % → {emoji}")

                    row = KamResult(
                        carrier_mhz=float(carrier_mhz),
                        mod_freq_hz=float(fm_hz),
                        set_depth_percent=float(kam),
                        peak_plus_percent=peak_plus,
                        peak_minus_percent=peak_minus,
                        delta_plus_percent=round(delta_plus, 2) if delta_plus is not None else None,
                        delta_minus_percent=round(delta_minus, 2) if delta_minus is not None else None,
                        tolerance_percent=round(tolerance, 2),
                        band_str=f'0.02-{lp_khz:g}',
                        status=status,
                        comment=emoji,
                    )

                    # --- Диалог ---
                    if status == 'fail' and confirm_callback is not None:
                        try:
                            decision = confirm_callback(
                                freq_mhz=float(carrier_mhz),
                                level_dbm=None,
                                error_value=round(max_dev, 2),
                                tolerance_value=round(tolerance, 2),
                                stage='am_peaks',
                            )
                        except Exception:
                            decision = True
                        if decision is False:
                            row = KamResult(
                                carrier_mhz=row.carrier_mhz,
                                mod_freq_hz=row.mod_freq_hz,
                                set_depth_percent=row.set_depth_percent,
                                peak_plus_percent=row.peak_plus_percent,
                                peak_minus_percent=row.peak_minus_percent,
                                delta_plus_percent=row.delta_plus_percent,
                                delta_minus_percent=row.delta_minus_percent,
                                tolerance_percent=row.tolerance_percent,
                                band_str=row.band_str,
                                status='fail',
                                comment=emoji + ' (остановлено оператором)',
                            )
                            results.append(row)
                            return results

                    results.append(row)

    except Exception as e:
        log(f"   ❌ Неожиданная ошибка Теста 11: {e}")

    # --- 5. Сброс ---
    try:
        gen.output_off()
        sk3.set_freq_manual_off()
        stop_event.wait(10.0)
        if flag_amt:
            try:
                sk3.set_amt_off()
                stop_event.wait(1.0)
            except Exception:
                pass
    except Exception as e:
        log(f"   ⚠ Ошибка выключения: {e}")

    return results