import unittest
from unittest.mock import Mock, patch

from stand_verification.devices.connections import open_socket
from stand_verification.ui.device_card import DeviceCard, PORT_POLL_INTERVAL_MS


class SocketConnectionTests(unittest.TestCase):
    def test_socket_idn_uses_raw_tcp_session_and_retries_empty_answer(self):
        session = Mock()
        session.readline.side_effect = [b'\n', b'Acme, SK3-50, 1, rev\n']
        sock = Mock()
        sock.makefile.return_value = session
        socket_module = Mock()
        socket_module.create_connection.return_value = sock

        with patch('stand_verification.devices.connections.time.sleep') as pause:
            got_sock, got_session, idn = open_socket(socket_module, '10.0.0.2', 5025)

        socket_module.create_connection.assert_called_once_with(
            ('10.0.0.2', 5025), timeout=2)
        sock.settimeout.assert_called_once_with(2)
        sock.makefile.assert_called_once_with('rwb')
        session.write.assert_called_once_with(b'*IDN?\n')
        session.flush.assert_called_once_with()
        self.assertEqual(session.readline.call_count, 2)
        self.assertEqual([call.args for call in pause.call_args_list], [(0.3,), (0.3,)])
        self.assertIs(got_sock, sock)
        self.assertIs(got_session, session)
        self.assertEqual(idn, 'Acme, SK3-50, 1, rev')

    def test_socket_failure_closes_file_and_socket(self):
        session = Mock()
        session.write.side_effect = OSError('socket write failed')
        sock = Mock()
        sock.makefile.return_value = session
        socket_module = Mock()
        socket_module.create_connection.return_value = sock

        with self.assertRaisesRegex(OSError, 'socket write failed'):
            open_socket(socket_module, 'host', 5025)

        session.close.assert_called_once_with()
        sock.close.assert_called_once_with()


class DeviceCardConnectionTests(unittest.TestCase):
    def card(self):
        return DeviceCard.__new__(DeviceCard)

    def test_refresh_adds_new_port_without_replacing_manual_selection(self):
        card = self.card()
        card._ports = ['COM1', 'COM15']
        card.port_cb = Mock()
        card.port_var = Mock()

        with patch.object(DeviceCard, '_list_ports', return_value=['COM1', 'COM14']):
            ports = card.refresh_ports()

        self.assertEqual(ports, ['COM1', 'COM14'])
        self.assertEqual(card._ports, ['COM1', 'COM14'])
        card.port_cb.configure.assert_called_once_with(values=['COM1', 'COM14'])
        card.port_var.set.assert_not_called()

    def test_refresh_does_not_rewrite_unchanged_port_list(self):
        card = self.card()
        card._ports = ['COM1']
        card.port_cb = Mock()

        with patch.object(DeviceCard, '_list_ports', return_value=['COM1']):
            card.refresh_ports()

        card.port_cb.configure.assert_not_called()

    def test_port_polling_repeats_while_card_exists(self):
        card = self.card()
        card.frame = Mock()
        card.frame.winfo_exists.return_value = True
        card.refresh_ports = Mock()

        card._poll_ports()

        card.refresh_ports.assert_called_once_with()
        card.frame.after.assert_called_once_with(PORT_POLL_INTERVAL_MS, card._poll_ports)

    def test_sk3_lan_selection_uses_socket_and_com_selection_uses_serial(self):
        card = self.card()
        card.kind = 'com_lan'
        card.connection_var = Mock()
        card.connection_var.get.side_effect = ['LAN', 'COM']

        self.assertEqual(card.connection_kind(), 'socket')
        self.assertEqual(card.connection_kind(), 'com')

    def test_socket_worker_returns_session_compatible_with_sk3_adapter(self):
        card = self.card()
        card.inst = card.rm = None
        card.dispatch = lambda callback: callback()
        card._on_connected = Mock()
        card._on_error = Mock()
        sock, session = Mock(), Mock()

        with patch('stand_verification.ui.device_card.open_socket',
                   return_value=(sock, session, 'Acme, SK3-50, 1, rev')) as opener:
            card._connect_worker('socket', ('10.0.0.2', 5025))

        opener.assert_called_once_with(unittest.mock.ANY, '10.0.0.2', 5025)
        self.assertIs(card.inst, session)
        self.assertIs(card.rm, sock)
        card._on_connected.assert_called_once_with('Acme, SK3-50, 1, rev')
        card._on_error.assert_not_called()

    def test_dual_connection_settings_are_saved_together(self):
        card = self.card()
        card.kind = 'com_lan'
        card.title = 'СК3-50'
        card.port_var = Mock()
        card.port_var.get.return_value = 'COM15'
        card.baud_var = Mock()
        card.baud_var.get.return_value = '115200'
        card.ip_var = Mock()
        card.ip_var.get.return_value = '10.0.0.2'
        card.lanport_var = Mock()
        card.lanport_var.get.return_value = '5025'
        card.connection_var = Mock()
        card.connection_var.get.return_value = 'LAN'
        cfg = {}

        card.update_config(cfg)

        self.assertEqual(cfg, {
            'СК3-50_port': 'COM15',
            'СК3-50_baud': '115200',
            'СК3-50_ip': '10.0.0.2',
            'СК3-50_lan_port': '5025',
            'СК3-50_connection': 'LAN',
        })


if __name__ == '__main__':
    unittest.main()
