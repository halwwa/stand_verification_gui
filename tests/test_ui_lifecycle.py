import queue
import unittest
from unittest.mock import Mock, patch

from stand_verification.ui.app import StandApp


class UiLifecycleTests(unittest.TestCase):
    def app(self):
        app = StandApp.__new__(StandApp)
        app.root = Mock()
        app.callbacks = queue.Queue()
        app.log = Mock()
        return app

    def test_failed_primary_export_uses_fallback_without_rerunning_engine(self):
        app = self.app()
        engine = Mock()
        with patch('stand_verification.ui.app.os.makedirs'), \
                patch('stand_verification.ui.app.export_excel',
                      side_effect=[OSError('primary failed'), True]) as export:
            result = app._save_report_to_excel(engine, ('reports', 'run.xlsx'))
        self.assertEqual(result, ('./run.xlsx', None))
        self.assertEqual([call.args[1] for call in export.call_args_list],
                         ['reports/run.xlsx', './run.xlsx'])
        engine.run.assert_not_called()
        while not app.callbacks.empty():
            app.callbacks.get_nowait()()
        app.log.assert_called_once()

    def test_both_export_failures_are_reported(self):
        app = self.app()
        with patch('stand_verification.ui.app.os.makedirs'), \
                patch('stand_verification.ui.app.export_excel',
                      side_effect=[OSError('primary failed'), OSError('fallback failed')]):
            path, error = app._save_report_to_excel(Mock(), ('reports', 'run.xlsx'))
        self.assertIsNone(path)
        self.assertIn('primary failed', error)
        self.assertIn('fallback failed', error)

    def test_close_waits_for_worker_before_disconnecting_sessions(self):
        app = self.app()
        app.close_requested = True
        app.tests_running = False
        app.initializing = False
        app._connections_active = Mock(return_value=False)
        app.engine_thread = Mock()
        app.engine_thread.is_alive.return_value = True
        app.retry_thread = None
        app.shutdown_blocked = False
        app.report_result = None
        card = Mock()
        card.locked = True
        app.cards = [card]
        app._poll_close()
        app.root.after.assert_called_once_with(50, app._poll_close)
        card.disconnect.assert_not_called()
        app.root.destroy.assert_not_called()
        app.engine_thread.is_alive.return_value = False
        app._poll_close()
        self.assertFalse(card.locked)
        card.disconnect.assert_called_once_with()
        app.root.destroy.assert_called_once_with()

    def test_failed_shutdown_keeps_sessions_open_on_close(self):
        app = self.app()
        app.close_requested = True
        app.tests_running = False
        app.initializing = False
        app._connections_active = Mock(return_value=False)
        app.engine_thread = app.retry_thread = None
        app.shutdown_blocked = True
        app._warn_shutdown = Mock()
        card = Mock()
        app.cards = [card]
        app._poll_close()
        app._warn_shutdown.assert_called_once_with()
        card.disconnect.assert_not_called()
        app.root.destroy.assert_not_called()
