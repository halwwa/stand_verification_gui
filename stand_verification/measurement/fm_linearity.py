"""
Тест 9: Проверка линейности шкал ЧМ.

Логика из скрипта AM_FM_PM_.py (блок «FM погрешность», секция линейности):

  Только для Fm = 1000 Гц, несущая 20 МГц, уровень 0 dBm.

  1. Генератор: 20 МГц, 0 dBm, ЧМ, 1 кГц, девиация 100 кГц.
  2. СК3-50: MODE FM, RANG:FM AUTO, CAL:CURR? (калибровка 20 сек).
  3. Если калибровка не удалась — тест останавливается (RuntimeError).
  4. Цикл по 5 максимальным девиациям (шкалам) × 2 делителя:
       - Dfm_mash (шкала) ∈ [1 000 000, 100 000, 10 000, 1 000, 100] Гц.
       - k (делитель) ∈ [1, 10].
       - Dfm_nel = Dfm_mash / k — фактическая девиация.
       - Устанавливаем девиацию Dfm_nel.
       - Устанавливаем шкалу CONF:RANG:FM {Dfm_mash}.
       - PEAK? (POS / NEG).
       - Допуск: AN × Dfm_nel + 3 × delnoise.
       - Сравниваем max(|Δ+|, |Δ−|) с допуском.
  5. Всего 10 точек. Все числа — в кГц.
"""

from stand_verification.config import (
    LIN_CARRIER_MHZ, LIN_POWER_DBM,
    LIN_MOD_FREQ_HZ, LIN_DEVIATION_SCALES_HZ, LIN_DIVISORS,
    LIN_AN, LIN_DELNOISE_HZ, LIN_FILTER_KHZ,
    LIN_WAIT_AFTER_SET_FREQ_S, LIN_WAIT_AFTER_SET_DEV_S,
    LIN_WAIT_AFTER_SET_RANGE_S, LIN_WAIT_BEFORE_PEAK_S,
    LIN_WAIT_AFTER_PEAK_POS_S, LIN_WAIT_BEFORE_PEAK_NEG_S,
    LIN_WAIT_AFTER_PEAK_NEG_S, LIN_CALIBRATION_WAIT_S,
    LIN_CALIBRATION_ATTEMPTS, LIN_CALIBRATION_ATTEMPT_WAIT_S,
)
from stand_verification.models import LinearityResult
from stand_verification.measurement.tolerances import evaluate, require_finite


def run_fm_linearity(gen, sk3, stop_event, log, confirm_callback=None):
    """
    Прогон Теста 9.
    :return: список LinearityResult (10 строк).
    """
    results = []

    log("─── Тест 9: Проверка линейности шкал ЧМ ───")

    # --- 1. Настройка генератора ---
    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(LIN_CARRIER_MHZ)
        stop_event.wait(1.0)
        gen.set_power_dbm(LIN_POWER_DBM)
        stop_event.wait(1.0)
        gen.set_fm_on()
        stop_event.wait(1.0)
        gen.set_fm_source_int()
        stop_event.wait(1.0)
        gen.set_lfo_freq_hz(LIN_MOD_FREQ_HZ)
        stop_event.wait(1.0)
        gen.set_fm_deviation_hz(LIN_DEVIATION_SCALES_HZ[0])  # 1 МГц — начальная
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
            timeout_s=LIN_CALIBRATION_WAIT_S,
            attempts=LIN_CALIBRATION_ATTEMPTS,
            attempt_wait_s=LIN_CALIBRATION_ATTEMPT_WAIT_S,
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

    # --- 4. Фильтр (один раз, Fm=1000) ---
    try:
        sk3.set_filter_hp_hz(20)             # ФВЧ 20 Гц
        stop_event.wait(1.0)
        sk3.set_filter_lp_khz(LIN_FILTER_KHZ)  # 20 кГц
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ❌ Ошибка установки фильтра: {e}")

    # --- 5. Двойной цикл: 5 шкал × 2 делителя ---
    try:
        for scale_hz in LIN_DEVIATION_SCALES_HZ:
            if stop_event.is_set():
                break

            for divisor in LIN_DIVISORS:
                if stop_event.is_set():
                    break

                dev_hz = scale_hz / divisor
                tolerance = LIN_AN * dev_hz + 3 * LIN_DELNOISE_HZ
                require_finite(tolerance, 'Допуск')

                log(f"─── Шкала {scale_hz} Гц, k={divisor}, девиация {dev_hz:.0f} Гц ───")

                # Устанавливаем девиацию
                try:
                    gen.set_fm_deviation_hz(dev_hz)
                except Exception as e:
                    log(f"   ❌ Ошибка установки девиации: {e}")
                    continue
                stop_event.wait(LIN_WAIT_AFTER_SET_DEV_S)

                # Устанавливаем шкалу
                try:
                    sk3.set_range_fm_hz(scale_hz)
                except Exception as e:
                    log(f"   ❌ Ошибка установки шкалы: {e}")
                    continue
                stop_event.wait(LIN_WAIT_AFTER_SET_RANGE_S)

                # --- PEAK + ---
                peak_plus = None
                delta_plus = None
                try:
                    sk3.set_polarity_pos()
                    stop_event.wait(LIN_WAIT_BEFORE_PEAK_S)
                    peak_plus = round(sk3.read_peak(), 1)
                    delta_plus = peak_plus - dev_hz
                    log(f"      +F: {peak_plus} Гц, Δ+ = {delta_plus:+.1f}")
                except Exception as e:
                    log(f"   ❌ Ошибка PEAK+ : {e}")

                stop_event.wait(LIN_WAIT_AFTER_PEAK_POS_S)

                # --- PEAK − ---
                peak_minus = None
                delta_minus = None
                try:
                    sk3.set_polarity_neg()
                    stop_event.wait(LIN_WAIT_BEFORE_PEAK_NEG_S)
                    peak_minus = round(sk3.read_peak(), 1)
                    delta_minus = peak_minus - dev_hz
                    log(f"      −F: {peak_minus} Гц, Δ− = {delta_minus:+.1f}")
                except Exception as e:
                    log(f"   ❌ Ошибка PEAK− : {e}")

                stop_event.wait(LIN_WAIT_AFTER_PEAK_NEG_S)

                # --- Оценка ---
                if delta_plus is None or delta_minus is None:
                    status, emoji = 'error', '⚪ нет данных'
                else:
                    max_dev = max(abs(delta_plus), abs(delta_minus))
                    status, emoji = evaluate(max_dev, tolerance)
                    log(f"      Допуск: ±{tolerance:.1f} Гц, max|Δ| = {max_dev:.1f} Гц → {emoji}")

                # В кГц
                row = LinearityResult(
                    scale_khz=round(scale_hz / 1000.0, 3),
                    set_deviation_khz=round(dev_hz / 1000.0, 3),
                    divisor=divisor,
                    peak_plus_khz=round(peak_plus / 1000.0, 3) if peak_plus is not None else None,
                    peak_minus_khz=round(peak_minus / 1000.0, 3) if peak_minus is not None else None,
                    delta_plus_khz=round(delta_plus / 1000.0, 3) if delta_plus is not None else None,
                    delta_minus_khz=round(delta_minus / 1000.0, 3) if delta_minus is not None else None,
                    tolerance_khz=round(tolerance / 1000.0, 3),
                    status=status,
                    comment=emoji,
                )

                # --- Диалог при fail ---
                if status == 'fail' and confirm_callback is not None:
                    try:
                        decision = confirm_callback(
                            freq_mhz=LIN_CARRIER_MHZ,
                            level_dbm=None,
                            error_value=round(max_dev / 1000.0, 3),
                            tolerance_value=round(tolerance / 1000.0, 3),
                            stage='fm_linearity',
                        )
                    except Exception:
                        decision = True
                    if decision is False:
                        row = LinearityResult(
                            scale_khz=row.scale_khz,
                            set_deviation_khz=row.set_deviation_khz,
                            divisor=row.divisor,
                            peak_plus_khz=row.peak_plus_khz,
                            peak_minus_khz=row.peak_minus_khz,
                            delta_plus_khz=row.delta_plus_khz,
                            delta_minus_khz=row.delta_minus_khz,
                            tolerance_khz=row.tolerance_khz,
                            status='fail',
                            comment=emoji + ' (остановлено оператором)',
                        )
                        results.append(row)
                        return results

                results.append(row)

    except Exception as e:
        log(f"   ❌ Неожиданная ошибка Теста 9: {e}")

    # --- 6. Сброс ---
    try:
        gen.output_off()
        sk3.set_range_fm_auto()
        stop_event.wait(1.0)
    except Exception as e:
        log(f"   ⚠ Ошибка выключения: {e}")

    return results