import unittest
from unittest.mock import Mock, patch

from stand_verification.measurement.engine import MeasurementEngine
from stand_verification.models import LevelResult


class LevelToleranceTests(unittest.TestCase):
    def test_frequency_boundary_and_signed_errors(self):
        cases = [(1999, 1.5, 1.0, 'fail'),
                 (2000, 1.4, 2.0, 'ok'),
                 (2000, 1.5, 2.0, 'warn'),
                 (2500, -2.0, 2.0, 'warn'),
                 (3000, 2.01, 2.0, 'fail'),
                 (3000, -2.01, 2.0, 'fail')]
        for frequency, measured, tolerance, expected in cases:
            with self.subTest(frequency=frequency, measured=measured):
                meter = Mock()
                meter.readline.return_value = str(measured).encode()
                engine = MeasurementEngine(Mock(), meter)
                with patch('stand_verification.measurement.level.SETTLE_DELAY', 0):
                    row = engine._measure_level(str(frequency), 0)
                self.assertEqual(row.tolerance_db, tolerance)
                self.assertEqual(row.status, expected)
                self.assertEqual(row.frequency_mhz, float(frequency))
                self.assertEqual(row.set_level_dbm, 0)
                self.assertEqual(row.measured_level_dbm, round(measured, 2))
                self.assertEqual(row.error_db, round(measured, 2))
                self.assertIsInstance(row, LevelResult)

    def test_stop_during_level_wait_returns_complete_error_result(self):
        event = Mock()
        event.is_set.return_value = False
        event.wait.return_value = True
        engine = MeasurementEngine(Mock(), Mock(), stop_event=event)
        with patch('stand_verification.measurement.level.SETTLE_DELAY', 0):
            result = engine._measure_level('2000', -13)
        self.assertEqual(result, LevelResult(
            frequency_mhz=2000.0, set_level_dbm=-13,
            measured_level_dbm=None, error_db=None, tolerance_db=2.0,
            status='error', comment='Остановка запрошена во время выдержки',
        ))
        event.wait.assert_called_once_with(0)

    def test_stop_before_level_measurement_performs_no_instrument_io(self):
        event = Mock()
        event.is_set.return_value = True
        generator, meter = Mock(), Mock()
        engine = MeasurementEngine(generator, meter, stop_event=event)
        result = engine._measure_level('2000', -13)
        self.assertEqual(result, LevelResult(
            frequency_mhz=2000.0, set_level_dbm=-13,
            measured_level_dbm=None, error_db=None, tolerance_db=2.0,
            status='error', comment='Остановка запрошена',
        ))
        generator.set_power_dbm.assert_not_called()
        meter.write.assert_not_called()
        meter.readline.assert_not_called()


if __name__ == '__main__':
    unittest.main()
