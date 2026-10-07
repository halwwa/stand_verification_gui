from stand_verification.config import SETTLE_DELAY
from stand_verification.measurement.tolerances import FREQ_TOLERANCE_FORMULA, evaluate
from stand_verification.models import FrequencyResult


def measure_frequency(gen, sk3, stop_event, log, freq_mhz) -> FrequencyResult:
    if stop_event.wait(SETTLE_DELAY):
        return FrequencyResult(
            reference_frequency_hz=float(freq_mhz) * 1_000_000,
            measured_frequency_hz=None, error_hz=None, tolerance_hz=None,
            if_frequency_khz=None, status='error',
            comment='Остановка запрошена во время выдержки',
        )
    try:
        inpf1 = gen.read_frequency_hz()
        fiz = sk3.read_frequency_hz()
        kf = fiz - inpf1
        tolerance = FREQ_TOLERANCE_FORMULA(inpf1)
        fph = sk3.read_if_khz()
        status, emoji = evaluate(kf, tolerance)
        log(f"   freq : {kf:+.2f} Гц, допуск ±{tolerance:.2f} Гц → {emoji}")
        return FrequencyResult(
            reference_frequency_hz=inpf1, measured_frequency_hz=fiz,
            error_hz=round(kf, 2), tolerance_hz=round(tolerance, 2),
            if_frequency_khz=round(fph, 2), status=status, comment=emoji,
        )
    except Exception as e:
        return FrequencyResult(
            reference_frequency_hz=float(freq_mhz) * 1_000_000,
            measured_frequency_hz=None, error_hz=None, tolerance_hz=None,
            if_frequency_khz=None, status='error', comment=str(e),
        )
