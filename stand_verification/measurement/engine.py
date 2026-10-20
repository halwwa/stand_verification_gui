# -*- coding: utf-8 -*-
"""
Единый движок измерений.

Режимы:
  1) Цикл по частотам — тесты 1–5.
  2) После цикла — Тест 6, Тест 7, Тест 8, Тест 10 (отдельные прогоны).
"""

import threading
from copy import deepcopy

from stand_verification.config import (
    F_LIST, U_LIST_0, U_LIST, INITIAL_POWER_DBM, NOISE_POWER_DBM,
    TEST_FREQ, TEST_LEVEL, TEST_AM_NOISE, TEST_FM_NOISE, TEST_PM_NOISE,
    TEST_AM_FM_TRANSITION, TEST_THD_AM, TEST_THD_FM, TEST_FM_LINEARITY,
    TEST_FM_DEVIATION, TEST_AM_PEAKS,
    NOT_IMPLEMENTED, SKIP_FOR_FM_PM_MHZ,
)
from stand_verification.measurement.frequency import measure_frequency
from stand_verification.measurement.level import measure_level
from stand_verification.measurement.am_noise import measure_am_noise
from stand_verification.measurement.fm_noise import measure_fm_noise
from stand_verification.measurement.pm_noise import measure_pm_noise
from stand_verification.measurement.am_fm_transition import run_transition
from stand_verification.measurement.thd_am import run_thd_am
from stand_verification.measurement.thd_fm import run_thd_fm
from stand_verification.measurement.fm_linearity import run_fm_linearity
from stand_verification.measurement.fm_deviation import run_fm_deviation
from stand_verification.measurement.am_peaks import run_am_peaks
from stand_verification.models import (
    FrequencyResult, LevelResult, NoiseResult,
    TransitionResult, ThdAmResult, ThdFmResult,
    LinearityResult, DeviationResult, KamResult,
)
from stand_verification.devices.smb100a import SMB100A
from stand_verification.devices.sk3_50 import SK350
from stand_verification.devices.c6_22 import C622


class _StopRequested(Exception):
    """Завершить запуск через общий finally."""


class MeasurementEngine:
    """Единый движок измерений."""

    def __init__(self, gen, sk3, active_tests=None, c6=None,
                 log_callback=None, stop_event=None, confirm_callback=None):
        self.gen = gen if isinstance(gen, SMB100A) else SMB100A(gen)
        self.sk3 = sk3 if isinstance(sk3, SK350) else SK350(sk3)
        if c6 is None:
            self.c6 = None
        else:
            self.c6 = c6 if isinstance(c6, C622) else C622(c6)

        self.log = log_callback if log_callback is not None else (lambda msg: None)
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self.confirm_callback = confirm_callback

        if active_tests is None:
            active_tests = [TEST_FREQ, TEST_LEVEL]
        self.active_tests = list(active_tests)

        self.results = {
            TEST_FREQ: [],
            TEST_LEVEL: [],
            TEST_AM_NOISE: [],
            TEST_FM_NOISE: [],
            TEST_PM_NOISE: [],
            TEST_AM_FM_TRANSITION: [],
            TEST_THD_AM: [],
            TEST_THD_FM: [],
            TEST_FM_LINEARITY: [],
            TEST_FM_DEVIATION: [],
            TEST_AM_PEAKS: [],
        }

        self.final_status = 'not_started'
        self._any_warn = False
        self._any_fail = False
        self.shutdown_success = None
        self.shutdown_error = ''
        self.termination_reason = ''
        self.diagnostics = []
        self._planned = {}

    # ---------- утилиты ----------

    def _log(self, message):
        try:
            self.log(message)
        except Exception:
            pass

    def _diagnose(self, message):
        self.diagnostics.append(str(message))
        self._log(message)

    def _stopped(self):
        return self.stop_event.is_set()

    def _init_generator(self):
        self._log("Инициализация генератора SMB100A…")
        self.gen.reset()
        if self._stopped():
            return
        self.gen.output_on()
        self.gen.set_frequency_mhz(10)
        self.gen.set_power_dbm(INITIAL_POWER_DBM)
        self.stop_event.wait(1)
        self._log("Генератор: *RST, OUTP ON, FREQ 10 MHz, POW -13 dBm.")

    def _deinit_generator(self):
        self._log("Выключение выхода генератора (OUTP OFF)…")
        try:
            self.gen.output_off()
            self.shutdown_success = True
            self.shutdown_error = ''
            return True, ''
        except Exception as e:
            self.shutdown_success = False
            self.shutdown_error = str(e)
            self._diagnose(f"Ошибка OUTP OFF: {e}")
            return False, str(e)

    def _init_c6_if_needed(self):
        needs_c6 = (TEST_THD_AM in self.active_tests or
                    TEST_THD_FM in self.active_tests)
        if not needs_c6:
            return
        if self.c6 is None:
            self._log("⚠ С6-22 не подключён — тесты 7 и 8 будут пропущены.")
            return
        try:
            self._log("Инициализация С6-22: MODE VM, LIMitD MAN, RANgeD 100V…")
            self.c6.init_voltage_mode()
        except Exception as e:
            self._diagnose(f"Ошибка инициализации С6-22: {e}")

    def _restore_c6(self):
        if self.c6 is None:
            return
        try:
            self.c6.init_voltage_mode()
            self._log("С6-22 возвращён в режим VM/MAN/100V.")
        except Exception as e:
            self._diagnose(f"Ошибка возврата С6-22: {e}")

    def _count_total_points(self, freqs):
        total = 0
        for f_mhz in freqs:
            f_val = float(f_mhz)
            if TEST_FREQ in self.active_tests:
                total += 1
            if TEST_LEVEL in self.active_tests:
                levels = U_LIST_0 if f_val in (0.01, 0.1) else U_LIST
                total += len(levels)
            if TEST_AM_NOISE in self.active_tests:
                total += 1 if f_val in (0.01, 0.1) else 5
            if TEST_FM_NOISE in self.active_tests:
                if f_val not in SKIP_FOR_FM_PM_MHZ:
                    total += 6 if f_val == 1 else 5
            if TEST_PM_NOISE in self.active_tests:
                if f_val not in SKIP_FOR_FM_PM_MHZ:
                    total += 3
        if TEST_AM_FM_TRANSITION in self.active_tests:
            total += 2
        if TEST_THD_AM in self.active_tests:
            total += 8
        if TEST_THD_FM in self.active_tests:
            total += 18
        if TEST_FM_LINEARITY in self.active_tests:
            total += 10
        if TEST_FM_DEVIATION in self.active_tests:
            total += 28  
        if TEST_AM_PEAKS in self.active_tests:
            total += 12   
        return total

    # ========================================================
    #                    ОСНОВНОЙ ЗАПУСК
    # ========================================================

    def run(self, freqs=None, progress_callback=None):
        if freqs is None:
            freqs = F_LIST

        self.results = {k: [] for k in self.results}
        self.final_status = 'not_started'
        self._any_warn = False
        self._any_fail = False
        self.shutdown_success = None
        self.shutdown_error = ''
        self.termination_reason = ''
        self.diagnostics = []

        total_points = self._count_total_points(freqs)

        self._planned = {
            TEST_FREQ: sum(1 for _ in freqs) if TEST_FREQ in self.active_tests else 0,
            TEST_LEVEL: sum(len(U_LIST_0 if float(f) in (0.01, 0.1) else U_LIST)
                            for f in freqs)
                        if TEST_LEVEL in self.active_tests else 0,
            TEST_AM_NOISE: sum((1 if float(f) in (0.01, 0.1) else 5) for f in freqs)
                           if TEST_AM_NOISE in self.active_tests else 0,
            TEST_FM_NOISE: sum(
                ((6 if float(f) == 1 else 5) if float(f) not in SKIP_FOR_FM_PM_MHZ else 0)
                for f in freqs
            ) if TEST_FM_NOISE in self.active_tests else 0,
            TEST_PM_NOISE: sum(
                (3 if float(f) not in SKIP_FOR_FM_PM_MHZ else 0) for f in freqs
            ) if TEST_PM_NOISE in self.active_tests else 0,
            TEST_AM_FM_TRANSITION: 2 if TEST_AM_FM_TRANSITION in self.active_tests else 0,
            TEST_THD_AM: 8 if TEST_THD_AM in self.active_tests else 0,
            TEST_THD_FM: 18 if TEST_THD_FM in self.active_tests else 0,
            TEST_FM_LINEARITY: 10 if TEST_FM_LINEARITY in self.active_tests else 0,
            TEST_FM_DEVIATION: 28 if TEST_FM_DEVIATION in self.active_tests else 0,
            TEST_AM_PEAKS: 12 if TEST_AM_PEAKS in self.active_tests else 0,
        }

        self._log("─" * 50)
        self._log(f"Активные тесты: {', '.join(self.active_tests)}")
        self._log(f"Всего точек: {total_points}")

        implemented = [t for t in self.active_tests
                       if t in self.results and t not in NOT_IMPLEMENTED]
        if not implemented:
            self._diagnose("Не выбрано ни одного реализованного теста.")
            self.final_status = 'error'
            return self.results, self.final_status

        init_started = False
        failed = False
        point_idx = 0

        try:
            if self._stopped():
                raise _StopRequested('Остановка запрошена до инициализации')
            init_started = True
            self._init_generator()
            self._init_c6_if_needed()
            if self._stopped():
                raise _StopRequested('Остановка запрошена')

            # =================== ЦИКЛ ПО ЧАСТОТАМ ===================
            for freq_i, freq_mhz in enumerate(freqs, start=1):
                if self._stopped():
                    self.termination_reason = 'Остановка запрошена'
                    self.final_status = 'stopped'
                    break

                self._log(f"─── Частота {freq_mhz} МГц ({freq_i}/{len(freqs)}) ───")

                try:
                    self.gen.set_frequency_mhz(freq_mhz)
                except Exception as e:
                    self._diagnose(f"Ошибка установки частоты {freq_mhz} МГц: {e}")
                    self.termination_reason = self.diagnostics[-1]
                    self.final_status = 'error'
                    failed = True
                    break

                f_val = float(freq_mhz)

                if TEST_FREQ in self.active_tests:
                    if self._stopped():
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                        break
                    point_idx += 1
                    if progress_callback:
                        try:
                            progress_callback(point_idx, total_points,
                                              f"Частота {freq_mhz} МГц — измерение частоты")
                        except InterruptedError:
                            self.stop_event.set()
                            self.termination_reason = 'Остановка запрошена'
                            self.final_status = 'stopped'
                            break
                    row = self._measure_freq(freq_mhz)
                    self.results[TEST_FREQ].append(row)
                    action = self._handle_row_status(row, 'частоты')
                    if action == 'break':
                        break
                    if action == 'failed':
                        failed = True
                        break
                if failed or self.final_status in ('stopped', 'error'):
                    break

                if TEST_LEVEL in self.active_tests:
                    levels = U_LIST_0 if f_val in (0.01, 0.1) else U_LIST
                    for lv in levels:
                        if self._stopped():
                            self.termination_reason = 'Остановка запрошена'
                            self.final_status = 'stopped'
                            break
                        point_idx += 1
                        if progress_callback:
                            try:
                                progress_callback(point_idx, total_points,
                                                  f"Частота {freq_mhz} МГц — уровень {lv:+.0f} dBm")
                            except InterruptedError:
                                self.stop_event.set()
                                self.termination_reason = 'Остановка запрошена'
                                self.final_status = 'stopped'
                                break
                        row = self._measure_level(freq_mhz, lv)
                        self.results[TEST_LEVEL].append(row)
                        action = self._handle_row_status(row, 'уровня')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break
                    if failed or self.final_status in ('stopped', 'error'):
                        break

                if TEST_AM_NOISE in self.active_tests:
                    if self._stopped():
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                        break
                    try:
                        self.gen.set_power_dbm(NOISE_POWER_DBM)
                    except Exception as e:
                        self._diagnose(f"Ошибка POW 0 для АМ шума: {e}")
                    point_idx += 1
                    if progress_callback:
                        try:
                            progress_callback(point_idx, total_points,
                                              f"Частота {freq_mhz} МГц — АМ шум")
                        except InterruptedError:
                            self.stop_event.set()
                            self.termination_reason = 'Остановка запрошена'
                            self.final_status = 'stopped'
                            break
                    noise_rows = self._measure_am_noise(freq_mhz)
                    for nr in noise_rows:
                        self.results[TEST_AM_NOISE].append(nr)
                        action = self._handle_row_status(nr, 'АМ шума')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break
                    if failed or self.final_status in ('stopped', 'error'):
                        break

                if TEST_FM_NOISE in self.active_tests and f_val not in SKIP_FOR_FM_PM_MHZ:
                    if self._stopped():
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                        break
                    try:
                        self.gen.set_power_dbm(NOISE_POWER_DBM)
                    except Exception:
                        pass
                    point_idx += 1
                    if progress_callback:
                        try:
                            progress_callback(point_idx, total_points,
                                              f"Частота {freq_mhz} МГц — ЧМ шум")
                        except InterruptedError:
                            self.stop_event.set()
                            self.termination_reason = 'Остановка запрошена'
                            self.final_status = 'stopped'
                            break
                    noise_rows = self._measure_fm_noise(freq_mhz)
                    for nr in noise_rows:
                        self.results[TEST_FM_NOISE].append(nr)
                        action = self._handle_row_status(nr, 'ЧМ шума')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break
                    if failed or self.final_status in ('stopped', 'error'):
                        break

                if TEST_PM_NOISE in self.active_tests and f_val not in SKIP_FOR_FM_PM_MHZ:
                    if self._stopped():
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                        break
                    try:
                        self.gen.set_power_dbm(NOISE_POWER_DBM)
                    except Exception:
                        pass
                    point_idx += 1
                    if progress_callback:
                        try:
                            progress_callback(point_idx, total_points,
                                              f"Частота {freq_mhz} МГц — ФМ шум")
                        except InterruptedError:
                            self.stop_event.set()
                            self.termination_reason = 'Остановка запрошена'
                            self.final_status = 'stopped'
                            break
                    noise_rows = self._measure_pm_noise(freq_mhz)
                    for nr in noise_rows:
                        self.results[TEST_PM_NOISE].append(nr)
                        action = self._handle_row_status(nr, 'ФМ шума')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break
                    if failed or self.final_status in ('stopped', 'error'):
                        break

            # =================== ТЕСТ 6 ===================
            if (not failed and self.final_status not in ('stopped', 'error')
                    and TEST_AM_FM_TRANSITION in self.active_tests
                    and not self._stopped()):
                point_idx += 1
                if progress_callback:
                    try:
                        progress_callback(point_idx, total_points, "Тест 6 — Переход АМ↔ЧМ")
                    except InterruptedError:
                        self.stop_event.set()
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                if not self._stopped():
                    trans_rows = run_transition(
                        self.gen, self.sk3, self.stop_event, self._log,
                        confirm_callback=self.confirm_callback,
                    )
                    for tr in trans_rows:
                        self.results[TEST_AM_FM_TRANSITION].append(tr)
                        action = self._handle_row_status(tr, 'перехода АМ↔ЧМ')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break

            # =================== ТЕСТ 7 ===================
            if (not failed and self.final_status not in ('stopped', 'error')
                    and TEST_THD_AM in self.active_tests
                    and not self._stopped()):
                point_idx += 1
                if progress_callback:
                    try:
                        progress_callback(point_idx, total_points, "Тест 7 — КГ АМ")
                    except InterruptedError:
                        self.stop_event.set()
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                if not self._stopped():
                    thd_rows = run_thd_am(
                        self.gen, self.sk3, self.c6,
                        self.stop_event, self._log,
                        confirm_callback=self.confirm_callback,
                    )
                    for tr in thd_rows:
                        self.results[TEST_THD_AM].append(tr)
                        action = self._handle_row_status(tr, 'КГ АМ')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break
                self._restore_c6()

            # =================== ТЕСТ 8 ===================
            if (not failed and self.final_status not in ('stopped', 'error')
                    and TEST_THD_FM in self.active_tests
                    and not self._stopped()):
                point_idx += 1
                if progress_callback:
                    try:
                        progress_callback(point_idx, total_points, "Тест 8 — КГ ЧМ")
                    except InterruptedError:
                        self.stop_event.set()
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                if not self._stopped():
                    thd_rows = run_thd_fm(
                        self.gen, self.sk3, self.c6,
                        self.stop_event, self._log,
                        confirm_callback=self.confirm_callback,
                    )
                    for tr in thd_rows:
                        self.results[TEST_THD_FM].append(tr)
                        action = self._handle_row_status(tr, 'КГ ЧМ')
                        if action == 'break':
                            break
                        if action == 'failed':
                            failed = True
                            break
                self._restore_c6()

                        # =================== ТЕСТ 9 ===================
            if (not failed and self.final_status not in ('stopped', 'error')
                    and TEST_FM_LINEARITY in self.active_tests
                    and not self._stopped()):
                point_idx += 1
                if progress_callback:
                    try:
                        progress_callback(point_idx, total_points,
                                          "Тест 9 — Линейность шкал ЧМ")
                    except InterruptedError:
                        self.stop_event.set()
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                if not self._stopped():
                    try:
                        lin_rows = run_fm_linearity(
                            self.gen, self.sk3,
                            self.stop_event, self._log,
                            confirm_callback=self.confirm_callback,
                        )
                        for lr in lin_rows:
                            self.results[TEST_FM_LINEARITY].append(lr)
                            action = self._handle_row_status(lr, 'линейности ЧМ')
                            if action == 'break':
                                break
                            if action == 'failed':
                                failed = True
                                break
                    except RuntimeError as e:
                        self._diagnose(f"Тест 9: {e}")
                        self.final_status = 'error'
                        self.termination_reason = str(e)
                        failed = True

            # =================== ТЕСТ 10 ===================
            if (not failed and self.final_status not in ('stopped', 'error')
                    and TEST_FM_DEVIATION in self.active_tests
                    and not self._stopped()):
                point_idx += 1
                if progress_callback:
                    try:
                        progress_callback(point_idx, total_points,
                                          "Тест 10 — Погрешность девиации ЧМ")
                    except InterruptedError:
                        self.stop_event.set()
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                if not self._stopped():
                    try:
                        dev_rows = run_fm_deviation(
                            self.gen, self.sk3,
                            self.stop_event, self._log,
                            confirm_callback=self.confirm_callback,
                        )
                        for dr in dev_rows:
                            self.results[TEST_FM_DEVIATION].append(dr)
                            action = self._handle_row_status(dr, 'девиации ЧМ')
                            if action == 'break':
                                break
                            if action == 'failed':
                                failed = True
                                break
                    except RuntimeError as e:
                        # Калибровка не удалась — тест помечен как error
                        self._diagnose(f"Тест 10: {e}")
                        self.final_status = 'error'
                        self.termination_reason = str(e)
                        failed = True

                        # =================== ТЕСТ 11 ===================
            if (not failed and self.final_status not in ('stopped', 'error')
                    and TEST_AM_PEAKS in self.active_tests
                    and not self._stopped()):
                point_idx += 1
                if progress_callback:
                    try:
                        progress_callback(point_idx, total_points,
                                          "Тест 11 — Погрешность Кам (АМ)")
                    except InterruptedError:
                        self.stop_event.set()
                        self.termination_reason = 'Остановка запрошена'
                        self.final_status = 'stopped'
                if not self._stopped():
                    try:
                        kam_rows = run_am_peaks(
                            self.gen, self.sk3,
                            self.stop_event, self._log,
                            confirm_callback=self.confirm_callback,
                        )
                        for kr in kam_rows:
                            self.results[TEST_AM_PEAKS].append(kr)
                            action = self._handle_row_status(kr, 'Кам АМ')
                            if action == 'break':
                                break
                            if action == 'failed':
                                failed = True
                                break
                    except RuntimeError as e:
                        self._diagnose(f"Тест 11: {e}")
                        self.final_status = 'error'
                        self.termination_reason = str(e)
                        failed = True
                        
            # =================== ФИНАЛИЗАЦИЯ ===================
            if not failed and self.final_status not in ('stopped', 'error'):
                if self._stopped():
                    self.final_status = 'stopped'
                    self.termination_reason = 'Остановка запрошена'
                elif self._any_warn:
                    self.final_status = 'warn'
                    self.termination_reason = (
                        'Измерения завершены; есть точки за пределами допуска'
                        if self._any_fail else
                        'Все запланированные измерения завершены')
                else:
                    self.final_status = 'done'
                    self.termination_reason = 'Все запланированные измерения завершены'

        except _StopRequested as e:
            self.termination_reason = str(e)
            self.final_status = 'stopped'
        except Exception as e:
            failed = True
            self.final_status = 'error'
            self.termination_reason = f"Неожиданная ошибка: {e}"
            self._diagnose(self.termination_reason)
        finally:
            if init_started:
                self._deinit_generator()
            if self.shutdown_success is False:
                self.final_status = 'error'
            if self.final_status == 'not_started':
                self.final_status = 'error'

        return self.results, self.final_status

    # ---------- обработка статуса ----------

    def _handle_row_status(self, row, label):
        if row.status == 'error':
            if self._stopped():
                self.termination_reason = row.comment
                self.final_status = 'stopped'
                return 'break'
            self.final_status = 'error'
            self.termination_reason = row.comment
            self._diagnose(row.comment)
            return 'failed'
        if row.status == 'fail':
            if 'остановлено оператором' in (row.comment or ''):
                self.termination_reason = f'Остановлено оператором при провале {label}'
                self.final_status = 'error'
                return 'break'
            self._any_fail = True
        self._any_warn |= row.status in ('warn', 'fail')
        return 'ok'

    # ---------- измерения ----------

    def _measure_freq(self, freq_mhz):
        return measure_frequency(self.gen, self.sk3, self.stop_event, self._log,
                                 freq_mhz, confirm_callback=self.confirm_callback)

    def _measure_level(self, freq_mhz, level_dbm):
        return measure_level(self.gen, self.sk3, self.stop_event, self._log,
                             freq_mhz, level_dbm,
                             confirm_callback=self.confirm_callback)

    def _measure_am_noise(self, freq_mhz):
        return measure_am_noise(self.gen, self.sk3, self.stop_event, self._log,
                                freq_mhz, confirm_callback=self.confirm_callback)

    def _measure_fm_noise(self, freq_mhz):
        return measure_fm_noise(self.gen, self.sk3, self.stop_event, self._log,
                                freq_mhz, confirm_callback=self.confirm_callback)

    def _measure_pm_noise(self, freq_mhz):
        return measure_pm_noise(self.gen, self.sk3, self.stop_event, self._log,
                                freq_mhz, confirm_callback=self.confirm_callback)

    # ---------- снимок / сводка ----------

    def snapshot(self):
        from stand_verification.models import RunSnapshot
        return RunSnapshot(
            active_tests=tuple(self.active_tests),
            results=deepcopy(self.results),
            final_status=self.final_status,
            termination_reason=self.termination_reason,
            shutdown_success=self.shutdown_success,
            shutdown_error=self.shutdown_error,
            diagnostics=tuple(self.diagnostics),
            summary=deepcopy(self.summary()),
        )

    def summary(self):
        out = {}
        for key, rows in self.results.items():
            if key not in self.active_tests or key in NOT_IMPLEMENTED:
                continue
            planned = getattr(self, '_planned', {}).get(key, 0)
            total = len(rows)
            ok = sum(1 for r in rows if r.status == 'ok')
            warn = sum(1 for r in rows if r.status == 'warn')
            fail = sum(1 for r in rows if r.status == 'fail')
            error = sum(1 for r in rows if r.status == 'error')
            complete = total == planned and error == 0 and fail == 0
            status = ('error' if error else
                      'not_started' if total == 0 else
                      'incomplete' if not complete else
                      'warn' if warn or fail else
                      'done')
            out[key] = {'status': status, 'planned': planned, 'total': total,
                        'ok': ok, 'warn': warn, 'fail': fail, 'error': error}
        out['final_status'] = self.final_status
        return out