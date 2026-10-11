"""
Драйвер измерителя нелинейных искажений С6-22.

Соединение (serial.Serial) открывается и закрывается снаружи —
класс получает уже открытую сессию.
"""

import time


class C622:
    """Операции с С6-22. Владение сессией — у вызывающего кода."""

    def __init__(self, session, delay=1.0):
        self.session = session
        self.delay = delay

    # --------------------------------------------------------
    #                    ВНУТРЕННИЕ
    # --------------------------------------------------------

    def _write(self, cmd, wait=None):
        """Отправить команду и подождать."""
        if isinstance(cmd, str):
            cmd = cmd.encode('utf-8')
        self.session.write(cmd)
        self.session.flush()
        time.sleep(self.delay if wait is None else wait)

    def _readline_str(self):
        """Прочитать строку, вернуть строку."""
        raw = self.session.readline()
        return raw.decode('utf-8', errors='ignore').strip()

    # --------------------------------------------------------
    #                    РЕЖИМ ИЗМЕРЕНИЯ НАПРЯЖЕНИЯ
    # --------------------------------------------------------

    def init_voltage_mode(self):
        """
        Привести С6-22 в исходное состояние:
        режим измерения напряжения, ручная шкала, 100 В.
        Вызывается перед всеми тестами.
        """
        self._write(b'MODE VM\n')
        self._write(b'LIMitD MAN\n')
        self._write(b'RANgeD 100V\n')

    # --------------------------------------------------------
    #                    РЕЖИМ КГ
    # --------------------------------------------------------

    def set_thd_mode(self):
        """Перевести С6-22 в режим измерения КГ (DFM, авто-пределы)."""
        self._write(b'MODE DFM\n')
        self._write(b'LIMitD AUTO\n')

    def read_thd(self):
        """
        Измерение КГ (MEASure:THD?).
        Ответ вида '0.0578PCT' или '0.0578'. Возвращает float.
        """
        self._write(b'MEASure:THD?\n', wait=2.0)
        raw = self._readline_str()
        # Убираем суффикс PCT и пробелы
        cleaned = raw.replace('PCT', '').replace('%', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f'Некорректный ответ С6-22 (THD): {raw!r}')

    def read_mod_frequency(self):
        """
        Измерение частоты модулирующего сигнала (MEASure:FREQuency?).
        Возвращает строку как есть, например '20.00HZ'.
        """
        self._write(b'MEASure:FREQuency?\n', wait=2.0)
        return self._readline_str()