
# Создание пустых списков
rs = []
rs1 = []
rsNoiseAm = [] 
rsNoiseFm = []
rsNoisePm = []
rsam_fm = []
#rsFmpik = []
#rsАmpik = []
#rsPmpik = []
#rsFmpikn = []
rsTHDam = []
rsTHDfm = []


# Инцилизация  списков
F_list = ['0.01', '0.1','1', '10','50','100','250', '500', '1000', '1500', '2000', '2500', '3000'] # Список частот для тестирования в МГц

U_list_0 = ['-13', '0'] # Список уровней тестирования для частот 0,01 и 0,1 МГц

U_list = ['-13', '0', '13'] # Список уровней тестирования кроме частот  0,01 и 0,1 МГц

LFiltr_list = ['3400', '20000', '60000', '200000'] # Список частот 

LFiltr_listFM = ['3400', '20000', '60000', '200000'] # Список частот  фидьтра НЧ при измерениях в режиме  FM

LFiltr_list_Pm = ['20000', '60000', '200000'] # Список частот  фильтра НЧ при измерениях в режиме PM

Fm_list = ['20', '60','90', '1000', '20000', '30000', '60000'] # Список модулирующих частот при тестирование шумов режима FM 

Pm_list = [ '300', '6000', '60000'] # Список модулирующих частот при тестирование шумов режима PM 

# Dpm_k_list = ['100', '10', '1'] # Список частот 

# F_listAm = ['20','4','1','0.1'] # Список частот 

# LF_Am_25 = ['0.02', '0.06', '1' , '30', '60'] # Список модулирующих частот при измерение в режиме AM на частоте 25 МГц

# LF_Am_1 = ['0.02', '0.06', '1' , '6'] # Список модулирующих частот при измерение в режиме AM на частоте 1 МГц

sleep_time=2

tolerdB = 1  # Погрешность при измерение уровня 1 дБ , красная ошибка если более 1 дБ погрешнность. желтая если 0,7 от 1 дБ ( более 70 %) 

###################  Переход АМ-ЧМ ЧМ-АМ

# Переход АМ-ЧМ Настройка SMB100A Частота 20 МГц, Уровень-7дБм,АМ, 20кГц, КАМ = 30%  

Gen.write('OUTP OFF')
Gen.write('*RST')
Gen.write('FREQ 20 MHz') # устанавливаем частоту генератора
time.sleep(1)
Gen.write('POW -7') # устанавливаем уровень генератора
time.sleep(1)
Gen.write('SOUR:AM:STAT ON') # устанавливаем режим АМ модуляции в генераторе
time.sleep(1)
Gen.write('SOUR:AM:SOURce INT') # источник модуляции  внутренний 
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 20000') # частота модулирующего сигнала 20 кГц 
time.sleep(1)
Gen.write('SOUR:AM:DEPT 30') # коэффициент модуляции АМ =30%
time.sleep(1)
Gen.write('OUTP ON')  # включаем выход генератора
time.sleep(1)  


ser.write(b'CONF:MODE FM\n') # Fм режим СК3-50
ser.flush()
time.sleep(1) 

ser.write(b'CONF:INP:FILT:HPAS 0.3kHz\n') # установка фильтра ФВЧ 300Гц СК3-50
ser.flush()
time.sleep(1)
ser.write(b'CONF:INP:FILT:LPAS 20kHz\n') # установка фильтра НЧ 20кГц СК3-50
ser.flush()
time.sleep(15)


ser.write(b'CONF:POL POS\n') # Установка измерения положительного пикового значения
ser.flush()
time.sleep(1)
ser.write(b'PEAK?\n') # Измерение пикового значения ЧМ+
ser.flush()
time.sleep(1)
response = ser.readline()
Dfp = round(float(response), 2)
print(f"+ДЧ: {Dfp}")
time.sleep(1)
ser.write(b'CONF:POL NEG\n') # Установка измерения отрицательного пикового значения
ser.flush()
time.sleep(5)
ser.write(b'PEAK?\n') #Измерение пикового значения -ЧМ
ser.flush()
time.sleep(1)
response = ser.readline()
Dfm = round(float(response), 2)
print(f"-ДЧ: {Dfm}")

if Dfp >=  Dfm: # Поиск какое значение больше + или -
    Kam_fm = Dfp/30 # Расчет перехода АМ  в FM
else:
    Kam_fm = Dfm/30
    
rowam_fm = ['К am_fm', round(Dfp, 1), round(Dfm, 1) , round(Kam_fm, 2), '10 Гц' ]
rsam_fm.append(rowam_fm)  

Gen.write('OUTP OFF')
Gen.write('SOUR:AM:STAT OFF')
time.sleep(1)  
# End переход АМ ЧМ

# Переход ЧМ АМ Настройка SMB100A Частота 100Гц ЧМ, 20кГц, Девиация 200кГц

Gen.write('FREQ 100 MHz') # устанавливаем частоту генератора 100 МГц
time.sleep(1)
Gen.write('POW 0') # устанавливаем уровень генератора 0дБм
time.sleep(1)
Gen.write('SOUR:FM:STAT ON') # Установка режим ЧМ
time.sleep(1)
Gen.write('SOUR:FM:SOURce INT') # источник модуляции  внутренний 
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 20000') # частота модулирующего сигнала 20 кГц 
time.sleep(1)
Gen.write('SOUR:FM:DEV 200kHz') # девиация 200 кГц
time.sleep(1)
Gen.write('OUTP ON')  # включаем выход генератора
time.sleep(1)  

ser.write(b'CONF:MODE AM\n') # Ам режим СК3-50
ser.flush()
time.sleep(1) 

ser.write(b'CONF:INP:FILT:HPAS 0.3kHz\n') # установка фильтра ФВЧ 300Гц СК3-50
ser.flush()
time.sleep(1)
ser.write(b'CONF:INP:FILT:LPAS 20kHz\n') # установка фильтра НЧ 20кГц СК3-50
ser.flush()
time.sleep(15)



ser.write(b'CONF:POL POS\n') # Установка измерения положительного пикового значения
ser.flush()
time.sleep(1)
ser.write(b'PEAK?\n') # Измерение пикового значения АМ+
ser.flush()
time.sleep(1)
response = ser.readline()
Amp = round(float(response), 2)
print(f"+Am: {Amp}")
ser.write(b'CONF:POL NEG\n') # Установка измерения отрицательного пикового значения
ser.flush()
time.sleep(5)
ser.write(b'PEAK?\n') # Измерение пикового значения АМ-
ser.flush()
time.sleep(1)
response = ser.readline()
Amm = round(float(response), 2)
print(f"-Am: {Amm}")

if Amp >=  Amm: # Поиск какое значение больше + или -
    Kfm_am = Amp/200 # Расчет перехода FM в AM
else:
    Kfm_am = Amm/200
    
rowam_fm = ['К fm_am', round(Amp, 1), round(Amm, 1) , round(Kfm_am, 2), '0.02 %' ]
rsam_fm.append(rowam_fm)  

Gen.write('OUTP OFF') # Выключение выхода генератора 
Gen.write('*RST') # Сброс в начальное состояние 

############# end Переход АМ-ЧМ ЧМ-АМ

############# КГ АМ

Gen.write('OUTP OFF')
Gen.write('*RST')
Gen.write('FREQ 20 MHz') # устанавливаем частоту генератора 20 МГц
time.sleep(1)
Gen.write('POW 0') # устанавливаем уровень генератора
time.sleep(1)
Gen.write('SOUR:AM:STAT ON') # устанавливаем режим АМ модуляции генератора
time.sleep(1)
Gen.write('SOUR:AM:SOURce INT') # источник модуляции внутренний
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 1000') # частота модуляции 1кГц
time.sleep(1)
Gen.write('SOUR:AM:DEPT 10') # Коэффициент АМ 10%
time.sleep(1)
  

ser.write(b'CONF:MODE AM\n') # АМ режим СК3-50
ser.flush()
time.sleep(1) 

Gen.write('OUTP ON')
time.sleep(5) # Задержка нужна чтоб измеритель измерил частоты коректно , далее фиксируем ее переходя в ручной режим

ser.write(b'CONF:FREQ:MAN ON\n') # Режим ручного ввода частоты несущей, фиксация последнего измеренного          
ser.flush()
time.sleep(5)

ser.write(b'CONF:THD ON\n') # Включаем измеритель КГ СК3-50 
ser.flush()
time.sleep(1)

ser_C6.write(b'MODE DFM\n') # С6-22 переводим в режим измерения КГ
ser_C6.flush()
time.sleep(1)

ser_C6.write(b'LIMitD AUTO\n') # Установка пределов в режим АВТО
ser_C6.flush()
time.sleep(1)


# Настройки фильтров

LOW_PASS_FREQ_1 = "CONF:INP:FILT:LPAS 3.4kHz"
LOW_PASS_FREQ_2 = "CONF:INP:FILT:LPAS 20kHz"
LOW_PASS_FREQ_3 = "CONF:INP:FILT:LPAS 200kHz"


def configure_filter(freq, low_pass_freq):
    ser.write(b'CONF:INP:FILT:HPAS 0.02kHz\n') # Установка фильра ФВЧ 20Гц СК3-50
    ser.flush()
    time.sleep(1)
    ser.write((low_pass_freq + '\n').encode('utf-8'))
    ser.flush()
    time.sleep(1)
    
  
flag_AMT = 0 
   

Fm_listAm = ['20', '90', '6000', '60000'] # Частоты устанавливаемые в генераторе модулирующего сигнала при которых происходит измерение КГ.
      
for n in Fm_listAm:
    st = str(n)
    stf = float(st)
    fg = "SOUR:LFO:FREQ ss"    # создаем форму команды установки частоты генератора
    s1 = fg.replace("ss", st)  # меняем в форме ss на st
    print(f"f: {st}")
    Gen.write(s1)     # записать команду s1 в Gen 
    time.sleep(1)     # задержка на 1 секунд
    if stf in [20,  90]:  # выбор значение НЧ фильтра в СК3-50 в зависимости от чатоты модуляции
         
        configure_filter(n, LOW_PASS_FREQ_1)
        filtr = 3.4
    elif stf == 6000:
        
        configure_filter(n, LOW_PASS_FREQ_2)
        filtr = 20
   
    else:
       
        configure_filter(n, LOW_PASS_FREQ_3)
        filtr = 200
        
    
    
    # Сначала проверяем, нужно ли включить AMT
    if stf in [20, 90]: # Для частот 20 и 90 Гц нужно включить режим "Постоянная времени АМ"
        if flag_AMT == 0:  # если ещё не включён
            ser.write(b'CONF:AMT ON\n') #  включить режим "Постоянная времени АМ"
            ser.flush()
            flag_AMT = 1
            time.sleep(5)
    # Затем проверяем, нужно ли выключить AMT (для других значений stf)
    else:
        if flag_AMT == 1:  # если был включён
            ser.write(b'CONF:AMT OFF\n')
            ser.flush()
            time.sleep(1)
            flag_AMT = 0
        
    Kam_list = ['30', '95'] # Значение коэффициента модуляции при которых происходит измерение КГ  
         
    for n in Kam_list:
        st = str(n)
        Kamk = float(st)
       
        fg = "SOUR:AM:DEPT ss"    # создаем форму команды установки частоты генератора
        s1 = fg.replace("ss", st)  # меняем в форме ss на st
        Gen.write(s1)     # записать команду s1 в Gen 
        print(f"Кам: {Kamk}")
        time.sleep(2)     # задержка на 2 секунд 
        ser.write(b'CONF:POL POS\n') # Установка измерения положительного пикового значения
        ser.flush()
        time.sleep(10)
        ser.write(b'PEAK?\n') # Измерение пикового значения АМ+
        ser.flush()
        time.sleep(1)
        response = ser.readline()
        Kamp = round(float(response), 2)
        print(f"+Kam: {Kamp}")
        time.sleep(20) # Измеритель С6-22 очень долго настраивается поэтому такая задержка 
        ser_C6.write(b'MEASure:THD?\n') # Измерение КГ С6-22
        ser_C6.flush()
        time.sleep(2)
        # Читаем ответ  через Serial порт
        response = ser_C6.readline()
        
        cleaned_response = response.decode('utf-8').replace('PCT', '').replace('\n', '')
        # Преобразуем в число
        thd_res = float(cleaned_response)
        print(f"Измеренное КГ,%: {thd_res}")
        ser_C6.write(b'MEASure:FREQuency?\n') # Измерение частоты модулирующей С6-22
        ser_C6.flush()
        time.sleep(2)
        # Читаем ответ  через Serial порт
        response = ser_C6.readline()
        Flo_res = response.decode('utf-8').replace('\n', '')
        # Преобразуем в число
        print(f"Частота НЧ С6-22: {Flo_res}")
        ser.write(b'THD?\n') # Измерение КГ СК3-50
        ser.flush()
        time.sleep(1)
        response = ser.readline()
        THD_CK3 = round(float(response), 3)
        print(f"КГ_СК3-50: {THD_CK3}")
        
        if Kamk == 30 and stf in [20,90]: 
            tolerTHDam = 0.15
        elif Kamk == 30 and stf in [6000]:
            tolerTHDam = 0.2
        elif Kamk == 95 and stf in [60000]:
           tolerTHDam = 0.4  
        else:
            tolerTHDam = 0.3
      
        if thd_res <= tolerTHDam:
            compliance = "Да"
        else:
            compliance = "Нет"
        
        print(f"Допустимое отклонение (tolerTHDam): {tolerTHDam:.2f}")
        rowTHDam = [ stf,  Kamk, Kamp, THD_CK3, thd_res,   tolerTHDam, compliance, f'{Flo_res}',  f'0.02-{filtr}']
                           
        rsTHDam.append(rowTHDam)
        
 # Выключение режимов в приборах       
Gen.write('OUTP OFF') 
ser.write(b'CONF:THD OFF\n')
ser.flush()
time.sleep(1)           
ser.write(b'CONF:FREQ:MAN OFF\n')
ser.flush()
time.sleep(1) 

  # С6-22 вернуть в режим измерения напряжения, ручная шкала , 100 В 
ser_C6.write(b'MODE VM\n')
ser_C6.flush()
time.sleep(1)
ser_C6.write(b'LIMitD MAN\n')
ser_C6.flush()
time.sleep(1)
ser_C6.write(b'RANgeD 100V\n')
ser_C6.flush()
time.sleep(1)    
      
################# end КГ АМ

############# КГ ЧМ
Gen.write('OUTP OFF')
Gen.write('*RST')
Gen.write('FREQ 20 MHz') # устанавливаем частоту генератора
time.sleep(1)
Gen.write('POW 0') # устанавливаем уровень генератора
time.sleep(1)
Gen.write('SOUR:FM:STAT ON') # устанавливаем режим FM
time.sleep(1)
Gen.write('SOUR:FM:SOURce INT') # источник модуляции внутренний
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 1000') # частота модуляции 1кГц
time.sleep(1)
Gen.write('SOUR:FM:DEV 100kHz') # девиация 100кГц
time.sleep(1)
  

ser.write(b'CONF:MODE FM\n') # Fм режим СК3-50
ser.flush()
time.sleep(1) 

Gen.write('OUTP ON') # выход генератора вкл.
time.sleep(1)



ser.write(b'CONF:THD ON\n') # режим измерения КГ СК3-50
ser.flush()
time.sleep(1)

ser_C6.write(b'MODE DFM\n') # режим измерения КГ С6-22
ser_C6.flush()
time.sleep(1)

ser_C6.write(b'LIMitD AUTO\n') # режим измерения Авто С6-22
ser_C6.flush()
time.sleep(1)

# Настройки фильтров

LOW_PASS_FREQ_1 = "CONF:INP:FILT:LPAS 3.4kHz"
LOW_PASS_FREQ_2 = "CONF:INP:FILT:LPAS 20kHz"
LOW_PASS_FREQ_3 = "CONF:INP:FILT:LPAS 60kHz"
LOW_PASS_FREQ_4 = "CONF:INP:FILT:LPAS 200kHz"


def configure_filter(freq, low_pass_freq):
    ser.write(b'CONF:INP:FILT:HPAS 0.02kHz\n')
    ser.flush()
    time.sleep(1)
    ser.write((low_pass_freq + '\n').encode('utf-8'))
    ser.flush()
    time.sleep(1)
    
  
 
   

Fm_listAm = ['20', '1000', '6000', '20000',  '60000', '16650', '9810','6970'] # список модулирующих частот при измерение КГ ЧМ
      
for n in Fm_listAm:
    st = str(n)
    stf = float(st)
    fg = "SOUR:LFO:FREQ ss"    # создаем форму команды установки частоты генератора
    s1 = fg.replace("ss", st)  # меняем в форме ss на st
    print(f"f: {st}")
    Gen.write(s1)     # записать команду s1 в Gen 
    time.sleep(1)     # задержка на 3 секунд
    if stf in [20, 1000]: # Установка фильра НЧ в зависимости от модулирующей частоты
         
        configure_filter(n, LOW_PASS_FREQ_1)
        filtr = 3.4
    elif stf in [6000, 16650, 9810,6970]:
        
        configure_filter(n, LOW_PASS_FREQ_2)
        filtr = 20
    
    elif stf == 20000:
        
        configure_filter(n, LOW_PASS_FREQ_3)
        filtr = 60
    else:
       
        configure_filter(n, LOW_PASS_FREQ_4)
        filtr = 200
        
    if stf in [ 16650, 9810,6970]:
        Gen.write('SOUR:LFO:SHAP SQU')
        KFm_list = ['500000']
    else:
        Gen.write('SOUR:LFO:SHAP SIN')
        KFm_list = ['300000', '500000','1000000'] 
    
   
        
   
         
    for n in KFm_list:
        st = str(n)
        Dfmk = float(st)
       
        fg = "SOUR:FM:DEV ss"    # создаем форму команды установки частоты генератора
        s1 = fg.replace("ss", st)  # меняем в форме ss на st
        Gen.write(s1)     # записать команду s1 в Gen 
        print(f"Df: {Dfmk}")
        time.sleep(2)     # задержка на 2 секунд 
        ser.write(b'CONF:POL POS\n') # Установка измерения положительного пикового значения
        ser.flush()
        time.sleep(10)
        
        ser.write(b'PEAK?\n') # Измеренени пикового значения
        ser.flush()
        time.sleep(1)
        response = ser.readline()
        Dfmp = round(float(response), 2)
        print(f"Dfm: {Dfmp}")
        time.sleep(20) # Измеритель С6-22 очень медленно настраивается
        ser_C6.write(b'MEASure:THD?\n') # Измеренени КГ С6-22
        ser_C6.flush()
        time.sleep(2)
        # Читаем ответ  через Serial порт
        response = ser_C6.readline()
        
        cleaned_response = response.decode('utf-8').replace('PCT', '').replace('\n', '')
        # Преобразуем в число
        thd_res = round(float(cleaned_response), 3)
        print(f"Измеренное КГ,%: {thd_res}")
        ser_C6.write(b'MEASure:FREQuency?\n') # Измерение С6-22 частоты модулирующей 
        ser_C6.flush()
        time.sleep(2)
        # Читаем ответ  через Serial порт
        response = ser_C6.readline()
        Flo_res = response.decode('utf-8').replace('\n', '')
        # Преобразуем в число
        print(f"Частота НЧ С6-22: {Flo_res}")
        
        ser.write(b'THD?\n') # Измерение КГ СК3-50
        ser.flush()
        time.sleep(2)
        response = ser.readline()
        THD_CK3 = round(float(response), 3)
        print(f"КГ_СК3-50: {THD_CK3}")
        
       
        
        tolerTHDam = 0.1*thd_res+0.03
        delthd_res = THD_CK3 - thd_res
        
        if delthd_res <= tolerTHDam:
            compliance = "Да"
        else:
            compliance = "Нет"
        
        print(f"Допустимое отклонение (tolerTHDam): {tolerTHDam:.2f}")
        rowTHDfm = [ stf,  Dfmk, Dfmp, THD_CK3, thd_res,   tolerTHDam, compliance, f'{Flo_res}',  f'0.02-{filtr}']
                           
        rsTHDfm.append(rowTHDfm)
        
  # Выключение выхода и режимов      
Gen.write('OUTP OFF') 
ser.write(b'CONF:THD OFF\n')
ser.flush()
time.sleep(1) 

 # С6-22 вернуть в режим измерения напряжения, ручная шкала , 100 В 
ser_C6.write(b'MODE VM\n')
ser_C6.flush()
time.sleep(1)
ser_C6.write(b'LIMitD MAN\n')
ser_C6.flush()
time.sleep(1)
ser_C6.write(b'RANgeD 100V\n')
ser_C6.flush()
time.sleep(1)            
          
############################## end КГ FM


dtfAm_Fm = pd.DataFrame(rsam_fm, columns=['Преобразование', 'Вверх', 'Вниз','Расчет', 'Допуск'])

dtfTHDam = pd.DataFrame(rsTHDam, columns=['Fm, Гц', 'Кам, %', 'Изм_Кам, %','Изм_КГ_С3-50,%','Изм_КГ_С6-22,%','Допуск, %', 'Соотвествие','Изм_Част_C6-22', 'Фильтр, кГц'])
dtfTHDfm = pd.DataFrame(rsTHDfm, columns=['Fm, Гц', 'Дев,кГц ', 'Изм_Дев, кГц','Изм_КГ_С3-50,%','Изм_КГ_С6-22,%','Допуск, %', 'Соотвествие','Изм_Част_C6-22', 'Фильтр, кГц'])


dtfAm_Fm.to_csv("CK350_Am_Fm"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv


dtfTHDam.to_csv("CK350_THDam"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv

dtfTHDfm.to_csv("CK350_THDfm"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv


with pd.ExcelWriter(safe_filename) as writer:

    dtfAm_Fm.to_excel(writer, sheet_name='Коэфф переоб', index=False)
    dtfTHDam.to_excel(writer, sheet_name='КГ_АМ', index=False)
    dtfTHDfm.to_excel(writer, sheet_name='КГ_ЧМ', index=False)

   

    
# # выключение OFF вых мощности

dataAm_Fm = pd.read_csv("CK350_Am_Fm.csv", index_col = 0)

dataTHDam = pd.read_csv("CK350_THDam.csv", index_col = 0)
dataTHDfm = pd.read_csv("CK350_THDfm.csv", index_col = 0)