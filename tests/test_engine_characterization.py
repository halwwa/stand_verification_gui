import unittest

from stand_verification.measurement.engine import MeasurementEngine, TEST_FREQ, TEST_LEVEL
from stand_verification.measurement.tolerances import evaluate


class FakeEvent:
    def __init__(self, stopped=False, wait_results=None):
        self.stopped = stopped
        self.wait_results = list(wait_results or [])
        self.wait_calls = []

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        result = self.wait_results.pop(0) if self.wait_results else False
        if result:
            self.stopped = True
        return result


class FakeGenerator:
    def __init__(self, query_responses=None, fail_write=None, fail_query=None):
        self.commands = []
        self.queries = []
        self.query_responses = list(query_responses or [])
        self.fail_write = fail_write
        self.fail_query = fail_query

    def write(self, command):
        self.commands.append(command)
        if command == self.fail_write:
            raise OSError('write failed')

    def query(self, command):
        self.queries.append(command)
        if command == self.fail_query:
            raise OSError('query failed')
        return self.query_responses.pop(0) if self.query_responses else '10000'


class FakeMeter:
    def __init__(self, responses=None, fail_write=None):
        self.responses = list(responses or [])
        self.commands = []
        self.fail_write = fail_write

    def write(self, command):
        self.commands.append(command)
        if command == self.fail_write:
            raise OSError('meter write failed')

    def flush(self):
        pass

    def readline(self):
        if not self.responses:
            raise OSError('meter read failed')
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class EngineCharacterizationTests(unittest.TestCase):
    def engine(self, tests, meter_responses=None, gen=None, event=None, log=None):
        return MeasurementEngine(
            gen or FakeGenerator(), FakeMeter(meter_responses), tests,
            stop_event=event or FakeEvent(), log_callback=log,
        )

    def test_combined_command_and_query_order_includes_double_frequency_query(self):
        gen = FakeGenerator(['10000', '10000'])
        meter = FakeMeter([b'10000\n', b'2000\n', b'-13\n', b'0\n'])
        engine = MeasurementEngine(gen, meter, [TEST_FREQ, TEST_LEVEL], stop_event=FakeEvent())

        result, status = engine.run(['0.01'])

        self.assertEqual(status, 'done')
        self.assertEqual(engine.gen.session.commands, [
            '*RST', 'OUTP ON', 'FREQ 10 MHz', 'POW -13', 'FREQ 0.01 MHz',
            'POW -13.0', 'POW 0.0', 'OUTP OFF',
        ])
        self.assertEqual(gen.queries, ['FREQ?', 'FREQ?'])
        self.assertEqual(meter.commands, [b'FREQ?\n', b'FREQ:INT?\n', b'POW?\n', b'POW?\n'])
        self.assertEqual([row[1] for row in result[TEST_LEVEL]], [-13.0, 0.0])

    def test_frequency_only_and_level_only_cycles(self):
        freq_engine = self.engine([TEST_FREQ], [b'10000\n', b'2000\n'])
        _, freq_status = freq_engine.run(['1'])
        self.assertEqual(freq_status, 'done')
        self.assertEqual(freq_engine.gen.session.queries, ['FREQ?', 'FREQ?'])
        self.assertEqual(freq_engine.sk3.session.commands, [b'FREQ?\n', b'FREQ:INT?\n'])

        level_engine = self.engine([TEST_LEVEL], [b'-12.5\n', b'0.5\n', b'13.5\n'])
        _, level_status = level_engine.run(['1'])
        self.assertEqual(level_status, 'done')
        self.assertEqual(level_engine.gen.session.queries, [])
        self.assertEqual(level_engine.sk3.session.commands, [b'POW?\n'] * 3)

    def test_low_frequency_uses_two_levels_and_high_frequency_uses_three(self):
        engine = self.engine([TEST_LEVEL], [b'-13\n', b'0\n', b'-13\n', b'0\n', b'13\n'])
        result, _ = engine.run(['0.1', '0.2'])
        self.assertEqual([row[1] for row in result[TEST_LEVEL]], [-13.0, 0.0, -13.0, 0.0, 13.0])

    def test_failure_stops_cycle_but_summary_retains_plan_and_partial_rows(self):
        engine = self.engine([TEST_FREQ, TEST_LEVEL], [b'invalid'])
        result, status = engine.run(['1', '10'])
        self.assertEqual(status, 'error')
        self.assertEqual(len(result[TEST_FREQ]), 1)
        self.assertEqual(result[TEST_FREQ][0][5], 'error')
        self.assertEqual(engine.summary()[TEST_FREQ], {
            'status': 'error', 'planned': 2, 'total': 1,
            'ok': 0, 'warn': 0, 'fail': 0, 'error': 1,
        })
        self.assertEqual(len(result[TEST_LEVEL]), 0)
        self.assertEqual(engine.gen.session.commands[-1], 'OUTP OFF')

    def test_out_of_tolerance_continues_all_points_and_summary_is_incomplete(self):
        engine = self.engine([TEST_LEVEL], [
            b'-11\n', b'0\n', b'13\n', b'-13\n', b'0\n', b'13\n',
        ])
        result, status = engine.run(['1', '10'])
        self.assertEqual(status, 'warn')
        self.assertEqual([row[5] for row in result[TEST_LEVEL]],
                         ['fail', 'ok', 'ok', 'ok', 'ok', 'ok'])
        self.assertEqual(engine.summary()[TEST_LEVEL], {
            'status': 'incomplete', 'planned': 6, 'total': 6,
            'ok': 5, 'warn': 0, 'fail': 1, 'error': 0,
        })
        self.assertEqual(engine.gen.session.commands[-1], 'OUTP OFF')

    def test_evaluation_boundaries_are_inclusive_for_both_signs(self):
        for sign in (-1, 1):
            for value, expected in ((0.7, 'ok'), (0.7001, 'warn'),
                                    (1, 'warn'), (1.0001, 'fail')):
                with self.subTest(sign=sign, value=value):
                    self.assertEqual(evaluate(sign * value, 1)[0], expected)

    def test_only_unimplemented_placeholders_return_error_without_instrument_io(self):
        gen, meter = FakeGenerator(), FakeMeter()
        engine = MeasurementEngine(gen, meter, ['am_noise'], stop_event=FakeEvent())
        result, status = engine.run(['1'])
        self.assertEqual(status, 'error')
        self.assertEqual(result[TEST_FREQ], [])
        self.assertEqual(engine.gen.session.commands, [])
        self.assertEqual(engine.sk3.session.commands, [])
        self.assertIn('реализованного теста', engine.diagnostics[0])

    def test_stop_during_wait_and_progress_interrupted_error(self):
        event = FakeEvent(wait_results=[False, True])
        engine = self.engine([TEST_FREQ], [b'10000\n', b'0\n'], event=event)
        result, status = engine.run(['1'])
        self.assertEqual(status, 'stopped')
        self.assertEqual(result[TEST_FREQ][0][5], 'error')
        self.assertEqual(result[TEST_FREQ][0][6], 'Остановка запрошена во время выдержки')
        self.assertEqual(event.wait_calls, [1, 6.0])

        event = FakeEvent()
        engine = self.engine([TEST_LEVEL], event=event)
        def interrupt(*_):
            raise InterruptedError()
        result, status = engine.run(['1'], progress_callback=interrupt)
        self.assertEqual(status, 'stopped')
        self.assertTrue(event.is_set())
        self.assertEqual(result[TEST_LEVEL], [])

    def test_frequency_setting_failure_and_meter_read_failure(self):
        gen = FakeGenerator(fail_write='FREQ 1 MHz')
        engine = self.engine([TEST_FREQ], gen=gen)
        result, status = engine.run(['1', '2'])
        self.assertEqual(status, 'error')
        self.assertEqual(result[TEST_FREQ], [])
        self.assertIn('Ошибка установки частоты 1 МГц', engine.termination_reason)
        self.assertEqual(engine.gen.session.commands[-1], 'OUTP OFF')

        engine = self.engine([TEST_LEVEL], [OSError('read broke')])
        result, status = engine.run(['1'])
        self.assertEqual(status, 'error')
        self.assertEqual(result[TEST_LEVEL][0][5], 'error')
        self.assertEqual(result[TEST_LEVEL][0][6], 'read broke')

    def test_signed_thresholds_and_rounded_frequency_fields(self):
        cases = [(1.0, 'warn'), (-1.0, 'warn'), (1.06, 'fail'), (-1.06, 'fail')]
        for measured_offset, expected in cases:
            with self.subTest(offset=measured_offset):
                gen = FakeGenerator(['10000.123', '10000.123'])
                meter = FakeMeter([str(10000.123 + measured_offset).encode(), b'1234.567\n'])
                engine = MeasurementEngine(gen, meter, [TEST_FREQ], stop_event=FakeEvent())
                result, status = engine.run(['0.01'])
                row = result[TEST_FREQ][0]
                self.assertEqual(row[2], round(measured_offset, 2))
                self.assertEqual(row[3], 1.05)
                self.assertEqual(row[4], 1.23)
                self.assertEqual(row[5], expected)
                self.assertEqual(status, 'warn')


if __name__ == '__main__':
    unittest.main()
