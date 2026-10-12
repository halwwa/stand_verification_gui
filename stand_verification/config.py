"""Default measurement parameters, preserved from the original application."""

# ---- Частоты, уровни, общие задержки ----

F_LIST = ['0.01', '0.1', '1', '10', '50', '100', '250', '500',
          '1000', '1500', '2000', '2500', '3000']
U_LIST_0 = [-13.0, 0.0]
U_LIST = [-13.0, 0.0, 13.0]
SETTLE_DELAY = 10.0
NOISE_SETTLE_DELAY = 15.0
INITIAL_POWER_DBM = -13
NOISE_POWER_DBM = 0

# ---- Идентификаторы тестов ----

TEST_FREQ = 'freq'
TEST_LEVEL = 'level'
TEST_AM_NOISE = 'am_noise'
TEST_FM_NOISE = 'fm_noise'
TEST_PM_NOISE = 'pm_noise'
TEST_AM_FM_TRANSITION = 'am_fm_transition'
TEST_THD_AM = 'thd_am'
TEST_THD_FM = 'thd_fm'

NOT_IMPLEMENTED = set()

# ---- АМ шум: полосы и допуски ----

AM_BAND_LOW_KHZ = 0.3
AM_BAND_HIGH_MAIN_KHZ = 3.4
AM_BAND_LOW_KHZ_20 = 0.02
AM_LFILT_LIST_KHZ = [3.4, 20.0, 60.0, 200.0]
AM_BAND_001_MHZ_LOW_KHZ = 0.02
AM_BAND_001_MHZ_HIGH_KHZ = 1.5
AM_BAND_01_MHZ_LOW_KHZ = 0.02
AM_BAND_01_MHZ_HIGH_KHZ = 3.4
AM_TOL_BAND_03_34 = 0.008

# ---- ЧМ / ФМ шум: полосы ----

SKIP_FOR_FM_PM_MHZ = {0.01, 0.1, 100.0, 1500.0, 2500.0}
FM_LFILT_LIST_KHZ = [3.4, 20.0, 60.0, 200.0]
PM_LFILT_LIST_KHZ = [20.0, 60.0, 200.0]

# ---- Тест 6: Переход АМ↔ЧМ ----

TR_AM_FM_FREQ_MHZ = 20.0
TR_AM_FM_POWER_DBM = -7.0
TR_AM_FM_MOD_FREQ_HZ = 20000
TR_AM_FM_DEPTH_PERCENT = 30.0
TR_AM_FM_HF_KHZ = 0.3
TR_AM_FM_LF_KHZ = 20.0
TR_AM_FM_TOLERANCE_HZ = 10.0

TR_FM_AM_FREQ_MHZ = 100.0
TR_FM_AM_POWER_DBM = 0.0
TR_FM_AM_MOD_FREQ_HZ = 20000
TR_FM_AM_DEVIATION_HZ = 200000
TR_FM_AM_HF_KHZ = 0.3
TR_FM_AM_LF_KHZ = 20.0
TR_FM_AM_TOLERANCE_PERCENT = 0.02

TR_SETTLE_DELAY = 15.0
TR_STEP_DELAY = 1.0

# ---- Тест 7: КГ АМ ----

THD_AM_CARRIER_MHZ = 20.0
THD_AM_POWER_DBM = 0.0
THD_AM_START_MOD_FREQ_HZ = 1000
THD_AM_START_DEPTH = 10

# Частоты модуляции при измерении КГ АМ
THD_AM_FM_LIST_HZ = [20, 90, 6000, 60000]
# Глубины АМ
THD_AM_KAM_LIST = [30, 95]

# Полосы фильтров СК3-50 в зависимости от модулирующей частоты
THD_AM_FILTER_MAP = {
    20:     3.4,
    90:     3.4,
    6000:   20.0,
    60000:  200.0,
}

# Задержки
THD_AM_WAIT_AFTER_FREQ_MAN_S = 5.0
THD_AM_WAIT_AFTER_SET_DEPTH_S = 2.0
THD_AM_WAIT_BEFORE_PEAK_S = 10.0
THD_AM_WAIT_AFTER_PEAK_S = 1.0
THD_AM_WAIT_BEFORE_C6_THD_S = 20.0   # «С6-22 очень долго настраивается»
THD_AM_WAIT_AFTER_C6_CMD_S = 2.0
THD_AM_WAIT_BEFORE_SK3_THD_S = 1.0

# Допуски (%) для Теста 7 (по папиному коду)
THD_AM_TOL_DEFAULT = 0.3
THD_AM_TOL_20_90_KAM30 = 0.15
THD_AM_TOL_6000_KAM30 = 0.2
THD_AM_TOL_60000_KAM95 = 0.4

# ---- Тест 8: КГ ЧМ ----

THD_FM_CARRIER_MHZ = 20.0
THD_FM_POWER_DBM = 0.0
THD_FM_START_MOD_FREQ_HZ = 1000
THD_FM_START_DEVIATION_HZ = 100000

THD_FM_FM_LIST_HZ = [20, 1000, 6000, 20000, 60000, 16650, 9810, 6970]
THD_FM_DEV_LIST_HZ_STD = [300000, 500000, 1000000]
THD_FM_DEV_LIST_HZ_SQU = [500000]

# Фильтры по Fm для Теста 8
THD_FM_FILTER_MAP = {
    20:     3.4,
    1000:   3.4,
    6000:   20.0,
    16650:  20.0,
    9810:   20.0,
    6970:   20.0,
    20000:  60.0,
    60000:  200.0,
}

THD_FM_WAIT_AFTER_FREQ_MAN_S = 5.0
THD_FM_WAIT_AFTER_SET_DEV_S = 2.0
THD_FM_WAIT_BEFORE_PEAK_S = 10.0
THD_FM_WAIT_AFTER_PEAK_S = 1.0
THD_FM_WAIT_BEFORE_C6_THD_S = 20.0
THD_FM_WAIT_AFTER_C6_CMD_S = 2.0
THD_FM_WAIT_BEFORE_SK3_THD_S = 2.0

# ---- Дефолты для приборов ----

DEVICE_DEFAULTS = (
    ("СК3-50", "com", {"port": "", "baud": 115200}, "auto_fill"),
    ("С6-22", "com", {"port": "", "baud": 9600}, None),
    ("SMB100A (R&S)", "lan", {"ip": "192.168.0.113", "lan_port": 5025}, None),
)
REPORT_PATH_DEFAULT = "C:/Reports/Calibration/2026/"