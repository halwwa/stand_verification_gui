# -*- coding: utf-8 -*-
"""
Тест «Погрешность измерения уровня» для СК3-50.
Логика взята из Freq_Level_Noise_.py (блок «Измерение погрешности Уровня»).
Цветовая оценка:
  🟢 Зелёный  — |ku| <= 0.7 * tolerance
  🟡 Жёлтый   — 0.7 * tolerance < |ku| <= tolerance
  🔴 Красный  — |ku| > tolerance (тест останавливается)
"""

import time


# ============================================================
#                    КОНСТАНТЫ
# ============================================================

# Название теста — используется в GUI и в логе
TEST_NAME = "Погрешность измерения уровня"

# Список частот для теста (МГц) — тот же, что в FrequencyTest
F_LIST = [
    '0.01', '0.1', '1', '10', '50', '100', '250', '500',
    '1000', '1500', '2000', '2500', '3000'
]

# Список уровней (dBm):
# для частот 0.01 и 0.1 МГц — только -13 и 0
U_LIST_0 = [-13.0, 0.0]

# для всех остальных частот — -13, 0, +13
U_LIST = [-13.0, 0.0, 13.0]

# Допуск по уровню — ±1 дБ
TOLERANCE_DB = 1.0

# Порог «жёлтой зоны» — доля от допуска
TOLERANCE_RATIO_WARN = 0.7

# Задержка после установки уровня (сек) — как в исходном скрипте
SETTLE_DELAY = 6.0

# Начальный уровень генератора (dBm)
INITIAL_POWER_DBM = -13


# ============================================================
#                    КЛАСС ТЕСТА
# ============================================================

class LevelTest:
    """
    Тест погрешности измерения уровня СК3-50.
    Для каждой частоты из F_LIST и каждого уровня из U_LIST:
      - устанавливаем уровень на генераторе (POW <un>),
      - ждём установления (6 сек),
      - читаем измеренный уровень с СК3-50 (POW?),
      - считаем погрешность ku = измеренный - заданный (дБ),
      - допуск ±1 дБ,
      - цвет (ok/warn/fail).
    При 'fail' — останавливаемся.
    """

    def __init__(self, gen, sk3, log_callback=None):
        self.gen = gen
        self.sk3 = sk3
        self.log = log_callback if log_callback is not None else (lambda msg: None)

        # Результаты: [freq_mhz, level_set_dbm, level_meas_dbm,
        #              error_db, tolerance_db, status, comment]
        self.results = []
        self.final_status = 'not_started'

    # --------------------------------------------------------
    #                    ИНИЦИАЛИЗАЦИЯ
    # --------------------------------------------------------

    def _init_generator(self):
        self.log("Инициализация генератора SMB100A…")
        try:
            self.gen.write('*RST')
            self.gen.write('OUTP ON')
            self.gen.write('FREQ 10 MHz')
            self.gen.write(f'POW {INITIAL_POWER_DBM}')
            time.sleep(1)
            self.log("Генератор: *RST, OUTP ON, FREQ 10 MHz, POW -13 dBm.")
        except Exception as e:
            self.log(f"⚠ Ошибка инициализации генератора: {e}")
            raise

    def _deinit_generator(self):
        self.log("Выключение выхода генератора (OUTP OFF)…")
        try:
            self.gen.write('OUTP OFF')
        except Exception as e:
            self.log(f"⚠ Не удалось выключить выход генератора: {e}")

    # --------------------------------------------------------
    #                    ОСНОВНОЙ ЦИКЛ
    # --------------------------------------------------------

    def run(self, freqs=None, progress_callback=None):
        """
        Прогон по всем частотам и уровням.
        :param freqs: список частот в МГц. По умолчанию F_LIST.
        :param progress_callback: f(idx, total, info_str) — вызывается перед
                                  каждой точкой (частота+уровень).
        :return: (results, final_status)
        """
        if freqs is None:
            freqs = F_LIST

        self.results = []
        self.final_status = 'not_started'

        # Считаем общее количество точек
        plan = []   # список кортежей (freq_mhz, level)
        for f_mhz in freqs:
            f_val = float(f_mhz)
            if f_val in (0.01, 0.1):
                levels = U_LIST_0
            else:
                levels = U_LIST
            for lv in levels:
                plan.append((f_mhz, lv))

        total = len(plan)

        self.log("─" * 50)
        self.log(f"Запуск теста: {TEST_NAME}")
        self.log(f"Частот: {len(freqs)}, всего точек: {total}")

        # Инициализация генератора
        try:
            self._init_generator()
        except Exception as e:
            self.log(f"❌ Не удалось инициализировать генератор: {e}")
            self.final_status = 'error'
            return self.results, self.final_status

        any_warn = False

        try:
            for idx, (freq_mhz, level) in enumerate(plan, start=1):
                info = f"{freq_mhz} МГц / {level:+.0f} dBm"

                if progress_callback is not None:
                    progress_callback(idx, total, info)

                self.log(f"[{idx}/{total}] {info} …")

                try:
                    row = self._measure_one(freq_mhz, level)
                except InterruptedError:
                    raise
                except Exception as e:
                    self.log(f"❌ Ошибка на {info}: {e}")
                    self.final_status = 'error'
                    return self.results, self.final_status

                self.results.append(row)

                ku = row[3]
                tol = row[4]
                color = row[5]
                comment = row[6]

                self.log(f"    Погрешность: {ku:+.2f} дБ, допуск: ±{tol:.2f} дБ → {comment}")

                if color == 'fail':
                    self.log(f"🔴 ПРОВАЛ на {info} — тест остановлен.")
                    self.final_status = 'error'
                    return self.results, self.final_status

                if color == 'warn':
                    any_warn = True

            if any_warn:
                self.final_status = 'warn'
                self.log("🟡 Тест завершён. Есть предупреждения.")
            else:
                self.final_status = 'done'
                self.log("🟢 Тест завершён успешно. Все точки в норме.")

            return self.results, self.final_status

        finally:
            self._deinit_generator()

    # --------------------------------------------------------
    #                    ИЗМЕРЕНИЕ ОДНОЙ ТОЧКИ
    # --------------------------------------------------------

    def _measure_one(self, freq_mhz, level_dbm):
        """Измерение на одной частоте и одном уровне."""
        # 1. Установка частоты
        self.gen.write(f"FREQ {freq_mhz} MHz")

        # 2. Установка уровня
        self.gen.write(f"POW {level_dbm}")

        # 3. Пауза
        time.sleep(SETTLE_DELAY)

        # 4. Запрос измеренного уровня у СК3-50
        self.sk3.write(b'POW?\n')
        self.sk3.flush()
        raw = self.sk3.readline()
        decoded = raw.decode('utf-8', errors='ignore').strip()

        try:
            oup = float(decoded)
        except ValueError:
            raise ValueError(f"Некорректный ответ СК3-50 (POW?): {decoded!r}")

        # 5. Погрешность в дБ
        ku = oup - level_dbm

        # 6. Оценка
        color, comment = self._evaluate(ku, TOLERANCE_DB)

        time.sleep(1)

        return [float(freq_mhz), level_dbm, round(oup, 2),
                round(ku, 2), TOLERANCE_DB, color, comment]

    # --------------------------------------------------------
    #                    ОЦЕНКА
    # --------------------------------------------------------

    @staticmethod
    def _evaluate(ku, tolerance):
        abs_ku = abs(ku)
        if abs_ku > tolerance:
            return 'fail', "🔴 Провал (вне допуска)"
        elif abs_ku > TOLERANCE_RATIO_WARN * tolerance:
            return 'warn', "🟡 Внимание (в жёлтой зоне)"
        else:
            return 'ok', "🟢 Норма"

    # --------------------------------------------------------
    #                    СОХРАНЕНИЕ
    # --------------------------------------------------------

    def save_to_excel(self, filepath, sheet_name="Уровень"):
        """Сохраняет результаты в Excel."""
        import os
        import pandas as pd

        columns = ['Частота, МГц', 'Заданный уровень, дБм', 'Измеренный уровень, дБм',
                   'Погрешность, дБ', 'Допуск, дБ', 'Статус', 'Комментарий']
        df = pd.DataFrame(self.results, columns=columns)

        if os.path.exists(filepath):
            mode = 'a'
            kwargs = {'engine': 'openpyxl', 'mode': mode, 'if_sheet_exists': 'replace'}
        else:
            mode = 'w'
            kwargs = {'engine': 'openpyxl', 'mode': mode}

        with pd.ExcelWriter(filepath, **kwargs) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        self.log(f"Результаты сохранены: {filepath} (лист «{sheet_name}»)")

    def summary(self):
        total = len(self.results)
        ok = sum(1 for r in self.results if r[5] == 'ok')
        warn = sum(1 for r in self.results if r[5] == 'warn')
        fail = sum(1 for r in self.results if r[5] == 'fail')
        return {'total': total, 'ok': ok, 'warn': warn, 'fail': fail,
                'final_status': self.final_status}
