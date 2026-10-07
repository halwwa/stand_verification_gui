from stand_verification.config import SETTLE_DELAY
from stand_verification.measurement.tolerances import FREQ_TOLERANCE_FORMULA, evaluate


def measure_frequency(gen, sk3, stop_event, log, freq_mhz):
    if stop_event.wait(SETTLE_DELAY):
        return [float(freq_mhz) * 1_000_000, None, None, None, None, 'error',
                'Остановка запрошена во время выдержки'], 'error'
    try:
        inpf1 = gen.read_frequency_hz()
        fiz = sk3.read_frequency_hz()
        kf = fiz - inpf1
        tolerance = FREQ_TOLERANCE_FORMULA(inpf1)
        fph = sk3.read_if_khz()
        status, emoji = evaluate(kf, tolerance)
        log(f"   freq : {kf:+.2f} Гц, допуск ±{tolerance:.2f} Гц → {emoji}")
        return [inpf1, fiz, round(kf, 2), round(tolerance, 2), round(fph, 2), status, emoji], status
    except Exception as e:
        return [float(freq_mhz) * 1_000_000, None, None, None, None, 'error', str(e)], 'error'
