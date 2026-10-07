import pyvisa

# Получаем IP-адрес от пользователя через ввод в консоли
ip_address = input("Введите IP-адрес прибора (например, 192.168.0.106): ").strip()

# Формируем стандартную строку ресурса LXI
resource_name = f"TCPIP::{ip_address}::inst0::INSTR"

# Инициализируем менеджер ресурсов с бэкэндом чистый Python
rm = pyvisa.ResourceManager('@py')

try:
    print(f"Попытка подключения к {ip_address}...")
    
    # Открываем сессию с прибором
    inst = rm.open_resource(resource_name, timeout=5000) # Таймаут 5 секунд
    
    # Настраиваем символы окончания строк для корректного обмена данными
    inst.read_termination = '\n'
    inst.write_termination = '\n'

    # Запрашиваем идентификационные данные прибора
    idn_info = inst.query("*IDN?").strip()
    
    print("\n" + "="*40)
    print("✨ ПРИБОР УСПЕШНО ПОДКЛЮЧЕН! ✨")
    print(f"Информация об устройстве: {idn_info}")
    print("="*40 + "\n")
    
    # Здесь можно продолжать работу с переменной inst...
    
    # Закрываем сессию с прибором после работы
    inst.close()

except Exception as e:
    print("\n" + "!"*40)
    print(f"❌ Ошибка подключения к прибору ({ip_address})")
    print(f"Детали ошибки: {e}")
    print("!"*40 + "\n")

finally:
    # Обязательно закрываем менеджер ресурсов
    rm.close()
        
