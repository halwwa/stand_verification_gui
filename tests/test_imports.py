import subprocess
import sys
import unittest


class ImportTests(unittest.TestCase):
    def test_engine_import_does_not_load_tkinter_openpyxl_or_hardware(self):
        code = (
            'import sys; import stand_verification.measurement.engine; '
            "assert 'tkinter' not in sys.modules; "
            "assert 'openpyxl' not in sys.modules; "
            "assert 'serial' not in sys.modules; "
            "assert 'pyvisa' not in sys.modules"
        )
        subprocess.run([sys.executable, '-c', code], check=True)

    def test_both_entrypoint_modules_import_without_creating_window(self):
        code = (
            'import stand_verification.__main__; import gui_stand; '
            'assert callable(gui_stand.main)'
        )
        subprocess.run([sys.executable, '-c', code], check=True)


if __name__ == '__main__':
    unittest.main()
