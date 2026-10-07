class SMB100A:
    """SMB100A SCPI operations; connection ownership stays with the caller."""

    def __init__(self, session):
        self.session = session

    def reset(self):
        return self.session.write('*RST')

    def output_on(self):
        return self.session.write('OUTP ON')

    def output_off(self):
        return self.session.write('OUTP OFF')

    def set_frequency_mhz(self, frequency_mhz):
        return self.session.write(f'FREQ {frequency_mhz} MHz')

    def set_power_dbm(self, power_dbm):
        return self.session.write(f'POW {power_dbm}')

    def read_frequency_hz(self):
        _ = float(self.session.query('FREQ?')) / 1_000_000
        return float(self.session.query('FREQ?'))
