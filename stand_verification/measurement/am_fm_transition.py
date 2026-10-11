"""
Тест 6: Переход АМ↔ЧМ.

Логика из скрипта AM_FM.py:
  A) Переход АМ → ЧМ:
     - Генератор: 20 МГц, −7 dBm, АМ 30%, 20 кГц.
     - СК3-50 в режиме FM, полоса 0.3–20 кГц.
     - Измерение пикового значения PEAK? (POS и NEG).
     - Коэффициент K_am_fm = max(|+ДЧ|, |−ДЧ|) / 30.
     - Допуск: 10 Гц.
  B) Переход ЧМ → АМ:
     - Генератор: 100 МГц, 0 dBm, ЧМ 200 кГц, 20 кГц.
     - СК3-50 в режиме AM, полоса 0.3–20 кГц.
     - Измерение PEAK? (POS и NEG).
     - Коэффициент K_fm_am = max(|+Кам|, |−Кам|) / 200.
     - Допуск: 0.02%.
"""

import time

from stand_verification.config import (
    TR_AM_FM_FREQ_MHZ, TR_AM_FM_POWER_DBM, TR_AM_FM_MOD_FREQ_HZ,
    TR_AM_FM_DEPTH_PERCENT, TR_AM_FM_HF_KHZ, TR_AM_FM_LF_KHZ,
    TR_AM_FM_TOLERANCE_HZ,
    TR_FM_AM_FREQ_MHZ, TR_FM_AM_POWER_DBM, TR_FM_AM_MOD_FREQ_HZ,
    TR_FM_AM_DEVIATION_HZ, TR_FM_AM_HF_KHZ, TR_FM_AM_LF_KHZ,
    TR_FM_AM_TOLERANCE_PERCENT,
    TR_SETTLE_DELAY, TR_STEP_DELAY,
)
from stand_verification.models import TransitionResult
from stand_verification.measurement.tolerances import evaluate, require_finite


def run_transition(gen, sk3, stop_event, log, confirm_callback=None):
    """
    Прогон теста 6 (два направления).
    Возвращает список TransitionResult (2 строки).
    """
    results = []

    # --------------------------------------------------------
    #         A) Переход АМ → ЧМ
    # --------------------------------------------------------
    if stop_event.is_set():
        return results
    log("─── Тест 6: Переход АМ → ЧМ ───")

    try:
        gen.output_off()
        gen.reset()
        gen.set_frequency_mhz(TR_AM_FM_FREQ_MHZ)
        stop_event.wait(TR_STEP_DELAY)
        gen.set_power_dbm(TR_AM_FM_POWER_DBM)
        stop_event.wait(TR_STEP_DELAY)
        gen.set_am_on()
        stop_event.wait(TR_STEP_DELAY)
        gen.set_am_source_int()
        stop_event.wait(TR_STEP_DELAY)
        gen.set_lfo_freq_hz(TR_AM_FM_MOD_FREQ_HZ)
        stop_event.wait(TR_STEP_DELAY)
        gen.set_am_depth_percent(TR_AM_FM_DEPTH_PERCENT)
        stop_event.wait(TR_STEP_DELAY)
        gen.output_on()
        stop_event.wait(TR_STEP_DELAY)

        sk3.set_mode_fm()
        stop_event.wait(1.0)
        sk3.set_filter_hp_khz(TR_AM_FM_HF_KHZ)
        stop_event.wait(1.0)
        sk3.set_filter_lp_khz(TR_AM_FM_LF_KHZ)
        if stop_event.wait(TR_SETTLE_DELAY):
            return results

        sk3.set_polarity_pos()
        stop_event.wait(1.0)
        dfp = round(sk3.read_peak(), 2)
        log(f"   +ДЧ (AM→FM): {dfp}")

        sk3.set_polarity_neg()
        stop_event.wait(1.0)
        dfm = round(sk3.read_peak(), 2)
        log(f"   −ДЧ (AM→FM): {dfm}")

        # max по модулю
        max_val = dfp if abs(dfp) >= abs(dfm) else dfm
        k_am_fm = max_val / TR_AM_FM_DEPTH_PERCENT
        require_finite(k_am_fm, 'K am_fm')

        status, emoji = evaluate(k_am_fm, TR_AM_FM_TOLERANCE_HZ)
        log(f"   K_am_fm: {k_am_fm:.2f} Гц, "
            f"допуск ±{TR_AM_FM_TOLERANCE_HZ:.2f} Гц → {emoji}")

        row = TransitionResult(
            direction='AM→FM',
            value_plus=dfp, value_minus=dfm,
            coefficient=round(k_am_fm, 2),
            tolerance=TR_AM_FM_TOLERANCE_HZ,
            unit='Гц', status=status, comment=emoji,
        )

        if status == 'fail' and confirm_callback is not None:
            try:
                decision = confirm_callback(
                    freq_mhz=TR_AM_FM_FREQ_MHZ,
                    level_dbm=None,
                    error_value=round(k_am_fm, 2),
                    tolerance_value=TR_AM_FM_TOLERANCE_HZ,
                    stage='am_fm_transition',
                )
            except Exception:
                decision = True
            if decision is False:
                row = TransitionResult(
                    direction='AM→FM',
                    value_plus=dfp, value_minus=dfm,
                    coefficient=round(k_am_fm, 2),
                    tolerance=TR_AM_FM_TOLERANCE_HZ,
                    unit='Гц', status='fail',
                    comment=emoji + ' (остановлено оператором)',
                )
                results.append(row)
                return results

        results.append(row)

    except Exception as e:
        log(f"   ❌ Ошибка AM→FM: {e}")
        results.append(TransitionResult(
            direction='AM→FM',
            value_plus=None, value_minus=None,
            coefficient=None, tolerance=TR_AM_FM_TOLERANCE_HZ,
            unit='Гц', status='error', comment=str(e),
        ))

    # Выключить выход перед следующим переходом
    try:
        gen.output_off()
        gen.set_am_off()
        stop_event.wait(1.0)
    except Exception:
        pass

    # --------------------------------------------------------
    #         B) Переход ЧМ → АМ
    # --------------------------------------------------------
    if stop_event.is_set():
        return results
    log("─── Тест 6: Переход ЧМ → АМ ───")

    try:
        gen.set_frequency_mhz(TR_FM_AM_FREQ_MHZ)
        stop_event.wait(TR_STEP_DELAY)
        gen.set_power_dbm(TR_FM_AM_POWER_DBM)
        stop_event.wait(TR_STEP_DELAY)
        gen.set_fm_on()
        stop_event.wait(TR_STEP_DELAY)
        gen.set_fm_source_int()
        stop_event.wait(TR_STEP_DELAY)
        gen.set_lfo_freq_hz(TR_FM_AM_MOD_FREQ_HZ)
        stop_event.wait(TR_STEP_DELAY)
        gen.set_fm_deviation_hz(TR_FM_AM_DEVIATION_HZ)
        stop_event.wait(TR_STEP_DELAY)
        gen.output_on()
        stop_event.wait(TR_STEP_DELAY)

        sk3.set_mode_am()
        stop_event.wait(1.0)
        sk3.set_filter_hp_khz(TR_FM_AM_HF_KHZ)
        stop_event.wait(1.0)
        sk3.set_filter_lp_khz(TR_FM_AM_LF_KHZ)
        if stop_event.wait(TR_SETTLE_DELAY):
            return results

        sk3.set_polarity_pos()
        stop_event.wait(1.0)
        amp = round(sk3.read_peak(), 2)
        log(f"   +Am (FM→AM): {amp}")

        sk3.set_polarity_neg()
        stop_event.wait(1.0)
        amm = round(sk3.read_peak(), 2)
        log(f"   −Am (FM→AM): {amm}")

        max_val = amp if abs(amp) >= abs(amm) else amm
        k_fm_am = max_val / (TR_FM_AM_DEVIATION_HZ / 1000.0)  # делим на 200 (кГц)
        require_finite(k_fm_am, 'K fm_am')

        status, emoji = evaluate(k_fm_am, TR_FM_AM_TOLERANCE_PERCENT)
        log(f"   K_fm_am: {k_fm_am:.3f} %, "
            f"допуск ±{TR_FM_AM_TOLERANCE_PERCENT:.3f} % → {emoji}")

        row = TransitionResult(
            direction='FM→AM',
            value_plus=amp, value_minus=amm,
            coefficient=round(k_fm_am, 3),
            tolerance=TR_FM_AM_TOLERANCE_PERCENT,
            unit='%', status=status, comment=emoji,
        )

        if status == 'fail' and confirm_callback is not None:
            try:
                decision = confirm_callback(
                    freq_mhz=TR_FM_AM_FREQ_MHZ,
                    level_dbm=None,
                    error_value=round(k_fm_am, 3),
                    tolerance_value=TR_FM_AM_TOLERANCE_PERCENT,
                    stage='am_fm_transition',
                )
            except Exception:
                decision = True
            if decision is False:
                row = TransitionResult(
                    direction='FM→AM',
                    value_plus=amp, value_minus=amm,
                    coefficient=round(k_fm_am, 3),
                    tolerance=TR_FM_AM_TOLERANCE_PERCENT,
                    unit='%', status='fail',
                    comment=emoji + ' (остановлено оператором)',
                )

        results.append(row)

    except Exception as e:
        log(f"   ❌ Ошибка FM→AM: {e}")
        results.append(TransitionResult(
            direction='FM→AM',
            value_plus=None, value_minus=None,
            coefficient=None, tolerance=TR_FM_AM_TOLERANCE_PERCENT,
            unit='%', status='error', comment=str(e),
        ))

    # Сброс
    try:
        gen.output_off()
        gen.reset()
    except Exception:
        pass

    return results