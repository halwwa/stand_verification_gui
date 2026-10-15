class SK350:
    """SK3-50 request/decode operations; connection ownership stays with caller."""

    def __init__(self, session):
        self.session = session

    # ---------- частота / уровень ----------

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

    # ---------- режимы модуляции ----------

    def set_mode_am(self):
        self.session.write(b'CONF:MODE AM\n')
        self.session.flush()

    def set_mode_fm(self):
        self.session.write(b'CONF:MODE FM\n')
        self.session.flush()

    def set_mode_pm(self):
        self.session.write(b'CONF:MODE PM\n')
        self.session.flush()

    # ---------- фильтры ----------

    def set_filter_hp_khz(self, value_khz):
        cmd = f'CONF:INP:FILT:HPAS {value_khz:g}kHz\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    def set_filter_hp_hz(self, value_hz):
        cmd = f'CONF:INP:FILT:HPAS {value_hz:g}\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    def set_filter_lp_khz(self, value_khz):
        cmd = f'CONF:INP:FILT:LPAS {value_khz:g}kHz\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    # ---------- СКЗ / пик / КГ ----------

    def read_rms(self):
        self.session.write(b'RMS?\n')
        self.session.flush()
        raw = self.session.readline()
        return float(raw.decode('utf-8', errors='ignore').strip())

    def set_polarity_pos(self):
        self.session.write(b'CONF:POL POS\n')
        self.session.flush()

    def set_polarity_neg(self):
        self.session.write(b'CONF:POL NEG\n')
        self.session.flush()

    def read_peak(self):
        self.session.write(b'PEAK?\n')
        self.session.flush()
        raw = self.session.readline()
        return float(raw.decode('utf-8', errors='ignore').strip())

    def set_thd_on(self):
        self.session.write(b'CONF:THD ON\n')
        self.session.flush()

    def set_thd_off(self):
        self.session.write(b'CONF:THD OFF\n')
        self.session.flush()

    def read_thd(self):
        self.session.write(b'THD?\n')
        self.session.flush()
        raw = self.session.readline()
        return float(raw.decode('utf-8', errors='ignore').strip())

    def set_freq_manual_on(self):
        self.session.write(b'CONF:FREQ:MAN ON\n')
        self.session.flush()

    def set_freq_manual_off(self):
        self.session.write(b'CONF:FREQ:MAN OFF\n')
        self.session.flush()

    def set_amt_on(self):
        self.session.write(b'CONF:AMT ON\n')
        self.session.flush()

    def set_amt_off(self):
        self.session.write(b'CONF:AMT OFF\n')
        self.session.flush()

    # ---------- Калибровка и шкалы (для Тестов 9, 10) ----------

    def set_range_fm_auto(self):
        """CONF:RANG:FM AUTO — автоматический выбор шкалы девиации."""
        self.session.write(b'CONF:RANG:FM AUTO\n')
        self.session.flush()

    def set_range_fm_hz(self, value_hz):
        """CONF:RANG:FM <value> — ручная шкала девиации (например 1000000)."""
        cmd = f'CONF:RANG:FM {int(value_hz)}\n'
        self.session.write(cmd.encode('utf-8'))
        self.session.flush()

    def cal_current(self, timeout_s=20.0, attempts=3, attempt_wait_s=2.0):
        """
        CAL:CURR? — запуск калибровки. Ждёт ответ '0' (успех).

        Возвращает True при успехе, False при неудаче.

        Логика:
          1. Отправить CAL:CURR?.
          2. Подождать timeout_s секунд (у приборов долгая калибровка).
          3. До attempts раз прочитать ответ. Если '0' — успех.
        """
        import time as _time
        self.session.write(b'CAL:CURR?\n')
        self.session.flush()

        _time.sleep(timeout_s)

        for _ in range(attempts):
            _time.sleep(attempt_wait_s)
            try:
                raw = self.session.readline()
                response = raw.decode('ascii', errors='ignore').strip()
                if response == '0':
                    return True
            except Exception:
                pass
        return False