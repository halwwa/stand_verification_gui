 # -*- coding: utf-8 -*-
"""
Тест «Погрешность измерения частоты входного сигнала» для СК3-50.
Логика взята из Freq_Level_Noise_.py, добавлена цветовая оценка:
  🟢 Зелёный  — |kf| <= 0.7 * tolerance
  🟡 Жёлтый   — 0.7 * tolerance < |kf| <= tolerance
  🔴 Красный  — |kf| > tolerance (тест останавливается)
"""

import time
from datetime import datetime


# ============================================================
#                    КОНСТАНТЫ
# ============================================================

# Название теста — используется в GUI и в логе
TEST_NAME = "Погрешность измерения частоты входного сигнала"

# Список частот для теста (МГц)
F_LIST = [
    '0.01', '0.1', '1', '10', '50', '100', '250', '500',
    '1000', '1500', '2000', '2500', '3000'
]

# Порог «жёлтой зоны» — доля от допуска
TOLERANCE_RATIO_WARN = 0.7

# Задержка после установки частоты (сек)
SETTLE_DELAY = 10.0

# Начальный уровень генератора (dBm) — как в исходном скрипте
INITIAL_POWER_DBM = -13


# ============================================================
#                    КЛАСС ТЕСТА
# ============================================================

class FrequencyTest:
    """
    Тест измерения частоты СК3-50.
    Порядок работы:
      0. Инициализация генератора: *RST, OUTP ON, FREQ 10 MHz, POW -13.
      1. Для каждой частоты из F_LIST:
         - устанавливаем частоту на генераторе,
         - устанавливаем уровень -13 dBm,
         - ждём установления,
         - читаем измеренную частоту с СК3-50,
         - читаем ПЧ (FREQ:INT?),
         - считаем погрешность и допуск,
         - присваиваем цвет.
      2. Если встретился 'fail' — прерываем цикл.
      3. Выключаем выход генератора: OUTP OFF.
    """

    def __init__(self, gen, sk3, log_callback=None):
        """
        :param gen: объект pyvisa-сессии генератора SMB100A.
                    Методы: .write(str), .query(str), .close()
        :param sk3: объект serial.Serial для СК3-50.
        :param log_callback: необязательная функция f(msg: str).
        """
        self.gen = gen
        self.sk3 = sk3
        self.log = log_callback if log_callback is not None else (lambda msg: None)

        self.results = []
        self.final_status = 'not_started'

    # --------------------------------------------------------
    #                    ИНИЦИАЛИЗАЦИЯ ГЕНЕРАТОРА
    # --------------------------------------------------------

    def _init_generator(self):
        """Сброс и включение выхода генератора — как в исходном скрипте."""
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
        """Выключение выхода генератора после теста."""
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
        Прогон по списку частот.
        :param freqs: список частот (МГц). По умолчанию F_LIST.
        :param progress_callback: f(idx, total, freq_mhz) — вызывается перед каждой
                                  частотой. Может возбудить InterruptedError для стопа.
        :return: (results, final_status)
        """
        if freqs is None:
            freqs = F_LIST

        self.results = []
        self.final_status = 'not_started'

        self.log("─" * 50)
        self.log(f"Запуск теста: {TEST_NAME}")
        self.log(f"Частот в списке: {len(freqs)}")

        # --- 1. Инициализация генератора ---
        try:
            self._init_generator()
        except Exception as e:
            self.log(f"❌ Не удалось инициализировать генератор: {e}")
            self.final_status = 'error'
            return self.results, self.final_status

        any_warn = False
        total = len(freqs)

        try:
            for idx, freq_mhz in enumerate(freqs, start=1):
                if progress_callback is not None:
                    progress_callback(idx, total, freq_mhz)

                self.log(f"[{idx}/{total}] Частота {freq_mhz} МГц …")

                try:
                    row = self._measure_one(freq_mhz)
                except InterruptedError:
                    raise
                except Exception as e:
                    self.log(f"❌ Ошибка связи на частоте {freq_mhz} МГц: {e}")
                    self.final_status = 'error'
                    return self.results, self.final_status

                self.results.append(row)

                kf = row[2]
                tol = row[3]
                color = row[5]
                comment = row[6]

                self.log(f"    Погрешность: {kf:+.2f} Гц, допуск: ±{tol:.2f} Гц → {comment}")

                if color == 'fail':
                    self.log(f"🔴 ПРОВАЛ на частоте {freq_mhz} МГц — тест остановлен.")
                    self.final_status = 'error'
                    return self.results, self.final_status

                if color == 'warn':
                    any_warn = True

            if any_warn:
                self.final_status = 'warn'
                self.log("🟡 Тест завершён. Есть предупреждения (жёлтая зона).")
            else:
                self.final_status = 'done'
                self.log("🟢 Тест завершён успешно. Все точки в зелёной зоне.")

            return self.results, self.final_status

        finally:
            # --- 3. Выключение выхода генератора — в любом случае ---
            self._deinit_generator()

    # --------------------------------------------------------
    #                    ИЗМЕРЕНИЕ НА ОДНОЙ ЧАСТОТЕ
    # --------------------------------------------------------

    def _measure_one(self, freq_mhz):
        """Измерение на одной частоте."""
        # 1. Установка частоты и уровня
        self.gen.write(f"FREQ {freq_mhz} MHz")
        self.gen.write(f"POW {INITIAL_POWER_DBM}")

        # 2. Пауза на установление
        time.sleep(SETTLE_DELAY)

        # 3. Читаем установленную частоту генератора (теперь query, не ask!)
        inpf_mhz = float(self.gen.query("FREQ?")) / 1_000_000
        inpf1 = float(self.gen.query("FREQ?"))

        # 4. Запрашиваем у СК3-50 измеренную частоту
        self.sk3.write(b'FREQ?\n')
        self.sk3.flush()
        raw = self.sk3.readline()
        decoded = raw.decode('utf-8', errors='ignore').strip()

        try:
            fiz = float(decoded)
        except ValueError:
            raise ValueError(f"Некорректный ответ СК3-50: {decoded!r}")

        # 5. Погрешность и допуск
        kf = fiz - inpf1
        tolerance = 5e-6 * abs(inpf1) + 1.0

        # 6. Частота ПЧ
        self.sk3.write(b'FREQ:INT?\n')
        self.sk3.flush()
        raw_if = self.sk3.readline()
        try:
            fph = float(raw_if.decode('utf-8', errors='ignore').strip()) / 1000.0
        except ValueError:
            fph = float('nan')

        # 7. Оценка
        color, comment = self._evaluate(kf, tolerance)

        time.sleep(1)

        return [inpf1, fiz, round(kf, 2), round(tolerance, 2),
                round(fph, 2), color, comment]

    # --------------------------------------------------------
    #                    ОЦЕНКА
    # --------------------------------------------------------

    @staticmethod
    def _evaluate(kf, tolerance):
        abs_kf = abs(kf)
        if abs_kf > tolerance:
            return 'fail', "🔴 Провал (вне допуска)"
        elif abs_kf > TOLERANCE_RATIO_WARN * tolerance:
            return 'warn', "🟡 Внимание (в жёлтой зоне)"
        else:
            return 'ok', "🟢 Норма"

    # --------------------------------------------------------
    #                    СОХРАНЕНИЕ
    # --------------------------------------------------------

    def save_to_excel(self, filepath, sheet_name="Частота"):
        """Сохраняет результаты в Excel."""
        import os
        import pandas as pd

        columns = ['Уст Частота, Гц', 'Изм Частота, Гц', 'Погрешность, Гц',
                   'Допуск, Гц', 'Частота ПЧ, кГц', 'Статус', 'Комментарий']
        df = pd.DataFrame(self.results, columns=columns)

        # Определяем режим: если файл уже есть — добавляем лист ('a'),
        # если нет — создаём новый ('w').
        if os.path.exists(filepath):
            mode = 'a'
        else:
            mode = 'w'

        kwargs = {'engine': 'openpyxl', 'mode': mode}
        if mode == 'a':
            kwargs['if_sheet_exists'] = 'replace'

        with pd.ExcelWriter(filepath, **kwargs) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        self.log(f"Результаты сохранены: {filepath}")

    def summary(self):
        total = len(self.results)
        ok = sum(1 for r in self.results if r[5] == 'ok')
        warn = sum(1 for r in self.results if r[5] == 'warn')
        fail = sum(1 for r in self.results if r[5] == 'fail')
        return {'total': total, 'ok': ok, 'warn': warn, 'fail': fail,
                'final_status': self.final_status}
