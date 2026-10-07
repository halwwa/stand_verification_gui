import unittest
from unittest.mock import Mock, patch

from stand_verification.devices.connections import open_serial, open_visa, close_resources
from stand_verification.devices.sk3_50 import SK350
from stand_verification.devices.smb100a import SMB100A


class DeviceTests(unittest.TestCase):
    def test_serial_idn_retries_with_exact_session_settings(self):
        session = Mock()
        session.readline.side_effect = [b'\n', b'Acme, Meter, 1, rev\n']
        serial = Mock(Serial=Mock(return_value=session))
        with patch('stand_verification.devices.connections.time.sleep') as pause:
            inst, idn = open_serial(serial, 'COM4', 115200)
        serial.Serial.assert_called_once_with(port='COM4', baudrate=115200, timeout=2)
        self.assertEqual(session.write.call_args_list[0].args, (b'*IDN?\n',))
        self.assertEqual(session.readline.call_count, 2)
        self.assertEqual(pause.call_args_list[0].args, (0.3,))
        self.assertEqual(pause.call_args_list[1].args, (0.3,))
        self.assertIs(inst, session)
        self.assertEqual(idn, 'Acme, Meter, 1, rev')

    def test_visa_setup_uses_py_backend_terminations_and_idn(self):
        resource, manager = Mock(), Mock()
        manager.open_resource.return_value = resource
        visa = Mock(ResourceManager=Mock(return_value=manager))
        got_manager, got_resource, idn = open_visa(visa, '10.0.0.1', 5025)
        visa.ResourceManager.assert_called_once_with('@py')
        manager.open_resource.assert_called_once_with(
            'TCPIP::10.0.0.1::5025::SOCKET', timeout=5000)
        self.assertEqual(resource.read_termination, '\n')
        self.assertEqual(resource.write_termination, '\n')
        resource.query.assert_called_once_with('*IDN?')
        self.assertEqual(idn, resource.query.return_value.strip())
        self.assertIs(got_manager, manager)
        self.assertIs(got_resource, resource)

    def test_visa_failure_closes_partial_resource_and_manager(self):
        resource, manager = Mock(), Mock()
        resource.query.side_effect = OSError('IDN failed')
        manager.open_resource.return_value = resource
        with self.assertRaisesRegex(OSError, 'IDN failed'):
            open_visa(Mock(ResourceManager=Mock(return_value=manager)), 'host', 5025)
        resource.close.assert_called_once_with()
        manager.close.assert_called_once_with()

    def test_close_resources_and_drivers_express_instrument_operations(self):
        resource, manager = Mock(), Mock()
        close_resources(resource, manager)
        resource.close.assert_called_once_with()
        manager.close.assert_called_once_with()
        visa_session, serial_session = Mock(), Mock()
        visa_session.query.side_effect = ['10000', '10000']
        generator = SMB100A(visa_session)
        generator.reset()
        generator.output_on()
        generator.set_frequency_mhz('0.01')
        generator.set_power_dbm(-13)
        generator.read_frequency_hz()
        generator.output_off()
        meter = SK350(serial_session)
        visa_session.write.assert_has_calls([
            unittest.mock.call('*RST'), unittest.mock.call('OUTP ON'),
            unittest.mock.call('FREQ 0.01 MHz'), unittest.mock.call('POW -13'),
            unittest.mock.call('OUTP OFF')])
        self.assertEqual(visa_session.query.call_args_list,
                         [unittest.mock.call('FREQ?'), unittest.mock.call('FREQ?')])
        serial_session.readline.side_effect = [b'12500.5\n', b'2400\n', b'-12.5\n']
        self.assertEqual(meter.read_frequency_hz(), 12500.5)
        self.assertEqual(meter.read_if_khz(), 2.4)
        self.assertEqual(meter.read_power_dbm(), -12.5)
        self.assertEqual(serial_session.write.call_args_list, [
            unittest.mock.call(b'FREQ?\n'), unittest.mock.call(b'FREQ:INT?\n'),
            unittest.mock.call(b'POW?\n')])

    def test_device_adapter_preserves_frequency_query_count_and_if_error_prefix(self):
        generator_session, meter_session = Mock(), Mock()
        generator_session.query.side_effect = ['10000', '10000']
        self.assertEqual(SMB100A(generator_session).read_frequency_hz(), 10000.0)
        self.assertEqual(generator_session.query.call_count, 2)
        meter_session.readline.return_value = b'invalid\n'
        with self.assertRaisesRegex(ValueError, '^Некорректный разбор частоты ПЧ:'):
            SK350(meter_session).read_if_khz()

    def test_serial_cleanup_suppresses_close_failure_and_preserves_open_error(self):
        session = Mock()
        session.write.side_effect = OSError('IDN write failed')
        session.close.side_effect = OSError('close failed')
        with self.assertRaisesRegex(OSError, 'IDN write failed'):
            open_serial(Mock(Serial=Mock(return_value=session)), 'COM1', 9600)
        session.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
