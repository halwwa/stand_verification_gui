import unittest
from unittest.mock import Mock, patch

from stand_verification.measurement.engine import MeasurementEngine


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
                    row, status = engine._measure_level(str(frequency), 0)
                self.assertEqual(row[4], tolerance)
                self.assertEqual(row[5], expected)
                self.assertEqual(status, expected)


if __name__ == '__main__':
    unittest.main()
