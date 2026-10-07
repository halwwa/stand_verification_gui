FREQ_TOLERANCE_FORMULA = lambda f_hz: 5e-6 * abs(f_hz) + 1.0
LEVEL_TOLERANCE_DB = 1.0
LEVEL_TOLERANCE_HIGH_DB = 2.0
TOLERANCE_RATIO_WARN = 0.7


def evaluate(value, tolerance):
    abs_v = abs(value)
    if abs_v > tolerance:
        return 'fail', '🔴'
    elif abs_v > TOLERANCE_RATIO_WARN * tolerance:
        return 'warn', '🟡'
    return 'ok', '🟢'
