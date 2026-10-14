import unittest
from unittest.mock import Mock

from stand_verification.measurement.thd_fm import _thd_fm_tolerance, run_thd_fm


class ThdFmToleranceTests(unittest.TestCase):
    def test_fixed_tolerances_do_not_depend_on_measured_thd(self):
        for freq, expected in ((20, 0.1), (1000, 0.1), (6000, 0.1),
                               (20000, 0.2), (60000, 0.2)):
            for thd in (0.0, 0.014, 0.497, 1.26, 31.9):
                with self.subTest(freq=freq, thd=thd):
                    self.assertEqual(_thd_fm_tolerance(freq, thd), expected)

    def test_square_wave_frequencies_keep_original_formula(self):
        for freq in (16650, 9810, 6970):
            for thd in (0.0, 1.26, 12.69, 31.9, -1.26):
                with self.subTest(freq=freq, thd=thd):
                    self.assertEqual(
                        _thd_fm_tolerance(freq, thd), 0.1 * abs(thd) + 0.03,
                    )

    def test_missing_reference_measurement_has_no_tolerance(self):
        for freq in (20, 1000, 6000, 20000, 60000, 16650, 9810, 6970):
            with self.subTest(freq=freq):
                self.assertIsNone(_thd_fm_tolerance(freq, None))

    def test_measurement_rows_use_frequency_tolerance_and_status(self):
        gen, sk3, c6 = Mock(), Mock(), Mock()
        sk3.read_peak.return_value = 500000.0
        sk3.read_thd.return_value = 0.2
        c6.read_thd.return_value = 0.05
        c6.read_mod_frequency.return_value = '1000HZ'
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.return_value = False

        rows = run_thd_fm(gen, sk3, c6, stop_event, Mock())

        self.assertEqual(len(rows), 18)
        expected = {
            20: (0.1, 'fail', 3),
            1000: (0.1, 'fail', 3),
            6000: (0.1, 'fail', 3),
            20000: (0.2, 'warn', 3),
            60000: (0.2, 'warn', 3),
            16650: (0.035, 'fail', 1),
            9810: (0.035, 'fail', 1),
            6970: (0.035, 'fail', 1),
        }
        for freq, (tolerance, status, count) in expected.items():
            with self.subTest(freq=freq):
                freq_rows = [row for row in rows if row.mod_freq_hz == freq]
                self.assertEqual(len(freq_rows), count)
                for row in freq_rows:
                    self.assertAlmostEqual(row.tolerance, tolerance)
                    self.assertEqual(row.status, status)


if __name__ == '__main__':
    unittest.main()
