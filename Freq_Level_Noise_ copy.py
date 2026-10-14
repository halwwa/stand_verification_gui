import pandas as pd
import numpy as np

import time
import matplotlib.pyplot as plt
import seaborn as sns
import serial
import os
from datetime import datetime

try:
    import xdrlib
except ImportError:
    pass  # xdrlib в стандартной библиотеке, обычно не требует установки
import pyvisa
#import vxi11
# остальной код.




# Основной код

# Функция работы с генератором
if __name__ == "__main__":
    # Получаем IP‑адрес от пользователя
    generator_ip = get_generator_ip()

    # Подключаемся к генератору
    Gen = connect_to_generator(generator_ip)
    


# Открываем Serial порт ('COMX' замените на имя вашего порта)

ser = serial.Serial(port_sk3_50,baudrate=9600, timeout=1 ) # Тестируемый прибор
ser_C6 = serial.Serial(port_c6_22,baudrate=9600, timeout=1 ) # Измеритель нелинейных искажений С6-22



# Инцилизация С6-22 перед измерением 

ser_C6.write(b'MODE VM\n') # Режим измерения напряжения
ser_C6.flush()
time.sleep(5)

ser_C6.write(b'LIMitD MAN\n') # Шкала ручная
ser_C6.flush()
time.sleep(5)
ser_C6.write(b'RANgeD 100V\n') # Шкала 100 В
ser_C6.flush()
time.sleep(5)

# Завершение инцилизация С6-22

# Параметры устанавливаемые в генераторе SMB: Выход Вкл/Выкл; Частота несущей; Уровень; Частота модулирующего сигнала; Режим модуляции АМ, ЧМ; Глубина модуляции АМ; Девиация частоты.
# Параметры устанавливаемые в измерителе модуляции СК3-50: Режим АМ, ЧМ, ФМ; Измерить частоту несущий, Измерить уровень входного сигнала, Измерить Пик+, Пик-, СКЗ значение АМ, ЧМ, ФМ.
# АМ в %, ЧМ в Гц, ФМ в рад.
# Параметры устанавливаемые в измерителе модуляции СК3-50: Значение фильтров ФВЧ(НF) 20 Гц, 300 Гц , фильтра ФНЧ(LF)  1,5 кГц, 3,4 кГц, 20 кГц, 60 кГц, 200 кГц
# Последовательность при измерениях 
# 1. Устанавливаем частоту и уровень в генераторе SMB 
# 2. Настраиваем СК3-50 Уставливаем режим АМ или ЧМ (ФМ) , Выбор фильра ФВЧ и ФНЧ.
# 3. Измеряем СК3-50 Частоту , Уровень, Значение Пик+/Пик-. СКЗ
# 4. Расчитывается погрешность , сравнивается с допуском и записывается в массив для формирования файла Excel
# При измерение вносимых нелинейных искажений добавляется С6-22 -Измерение частоты мулирующей , значение КГ 

# Создание пустых списков
rs = []
rs1 = []
rsNoiseAm = [] 
rsNoiseFm = []
rsNoisePm = []
#rsam_fm = []
#rsFmpik = []
#rsАmpik = []
#rsPmpik = []
#rsFmpikn = []
#rsTHDam = []
#rsTHDfm = []


# Инцилизация  списков
F_list = ['0.01', '0.1','1', '10','50','100','250', '500', '1000', '1500', '2000', '2500', '3000'] # Список частот для тестирования в МГц

U_list_0 = ['-13', '0'] # Список уровней тестирования для частот 0,01 и 0,1 МГц

U_list = ['-13', '0', '13'] # Список уровней тестирования кроме частот  0,01 и 0,1 МГц

LFiltr_list = ['3400', '20000', '60000', '200000'] # Список частот 

LFiltr_listFM = ['3400', '20000', '60000', '200000'] # Список частот  фидьтра НЧ при измерениях в режиме  FM

LFiltr_list_Pm = ['20000', '60000', '200000'] # Список частот  фильтра НЧ при измерениях в режиме PM

Fm_list = ['20', '60','90', '1000', '20000', '30000', '60000'] # Список модулирующих частот при тестирование шумов режима FM 

Pm_list = [ '300', '6000', '60000'] # Список модулирующих частот при тестирование шумов режима PM 

Dpm_k_list = ['100', '10', '1'] # Список частот 

F_listAm = ['20','4','1','0.1'] # Список частот 

LF_Am_25 = ['0.02', '0.06', '1' , '30', '60'] # Список модулирующих частот при измерение в режиме AM на частоте 25 МГц

LF_Am_1 = ['0.02', '0.06', '1' , '6'] # Список модулирующих частот при измерение в режиме AM на частоте 1 МГц

sleep_time=2

tolerdB = 1  # Погрешность при измерение уровня 1 дБ , красная ошибка если более 1 дБ погрешнность. желтая если 0,7 от 1 дБ ( более 70 %) 




#################   Измерение частоты: АМ noise,FM noise,PM noise,Уровень
# Сброс генератора SMB в начальное состояние и инцилизация в нужное состояние
Gen.write('*RST')
Gen.write('OUTP ON')
Gen.write('FREQ 10 MHz') # устанавливаем частоту генератора
time.sleep(1)
indBm = -13
Gen.write('POW -13') # устанавливаем уровень генератора
time.sleep(2)

# Чтение с СК3-50 измеренной частоты
ser.write(b'FREQ?\n')
ser.flush()
# Читаем ответ через Serial порт
response = ser.readline()
print(f"Измеренная Частота СК3-50: {response}")

# Здесь можно было бы добавить проверку что все хорошо, т.е. установили 10 МГц и считали с СК3-50  10 МГц с точностью 5*10^(-6), т.е от 10 МГц это +- 50 Гц

# 1) Измерение частоты;
# 2) Измерение уровня;
# 3) Уровень АМ noise
# 4) Уровень FM noise
# 5) Уровень PM noise
for n in F_list: # Цикл общий для всех измерений , нужно сделать условия чтоб запускался каждый отдельно

    #################   Погрешность измерения частоты
    st = str(n)
    fg = "FREQ ss MHz"    # создаем форму команды установки частоты генератора
    s1 = fg.replace("ss", st)  # меняем в форме ss на st
    Gen.write(s1)     # записать команду s1 в Gen 
    Gen.write('POW -13')
    time.sleep(10)     # задержка на 10 секунд
    inpf = float(Gen.ask("FREQ?"))/1000000 # считываем частоту генератора
    inpf1 = float(Gen.ask("FREQ?")) # считываем частоту генератора
    ser.write(b'FREQ?\n') # запрос измеренной частоты СК3-50
    ser.flush()
    response = ser.readline()
    decoded_response = response.decode('utf-8')
    print("Частота ", inpf, "МГц")
    fiz = float(decoded_response) # измер частота СК3-50 
    kf = fiz - inpf1   # погрешность частоты
    # Рассчитываем допуск по формуле Δf = ±(5·10⁻⁶ · f + 1)
    tolerance = 5e-6 * abs(inpf1) + 1  # допуск в Гц
    ser.write(b'FREQ:INT?\n') # запрос измеренной частоты ПЧ СК3-50
    ser.flush()
    response = ser.readline()
    decoded_response_f = response.decode('utf-8')
    fph = float(decoded_response_f)/1000 
    time.sleep(1)     # задержка на 0.2 секунды
    # Проверяем соответствие допуску: погрешность по модулю не должна превышать допуск
    if abs(kf) <= tolerance:
        compliance = "Да"
    else:
        compliance = "Нет"
    row1 = [inpf1, fiz, round(kf, 2),tolerance, compliance, round(fph, 2)]
    rs1.append(row1) 
    
    
    ###################  Измерение погрешности Уровня  # Тут можно оптимизировать условия это первые попытки
    # Для частот 0,01 и 0,1 МГц (10 кГц и 100кГц) свой список уровней , можно все объединить в один алгоритм
    if inpf != 0.01 and inpf != 0.1: 
        for un in U_list:
            st1 = str(un)
            iU = float(st1)
            fg1 = "POW ss"    # создаем форму команды установки частоты генератора
            s2 = fg1.replace("ss", st1)  # меняем в форме ss на st
            Gen.write(s2)     # записать команду s1 в Gen 
            time.sleep(6)     # задержка на 3 секунд
            ser.write(b'POW?\n') # запрос измеренного уровня СК3-50
            ser.flush()
            response = ser.readline()
            decoded_response = response.decode('utf-8')
            oup = float(decoded_response) # измер уровень мощности СК3-50  
            print("Частота ", inpf, "МГц")
            print(f"Измеренный уровень {oup:.2f} dBm")
            ku = oup - iU   # коэф. усиления 
            time.sleep(1)     # задержка на 0.2 секунды
            # Проверяем соответствие допуску
            if abs(ku) <= tolerdB:
                compliance = "Да"
            else:
                compliance = "Нет"
            row = [inpf, round(oup, 2), round(ku, 2), tolerdB, compliance ]
            rs.append(row)
    if inpf == 0.01 and inpf == 0.1: 
        for un in U_list_0:
            st1 = str(un)
            iU = float(st1)
            fg1 = "POW ss"    # создаем форму команды установки частоты генератора
            s2 = fg1.replace("ss", st1)  # меняем в форме ss на st
            Gen.write(s2)     # записать команду s1 в Gen 
            time.sleep(6)     # задержка на 3 секунд
            ser.write(b'POW?\n') # запрос измеренного уровня СК3-50
            ser.flush()
            response = ser.readline()
            decoded_response = response.decode('utf-8')
            oup = float(decoded_response) # измер уровень мощности СК3-50  
            print("Частота ", inpf, "МГц")
            print(f"Измеренный уровень {oup:.2f} dBm")
            ku = oup - iU   # коэф. усиления 
            time.sleep(1)     # задержка на 0.2 секунды
            # Проверяем соответствие допуску
            if abs(ku) <= tolerdB:
                compliance = "Да"
            else:
                    compliance = "Нет"
        row = [inpf, round(oup, 2), round(ku, 2), tolerdB, compliance ]
        rs.append(row)  
        
    ######################### end  Уровень
   
   
    #################   АМ noise
    Gen.write('POW 0') #устанавливаем уровень генератора SMB 0 дБм перед измерение   АМ noise
    time.sleep(5)
    ser.write(b'CONF:MODE AM\n') # режим АМ СК3-50
    ser.flush()
    time.sleep(sleep_time)
    # Измерение в полосе фильтра 300Гц-3.4 кГц всех частот кроме 10 кГц 
    if inpf != 0.01:
        ser.write(b'CONF:INP:FILT:HPAS 0.3kHz\n') # установка фильра HF 300 Гц  СК3-50
        ser.flush()
        time.sleep(1)
        ser.write(b'CONF:INP:FILT:LPAS 3.4kHz\n') # установка фильра LF 3,4 кГц СК3-50
        ser.flush()
        time.sleep(15)
        ser.write(b'RMS?\n') # запрос СКЗ детектора СК3-50
        ser.flush()
        response = ser.readline()
        decoded_response = response.decode('utf-8')
        amnoise = float(decoded_response) # 
        tolerAmn = 0.008
        if abs(amnoise) <= tolerAmn:
            compliance = "Да"
        else:
            compliance = "Нет"
        print(f"Am noise {amnoise:.3f} %  0.3-3.4кГц")
        
        
        rowAm300 = [inpf,'0.3-3.4', round(amnoise, 3),tolerAmn, compliance ]
        rsNoiseAm.append(rowAm300)
        
        ser.write(b'CONF:INP:FILT:HPAS 20\n') # установка фильра HF 20 Гц  СК3-50 ; Возвращает фильтр HF 20 Гц 
        ser.flush()
    # Измерение в полосе фильтра 20Гц-"Частоты из списка" кГц для  всех частот несущих кроме 10 кГц и 100 кГц     
    if inpf != 0.01 and inpf != 0.1:
        for n in LFiltr_list:
            stLF = str(n)
            fglf = "CONF:INP:FILT:LPAS ss"    # создаем форму команды установки частоты среза фильтра LF СК3-50
            slf = fglf.replace("ss", stLF)  # меняем в форме ss на st
            time.sleep(1)
            ser.write((slf + '\n').encode('utf-8'))
            ser.flush()
            time.sleep(15)
            ser.write(b'RMS?\n') # запрос измеренного значения шумов СК3-50
            ser.flush()
            response = ser.readline()
            decoded_response = response.decode('utf-8')
            amnoise = float(decoded_response) #  
            lfpr = float(n)/1000
            if lfpr == 3.4:
                tolerAmn = 0.01
            elif lfpr == 20:
                tolerAmn = 0.03
            elif lfpr == 60:
                tolerAmn = 0.05
            else:
                tolerAmn = 0.1 
            
            if abs(amnoise) <= tolerAmn:
                compliance = "Да"
            else:
                compliance = "Нет"
            print(f"Am noise {amnoise:.3f} % полоса 0.02", lfpr, "kHz")
            rowAm = [inpf, f'0.02-{lfpr}', round(amnoise, 3),tolerAmn, compliance ]
            rsNoiseAm.append(rowAm)
    # Измерение в полосе фильтра 20Гц-1,5 кГц для частоты 10 кГц      
    if inpf == 0.01:
        ser.write(b'CONF:INP:FILT:HPAS 20\n') # 
        ser.flush()
        time.sleep(1)
        ser.write(b'CONF:INP:FILT:LPAS 1.5kHz\n') # установка фильра LF 3,4 кГц СК3-50
        ser.flush()
        time.sleep(15)
        ser.write(b'RMS?\n') # запрос измеренного значения СК3-50
        ser.flush()
        response = ser.readline()
        decoded_response = response.decode('utf-8')
        amnoise = float(decoded_response) # 
        tolerAmn = 0.01
        if abs(amnoise) <= tolerAmn:
            compliance = "Да"
        else:
            compliance = "Нет"
        print(f"Am noise {amnoise:.3f} % 0,02-1.5кГц")
        rowAm = [inpf, '0.02-1.5', round(amnoise, 3), tolerAmn, compliance ]
        rsNoiseAm.append(rowAm)
    # Измерение в полосе фильтра 20Гц-3,4 кГц для частоты 100 кГц 
    if inpf == 0.1:
        time.sleep(15)
        ser.write(b'RMS?\n') # запрос измеренного значения СК3-50
        ser.flush()
        response = ser.readline()
        decoded_response = response.decode('utf-8')
        amnoise = float(decoded_response) # 
        tolerAmn = 0.01
        if abs(amnoise) <= tolerAmn:
            compliance = "Да"
        else:
            compliance = "Нет"
        print(f"Am noise {amnoise:.3f} % 0.02-3.4кГц")
        rowAm = [inpf,'0.02-3.4', round(amnoise, 3),tolerAmn, compliance ]
        rsNoiseAm.append(rowAm)
        
         
    ###################FM noise # FM шумы измеряются на частотах 50, 250, 500, 1000, 2000, 3000 МГц
    if inpf != 0.01 and inpf != 0.1 and inpf != 100 and inpf != 1500 and inpf != 2500: # 
        ser.write(b'CONF:MODE FM\n') # установка режима FM СК3-50
        ser.flush()
        time.sleep(sleep_time)
        # Измерение на частоте несущей из списка , полоса фильтра СК3-50 0,3 -3,4 кГц
        ser.write(b'CONF:INP:FILT:HPAS 0.3kHz\n') # установка фильра HF 0.3 кГц СК3-50
        ser.flush()
        time.sleep(1)
        ser.write(b'CONF:INP:FILT:LPAS 3.4kHz\n') # установка фильра LF 3.4 кГц СК3-50
        ser.flush()
        time.sleep(15)
        ser.write(b'RMS?\n') # запрос измеренного значения шумов СК3-50
        ser.flush()
        response = ser.readline()
        decoded_response = response.decode('utf-8')
        fmnoise = float(decoded_response) # 
        if inpf == 1: # Измерение на частоте несущей 1 МГц , полоса фильтра СК3-50 0,3 -3,4 кГц
            tolerFmn = 2
        else:
            tolerFmn =  4 * (10**(-9)) * (inpf * 1000000) + 1
       
        if abs(fmnoise) <= tolerFmn:
            compliance = "Да"
        else:
            compliance = "Нет"
            
        print(f"Fm noise {fmnoise:.1f} Гц  0.3-3.4кГц")
        rowFm300 = [inpf,  '0.3-3.4', round(fmnoise, 1),round(tolerFmn, 1),compliance]
        rsNoiseFm.append(rowFm300)
        # End Измерение на частоте несущей из списка , полоса фильтра СК3-50 0,3 -3,4 кГц
        
        ser.write(b'CONF:INP:FILT:HPAS 20\n') # установка фильра HF 20 Гц СК3-50
        ser.flush()
        time.sleep(1)
        # Измерение на частоте несущей 1 МГц , полоса фильтра СК3-50 0,02 -1,5 кГц
        if inpf == 1: 
            ser.write(b'CONF:INP:FILT:LPAS 1.5kHz\n') # установка фильра LF 1.5 кГц СК3-50
            ser.flush()
            time.sleep(15)
            ser.write(b'RMS?\n') # запрос измеренного значения шумов СК3-50
            ser.flush()
            response = ser.readline()
            decoded_response = response.decode('utf-8')
            fmnoise = float(decoded_response) # 
            tolerFmn = 2
            if abs(fmnoise) <= tolerFmn:
                compliance = "Да"
            else:
                compliance = "Нет"
            print(f"Fm noise {fmnoise:.1f} Гц 0.02-1.5кГц")
            rowFm = [inpf,  '0.02-1.5', round(fmnoise, 1), round(tolerFmn, 1),compliance]
            rsNoiseFm.append(rowFm)
        # End Измерение на частоте несущей 1 МГц , полоса фильтра СК3-50 0,02 -1,5 кГц
        # Измерение на частоте несущей из списка, полоса фильтра СК3-50 0,02 -"Значение из списка" кГц
        for n in LFiltr_listFM:
            stLF = str(n)
            fglf = "CONF:INP:FILT:LPAS ss"    # создаем форму команды установки фильтра LF в СК3-50
            slf = fglf.replace("ss", stLF)  # меняем в форме ss на stLF
            time.sleep(1)
            ser.write((slf + '\n').encode('utf-8'))
            ser.flush()
            time.sleep(15)
            ser.write(b'RMS?\n') # запрос измеренного значения СК3-50
            ser.flush()
            response = ser.readline()
            decoded_response = response.decode('utf-8')
            fmnoise = float(decoded_response) # 
            lfpr = float(n)/1000
            if lfpr == 3.4:
                if inpf == 1:
                    tolerFmn = 2
                else:
                    tolerFmn =  4 * (10**(-9)) * (inpf * 1000000) + 1
            if lfpr == 20:
                if inpf == 1:
                    tolerFmn = 4
                else:
                    tolerFmn =  4 * (10**(-8)) * (inpf * 1000000) + 2
            if lfpr == 60:
                if inpf == 1:
                    tolerFmn = 10
                else:
                    tolerFmn =  1 * (10**(-7)) * (inpf * 1000000) + 10
            if lfpr == 200:
                 if inpf == 1:
                     tolerFmn = 30
                 else:
                     tolerFmn =  2 * (10**(-7)) * (inpf * 1000000) + 40
                     
            if abs(fmnoise) <= tolerFmn:
                compliance = "Да"
            else:
                compliance = "Нет"
            print(f"Fm noise {fmnoise:.1f} Гц полоса 0.02", lfpr, "kHz")
            rowFm = [inpf,  f'0.02-{lfpr}', round(fmnoise, 1), round(tolerFmn, 1), compliance ]
            rsNoiseFm.append(rowFm)
          # End Измерение на частоте несущей из списка, полоса фильтра СК3-50 0,02 -"Значение из списка" кГц  
    ################### end FM noise 
      
    ################### PM noise PM шумы измеряются на частотах 1, 10, 50, 250, 500, 1000, 2000, 3000 МГц
    if inpf != 0.01 and inpf != 0.1 and inpf != 100 and inpf != 1500 and inpf != 2500:
         ser.write(b'CONF:MODE PM\n') # установка режима PM СК3-50
         ser.flush()
         time.sleep(sleep_time)
         ser.write(b'CONF:INP:FILT:HPAS 0.3kHz\n') # установка фильра HF 300 Гц СК3-50
         ser.flush()
         time.sleep(1)
         for n in LFiltr_list_Pm:
             stLF = str(n)
             fglf = "CONF:INP:FILT:LPAS ss"    # создаем форму команды установки частоты генератора
             slf = fglf.replace("ss", stLF)  # меняем в форме ss на st
             time.sleep(1)
             ser.write((slf + '\n').encode('utf-8'))
             ser.flush()
             time.sleep(15)
             ser.write(b'RMS?\n') # запрос измеренного значения СК3-50
             ser.flush()
             response = ser.readline()
             decoded_response = response.decode('utf-8')
             pmnoise = float(decoded_response) # 
             lfpr = float(n)/1000
             
             if lfpr == 20: 
                 tolerPmn = 0.003 * (inpf1/1e+9) + 0.003
             if lfpr == 60: 
                 tolerPmn = 0.003 * (inpf1/1e+9) + 0.004
             if lfpr == 200: 
                 tolerPmn = 0.003 * (inpf1/1e+9) + 0.005 
             if abs(pmnoise) <= tolerPmn:
                 compliance = "Да"
             else:
                 compliance = "Нет"
             print(f"Pm noise {pmnoise:.3f} Гц полоса 0.3", lfpr, "kHz")
             rowPm = [inpf,  f'0.3-{lfpr}', round(pmnoise, 3), round(tolerPmn, 3) , compliance ]
             rsNoisePm.append(rowPm)
    #################### PM noise
      
    
    
######################### end  Измерение частоты: АМ noise,FM noise,PM noise,Уровень
####
ser_C6.close()
ser.close() 
Gen.close()
####

dtf1 = pd.DataFrame(rs1, columns=['Уст Частота, Гц', 'Изм Частота, Гц', 'Погрешность, Гц','Допуск, Гц', 'Соотвествие','Частота ПЧ, кГц'])
#dtfnAm300 = pd.DataFrame(rsNoiseAm300, columns=['Уст Частота, Гц', 'Скз шум, %', 'Полоса, кГц'])
dtfnAm = pd.DataFrame( rsNoiseAm, columns=['Уст Частота, Гц', 'Полоса, кГц','Скз шум, %', 'Допуск, %', 'Соотвествие'])
dtfnFm = pd.DataFrame( rsNoiseFm, columns=['Уст Частота, Гц',  'Полоса, кГц', 'Скз шум, Гц','Допуск, Гц', 'Соотвествие'])
dtfnPm = pd.DataFrame( rsNoisePm, columns=['Уст Частота, Гц',  'Полоса, кГц','Скз шум, Рад','Допуск, Рад', 'Соотвествие'])

dtf = pd.DataFrame(rs, columns=['Частота, МГц', 'Уровень, дБм', 'Погрешность, дБм','Допуск, дБ', 'Соотвествие'])
# dtfAm_Fm = pd.DataFrame(rsam_fm, columns=['Преобразование', 'Вверх', 'Вниз','Расчет', 'Допуск'])
# dtfFmpik = pd.DataFrame(rsFmpik, columns=['Fm, кГц', 'Дев част, кГц', '+F, кГц','-F, кГц', '+dF, кГц','-dF, кГц','Допуск, кГц', 'Соотвествие', 'Фильтр, кГц'])
# dtfPpik = pd.DataFrame(rsPmpik, columns=['Fm, Гц', 'Дев фаз, рад', '+P, рад','-P, рад', '+dP, рад','-dP, рад','Допуск, рад', 'Соотвествие','Фильтр, кГц'])
# dtfАmpik = pd.DataFrame(rsАmpik, columns=['F несущая МГц','Fm, Гц', 'Кам, %', '+Кам, %','-Кам, %', '+dКам, %','-dКам, %','Допуск, %', 'Соотвествие', 'Фильтр, кГц'])
# dtfFmpikn = pd.DataFrame(rsFmpikn, columns=['Fm, кГц', 'Дев част, кГц', '+F, кГц','-F, кГц', '+dF, кГц','-dF, кГц','Допуск, кГц', 'Соотвествие', 'Фильтр, кГц', 'Шкала, кГц'])

# dtfTHDam = pd.DataFrame(rsTHDam, columns=['Fm, Гц', 'Кам, %', 'Изм_Кам, %','Изм_КГ_С3-50,%','Изм_КГ_С6-22,%','Допуск, %', 'Соотвествие','Изм_Част_C6-22', 'Фильтр, кГц'])
# dtfTHDfm = pd.DataFrame(rsTHDfm, columns=['Fm, Гц', 'Дев,кГц ', 'Изм_Дев, кГц','Изм_КГ_С3-50,%','Изм_КГ_С6-22,%','Допуск, %', 'Соотвествие','Изм_Част_C6-22', 'Фильтр, кГц'])

dtf1.to_csv("CK350_f"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
dtfnAm.to_csv("CK350_noiseAm"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
dtfnFm.to_csv("CK350_noiseFm"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
dtf.to_csv("CK350_U"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
# dtfAm_Fm.to_csv("CK350_Am_Fm"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
# dtfFmpik.to_csv("CK350_Fmpik"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
# dtfАmpik.to_csv("CK350_Аmpik"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
# dtfFmpikn.to_csv("CK350_Fmpikn"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
# dtfPpik.to_csv("CK350_Pmpik"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv

# dtfTHDam.to_csv("CK350_THDam"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv

# dtfTHDfm.to_csv("CK350_THDfm"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv


with pd.ExcelWriter(safe_filename) as writer:
    dtf1.to_excel(writer, sheet_name='Частота', index=False)
    dtf.to_excel(writer, sheet_name='Уровень', index=False)
    dtfnAm.to_excel(writer, sheet_name='АМ шум СКЗ', index=False)
    dtfnFm.to_excel(writer, sheet_name='FМ шум СКЗ', index=False)
    dtfnPm.to_excel(writer, sheet_name='PМ шум СКЗ', index=False)
    # dtfAm_Fm.to_excel(writer, sheet_name='Коэфф переоб', index=False)
    # dtfTHDam.to_excel(writer, sheet_name='КГ_АМ', index=False)
    # dtfTHDfm.to_excel(writer, sheet_name='КГ_ЧМ', index=False)
    # dtfFmpikn.to_excel(writer, sheet_name='ЧМ_лин', index=False)
   
    # dtfFmpik.to_excel(writer, sheet_name='ЧМ', index=False)
    # dtfАmpik.to_excel(writer, sheet_name='АМ', index=False)
    # dtfPpik.to_excel(writer, sheet_name='PM', index=False)
    
# # выключение OFF вых мощности
data1 = pd.read_csv("CK350_f.csv", index_col = 0) 
dataAm = pd.read_csv("CK350_noiseAm.csv", index_col = 0)
dataFm = pd.read_csv("CK350_noiseFm.csv", index_col = 0)
data = pd.read_csv("CK350.csv", index_col = 0) 
# dataAm_Fm = pd.read_csv("CK350_Am_Fm.csv", index_col = 0)
# dataFmpik = pd.read_csv("CK350_Fmpik.csv", index_col = 0)
# dataFmpikn = pd.read_csv("CK350_Fmpikn.csv", index_col = 0)
# dataАmpik = pd.read_csv("CK350_Аmpik.csv", index_col = 0)
# dataPpik = pd.read_csv("CK350_Pmpik.csv", index_col = 0)

# dataTHDam = pd.read_csv("CK350_THDam.csv", index_col = 0)
# dataTHDfm = pd.read_csv("CK350_THDfm.csv", index_col = 0)
#print(dataAm_Fm)
#print(data1)
#print(data)
#print(dataAm)
#print(dataFm)
#print(dataFmpik)
# print(dataTHDfm )
