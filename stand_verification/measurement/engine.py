# -*- coding: utf-8 -*-
"""
Единый движок измерений.
Один цикл по частотам, внутри которого выполняются ВСЕ выбранные тесты.

Активные тесты передаются списком, например:
    ['freq', 'level']
    ['freq', 'level', 'am_noise', 'fm_noise', 'pm_noise']

Нереализованные тесты (am_noise, fm_noise, pm_noise) — пока пропускаются
с сообщением в лог.
"""

import threading
from copy import deepcopy
from stand_verification.config import (
    F_LIST, U_LIST_0, U_LIST, INITIAL_POWER_DBM, TEST_FREQ, TEST_LEVEL,
    TEST_AM_NOISE, TEST_FM_NOISE, TEST_PM_NOISE, NOT_IMPLEMENTED,
)
from stand_verification.measurement.frequency import measure_frequency
from stand_verification.measurement.level import measure_level
from stand_verification.models import FrequencyResult, LevelResult
from stand_verification.devices.smb100a import SMB100A
from stand_verification.devices.sk3_50 import SK350


class _StopRequested(Exception):
    """Завершить запуск через общий finally до формирования результата."""


# ============================================================
#                    ОСНОВНОЙ ДВИЖОК
# ============================================================

class MeasurementEngine:
    """
    Единый движок. Один цикл по частотам.
    Внутри каждой частоты — выбранные измерения.
    """

    def __init__(self, gen, sk3, active_tests=None, log_callback=None, stop_event=None):
        """
        :param gen: объект pyvisa-сессии генератора SMB100A
        :param sk3: объект serial.Serial для СК3-50
        :param active_tests: список идентификаторов активных тестов.
                             По умолчанию — все реализованные (freq, level).
        :param log_callback: функция f(msg: str)
        """
        self.gen = gen if isinstance(gen, SMB100A) else SMB100A(gen)
        self.sk3 = sk3 if isinstance(sk3, SK350) else SK350(sk3)
        self.log = log_callback if log_callback is not None else (lambda msg: None)
        self.stop_event = stop_event if stop_event is not None else threading.Event()

        if active_tests is None:
            active_tests = [TEST_FREQ, TEST_LEVEL]
        self.active_tests = list(active_tests)

        # Результаты по каждому тесту — свой список
        self.results = {
            TEST_FREQ: [],
            TEST_LEVEL: [],
            TEST_AM_NOISE: [],
            TEST_FM_NOISE: [],
            TEST_PM_NOISE: [],
        }

        # Общий итоговый статус (done / warn / error)
        self.final_status = 'not_started'

        # Признак, что где-то встретился warn / fail
        self._any_warn = False
        self.shutdown_success = None
        self.shutdown_error = ''
        self.termination_reason = ''
        self.diagnostics = []

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

    # --------------------------------------------------------
    #                    ИНИЦИАЛИЗАЦИЯ
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    #                    ПОДСЧЁТ ТОЧЕК
    # --------------------------------------------------------

    def _count_total_points(self, freqs):
        """Сколько всего измерений будет сделано (для прогресс-бара)."""
        total = 0
        for f_mhz in freqs:
            f_val = float(f_mhz)
            if TEST_FREQ in self.active_tests:
                total += 1
            if TEST_LEVEL in self.active_tests:
                levels = U_LIST_0 if f_val in (0.01, 0.1) else U_LIST
                total += len(levels)
            # нереализованные не считаем
        return total

    # --------------------------------------------------------
    #                    ОСНОВНОЙ ЗАПУСК
    # --------------------------------------------------------

    def run(self, freqs=None, progress_callback=None):
        """
        :param freqs: список частот (МГц). По умолчанию F_LIST.
        :param progress_callback: f(idx, total, info_str) — перед каждой точкой.
                                  Может возбудить InterruptedError для остановки.
        :return: (results_dict, final_status), results contain FrequencyResult/LevelResult.
        """
        if freqs is None:
            freqs = F_LIST

        self.results = {k: [] for k in self.results}
        self.final_status = 'not_started'
        self._any_warn = False
        self.shutdown_success = None
        self.shutdown_error = ''
        self.termination_reason = ''
        self.diagnostics = []

        total_points = self._count_total_points(freqs)
        self._planned = {
            TEST_FREQ: sum(1 for _ in freqs) if TEST_FREQ in self.active_tests else 0,
            TEST_LEVEL: sum(len(U_LIST_0 if float(f) in (0.01, 0.1) else U_LIST) for f in freqs)
                        if TEST_LEVEL in self.active_tests else 0,
        }

        self._log("─" * 50)
        self._log(f"Активные тесты: {', '.join(self.active_tests)}")
        self._log(f"Частот в цикле: {len(freqs)}. Всего измерений: {total_points}")

        # Проверяем, не выбраны ли только нереализованные тесты
        implemented = [t for t in self.active_tests if t not in NOT_IMPLEMENTED]
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
            if self._stopped():
                raise _StopRequested('Остановка запрошена')
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
                            progress_callback(point_idx, total_points, f"Частота {freq_mhz} МГц — измерение частоты")
                        except InterruptedError:
                            self.stop_event.set()
                            self.termination_reason = 'Остановка запрошена'
                            self.final_status = 'stopped'
                            break
                    row = self._measure_freq(freq_mhz)
                    self.results[TEST_FREQ].append(row)
                    if row.status == 'error':
                        if self._stopped():
                            self.termination_reason = row.comment
                            self.final_status = 'stopped'
                            break
                        failed = True
                        self.final_status = 'error'
                        self.termination_reason = row.comment
                        self._diagnose(row.comment)
                        break
                    self._any_warn |= row.status in ('warn', 'fail')
                if failed or self.final_status == 'stopped':
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
                                progress_callback(point_idx, total_points, f"Частота {freq_mhz} МГц — уровень {lv:+.0f} dBm")
                            except InterruptedError:
                                self.stop_event.set()
                                self.termination_reason = 'Остановка запрошена'
                                self.final_status = 'stopped'
                                break
                        row = self._measure_level(freq_mhz, lv)
                        self.results[TEST_LEVEL].append(row)
                        if row.status == 'error':
                            if self._stopped():
                                self.termination_reason = row.comment
                                self.final_status = 'stopped'
                                break
                            failed = True
                            self.final_status = 'error'
                            self.termination_reason = row.comment
                            self._diagnose(row.comment)
                            break
                        self._any_warn |= row.status in ('warn', 'fail')
                    if failed or self.final_status == 'stopped':
                        break
                for t in self.active_tests:
                    if t in NOT_IMPLEMENTED:
                        self._log(f"   (тест «{t}» пока в разработке — пропущен)")
            else:
                if self._stopped():
                    self.final_status = 'stopped'
                    self.termination_reason = 'Остановка запрошена'
                else:
                    self.final_status = 'warn' if self._any_warn else 'done'
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

    # --------------------------------------------------------
    #                    ИЗМЕРЕНИЕ ЧАСТОТЫ
    # --------------------------------------------------------

    def _measure_freq(self, freq_mhz) -> FrequencyResult:
        return measure_frequency(self.gen, self.sk3, self.stop_event, self._log, freq_mhz)

    # --------------------------------------------------------
    #                    ИЗМЕРЕНИЕ УРОВНЯ
    # --------------------------------------------------------

    def _measure_level(self, freq_mhz, level_dbm) -> LevelResult:
        return measure_level(self.gen, self.sk3, self.stop_event, self._log,
                             freq_mhz, level_dbm)

    # --------------------------------------------------------
    #                    СОХРАНЕНИЕ
    # --------------------------------------------------------

    def snapshot(self):
        from stand_verification.models import RunSnapshot
        return RunSnapshot(
            active_tests=tuple(self.active_tests), results=deepcopy(self.results),
            final_status=self.final_status, termination_reason=self.termination_reason,
            shutdown_success=self.shutdown_success, shutdown_error=self.shutdown_error,
            diagnostics=tuple(self.diagnostics), summary=deepcopy(self.summary()),
        )

    # --------------------------------------------------------
    #                    СВОДКА
    # --------------------------------------------------------

    def summary(self):
        """Возвращает dict со сводкой по каждому тесту."""
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
            status = ('error' if error else 'not_started' if total == 0 else
                      'incomplete' if not complete else 'warn' if warn or fail else 'done')
            out[key] = {'status': status, 'planned': planned, 'total': total,
                        'ok': ok, 'warn': warn, 'fail': fail, 'error': error}
        out['final_status'] = self.final_status
        return out
