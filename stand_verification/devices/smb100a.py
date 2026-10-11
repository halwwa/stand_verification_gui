class SMB100A:
    """SMB100A SCPI operations; connection ownership stays with the caller."""

    def __init__(self, session):
        self.session = session

    # --------------------------------------------------------
    #                    ВЫХОД И БАЗА
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    #                    АМ МОДУЛЯЦИЯ
    # --------------------------------------------------------

    def set_am_on(self):
        return self.session.write('SOUR:AM:STAT ON')

    def set_am_off(self):
        return self.session.write('SOUR:AM:STAT OFF')

    def set_am_source_int(self):
        return self.session.write('SOUR:AM:SOURce INT')

    def set_am_depth_percent(self, depth):
        return self.session.write(f'SOUR:AM:DEPT {depth}')

    # --------------------------------------------------------
    #                    ЧМ МОДУЛЯЦИЯ
    # --------------------------------------------------------

    def set_fm_on(self):
        return self.session.write('SOUR:FM:STAT ON')

    def set_fm_off(self):
        return self.session.write('SOUR:FM:STAT OFF')

    def set_fm_source_int(self):
        return self.session.write('SOUR:FM:SOURce INT')

    def set_fm_deviation_hz(self, deviation_hz):
        return self.session.write(f'SOUR:FM:DEV {deviation_hz}')

    # --------------------------------------------------------
    #                    ОБЩЕЕ ДЛЯ МОДУЛЯЦИИ
    # --------------------------------------------------------

    def set_lfo_freq_hz(self, freq_hz):
        return self.session.write(f'SOUR:LFO:FREQ {freq_hz}')

    def set_lfo_shape_sin(self):
        return self.session.write('SOUR:LFO:SHAP SIN')

    def set_lfo_shape_square(self):
        return self.session.write('SOUR:LFO:SHAP SQU')