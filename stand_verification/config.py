"""Default measurement parameters, preserved from the original application."""

# Список частот для цикла по частотам (МГц)
F_LIST = ['0.01', '0.1', '1', '10', '50', '100', '250', '500',
          '1000', '1500', '2000', '2500', '3000']

# Список уровней для теста уровня (dBm)
U_LIST_0 = [-13.0, 0.0]           # для частот 0.01 и 0.1 МГц
U_LIST = [-13.0, 0.0, 13.0]       # для остальных частот

# Задержка после установки частоты / уровня (сек)
SETTLE_DELAY = 10.0

# Задержка после установки фильтра перед RMS? (сек)
NOISE_SETTLE_DELAY = 5.0

# Начальный уровень генератора (dBm)
INITIAL_POWER_DBM = -13

# Уровень, при котором измеряются шумы (dBm)
NOISE_POWER_DBM = 0

# Идентификаторы тестов
TEST_FREQ = 'freq'
TEST_LEVEL = 'level'
TEST_AM_NOISE = 'am_noise'
TEST_FM_NOISE = 'fm_noise'
TEST_PM_NOISE = 'pm_noise'

# Тесты, которые пока НЕ реализованы
NOT_IMPLEMENTED = set()  # все три шума реализуем сейчас

# Списки полос для АМ шума
# Для большинства частот: сначала 0.3–3.4, потом 0.02–{3.4, 20, 60, 200}
AM_BAND_LOW_KHZ = 0.3             # HF фильтр для стандартной полосы
AM_BAND_HIGH_MAIN_KHZ = 3.4       # LF фильтр для 0.3–3.4
AM_BAND_LOW_KHZ_20 = 0.02         # HF фильтр для полос 0.02–*
AM_LFILT_LIST_KHZ = [3.4, 20.0, 60.0, 200.0]  # верхние срезы для полос 0.02–*

# Особые случаи АМ шума
AM_BAND_001_MHZ_LOW_KHZ = 0.02    # для 0.01 МГц
AM_BAND_001_MHZ_HIGH_KHZ = 1.5    # для 0.01 МГц
AM_BAND_01_MHZ_LOW_KHZ = 0.02     # для 0.1 МГц
AM_BAND_01_MHZ_HIGH_KHZ = 3.4     # для 0.1 МГц

# Допуски АМ шума (в %)
AM_TOL_BAND_03_34 = 0.008
AM_TOL_BAND_02_34 = 0.01
AM_TOL_BAND_02_20 = 0.03
AM_TOL_BAND_02_60 = 0.05
AM_TOL_BAND_02_200 = 0.1
AM_TOL_BAND_02_15 = 0.01

# Частоты для ЧМ и ФМ шумов — те, что НЕ 0.01, 0.1, 100, 1500, 2500
SKIP_FOR_FM_PM_MHZ = {0.01, 0.1, 100.0, 1500.0, 2500.0}

# Списки полос для ЧМ шума
FM_LFILT_LIST_KHZ = [3.4, 20.0, 60.0, 200.0]

# Списки полос для ФМ шума
PM_LFILT_LIST_KHZ = [20.0, 60.0, 200.0]

# --- Настройки по умолчанию для приборов ---
DEVICE_DEFAULTS = (
    ("СК3-50", "com", {"port": "", "baud": 115200}, "auto_fill"),
    ("С6-22", "com", {"port": "", "baud": 9600}, None),
    ("SMB100A (R&S)", "lan", {"ip": "192.168.0.113", "lan_port": 5025}, None),
)
REPORT_PATH_DEFAULT = "C:/Reports/Calibration/2026/"