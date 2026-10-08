"""Default measurement parameters, preserved from the original application."""

F_LIST = ['0.01', '0.1', '1', '10', '50', '100', '250', '500',
          '1000', '1500', '2000', '2500', '3000']
U_LIST_0 = [-13.0, 0.0]
U_LIST = [-13.0, 0.0, 13.0]
SETTLE_DELAY = 10.0
INITIAL_POWER_DBM = -13
TEST_FREQ = 'freq'
TEST_LEVEL = 'level'
TEST_AM_NOISE = 'am_noise'
TEST_FM_NOISE = 'fm_noise'
TEST_PM_NOISE = 'pm_noise'
NOT_IMPLEMENTED = {TEST_AM_NOISE, TEST_FM_NOISE, TEST_PM_NOISE}
DEVICE_DEFAULTS = (
    ("СК3-50", "com", {"port": "", "baud": 115200}, "auto_fill"),
    ("С6-22", "com", {"port": "", "baud": 9600}, None),
    ("SMB100A (R&S)", "lan", {"ip": "192.168.0.113", "lan_port": 5025}, None),
)
REPORT_PATH_DEFAULT = "C:/Reports/Calibration/2026/"
