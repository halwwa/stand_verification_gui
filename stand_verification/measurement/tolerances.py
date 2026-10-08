from math import isfinite


FREQ_TOLERANCE_FORMULA = lambda f_hz: 5e-6 * abs(f_hz) + 1.0
LEVEL_TOLERANCE_DB = 1.0
LEVEL_TOLERANCE_HIGH_DB = 2.0
TOLERANCE_RATIO_WARN = 0.7


def require_finite(value, label):
    if not isfinite(value):
        raise ValueError(f'{label}: недопустимое числовое значение {value}')


def evaluate(value, tolerance):
    """
    Оценка результата по допуску.
    Возвращает ('ok' | 'warn' | 'fail', emoji).
    """
    require_finite(value, 'Погрешность')
    require_finite(tolerance, 'Допуск')
    abs_v = abs(value)
    if abs_v > tolerance:
        return 'fail', '🔴'
    elif abs_v > TOLERANCE_RATIO_WARN * tolerance:
        return 'warn', '🟡'
    return 'ok', '🟢'


# ============================================================
#              ДОПУСКИ ДЛЯ АМ ШУМА (в %)
# ============================================================

def am_noise_tolerance(band_high_khz: float) -> float:
    """
    Допуск СКЗ АМ шума (%) по верхней границе полосы.
    Возвращает %.
    """
    if band_high_khz <= 1.5:
        return 0.01      # полоса 0.02–1.5 кГц
    elif band_high_khz <= 3.4:
        return 0.01      # полоса 0.02–3.4 кГц (для 0.1 МГц и выше)
    elif band_high_khz <= 20:
        return 0.03
    elif band_high_khz <= 60:
        return 0.05
    else:
        return 0.1


# ============================================================
#              ДОПУСКИ ДЛЯ ЧМ ШУМА (в Гц)
# ============================================================

def fm_noise_tolerance(freq_mhz: float, band_high_khz: float) -> float:
    """
    Допуск СКЗ ЧМ шума (Гц) по частоте несущей и верхней границе полосы.
    Формулы из старого скрипта.
    """
    f_hz = freq_mhz * 1_000_000
    if band_high_khz <= 3.4:
        if freq_mhz == 1:
            return 2.0
        else:
            return 4e-9 * f_hz + 1.0
    elif band_high_khz <= 20:
        if freq_mhz == 1:
            return 4.0
        else:
            return 4e-8 * f_hz + 2.0
    elif band_high_khz <= 60:
        if freq_mhz == 1:
            return 10.0
        else:
            return 1e-7 * f_hz + 10.0
    else:  # 200 кГц
        if freq_mhz == 1:
            return 30.0
        else:
            return 2e-7 * f_hz + 40.0


# ============================================================
#              ДОПУСКИ ДЛЯ ФМ ШУМА (в рад)
# ============================================================

def pm_noise_tolerance(freq_mhz: float, band_high_khz: float) -> float:
    """
    Допуск СКЗ ФМ шума (рад) по частоте несущей и верхней границе полосы.
    Формулы из старого скрипта.
    """
    f_ghz = freq_mhz / 1000.0
    if band_high_khz <= 20:
        return 0.003 * f_ghz + 0.003
    elif band_high_khz <= 60:
        return 0.003 * f_ghz + 0.004
    else:  # 200 кГц
        return 0.003 * f_ghz + 0.005