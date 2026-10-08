class SK350:
    """SK3-50 request/decode operations; connection ownership stays with caller."""

    def __init__(self, session):
        self.session = session

    # --------------------------------------------------------
    #                    Частота и уровень
    # --------------------------------------------------------

    def _read_float(self, command):
        self.session.write(command)
        self.session.flush()
        return float(self.session.readline().decode('utf-8', errors='ignore').strip())

    def read_frequency_hz(self):
        return self._read_float(b'FREQ?\n')

    def read_if_khz(self):
        self.session.write(b'FREQ:INT?\n')
        self.session.flush()
        raw = self.session.readline()
        try:
            return float(raw.decode('utf-8', errors='ignore').strip()) / 1000.0
        except ValueError as e:
            raise ValueError(f"Некорректный разбор частоты ПЧ: {e}")

    def read_power_dbm(self):
        return self._read_float(b'POW?\n')

    # --------------------------------------------------------
    #                    Режимы модуляции
    # --------------------------------------------------------

    def set_mode_am(self):
        self.session.write(b'CONF:MODE AM\n')
        self.session.flush()

    def set_mode_fm(self):
        self.session.write(b'CONF:MODE FM\n')
        self.session.flush()

    def set_mode_pm(self):
        self.session.write(b'CONF:MODE PM\n')
        self.session.flush()

    # --------------------------------------------------------
    #                    Фильтры ФВЧ / ФНЧ
    # --------------------------------------------------------

    def set_filter_hp_khz(self, value_khz):
        """
        Установка ФВЧ (HPAS). value_khz — например, 0.3 или 0.02.
        Формат команды как в старом скрипте: 'CONF:INP:FILT:HPAS 0.3kHz'
        Для 20 Гц — без 'kHz'.
        """
        if value_khz >= 1:
            cmd = f'CONF:INP:FILT:HPAS {value_khz:g}kHz\n'
        else:
            # 0.3 кГц → 300 Гц? В старом скрипте: 'HPAS 0.3kHz'.
            # Оставляем как есть — формат с 'kHz'.
            cmd = f'CONF:INP:FILT:HPAS {value_khz:g}kHz\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    def set_filter_hp_hz(self, value_hz):
        """Установка ФВЧ в герцах (например, 20 Гц)."""
        cmd = f'CONF:INP:FILT:HPAS {value_hz:g}\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    def set_filter_lp_khz(self, value_khz):
        """Установка ФНЧ (LPAS) в кГц."""
        cmd = f'CONF:INP:FILT:LPAS {value_khz:g}kHz\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    # --------------------------------------------------------
    #                    Чтение СКЗ
    # --------------------------------------------------------

    def read_rms(self):
        """Запрос СКЗ шума (RMS?)."""
        self.session.write(b'RMS?\n')
        self.session.flush()
        raw = self.session.readline()
        return float(raw.decode('utf-8', errors='ignore').strip())