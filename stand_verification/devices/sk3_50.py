class SK350:
    """SK3-50 request/decode operations; connection ownership stays with caller."""

    def __init__(self, session):
        self.session = session

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
