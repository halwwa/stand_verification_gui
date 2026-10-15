

rsFmpik = []
rsАmpik = []
rsPmpik = []
rsFmpikn = []


#columns = ["UindBm","UoutdBm","DEL"]
F_list = ['0.01', '0.1','1', '10','50','100','250', '500', '1000', '1500', '2000', '2500', '3000']





Fm_list = ['20', '60','90', '1000', '20000', '30000', '60000']

Pm_list = [ '300', '6000', '60000']

Dpm_k_list = ['100', '10', '1']



F_listAm = ['20','4','1','0.1']
LF_Am_25 = ['0.02', '0.06', '1' , '30', '60']
LF_Am_1 = ['0.02', '0.06', '1' , '6']

Fm_list = ['20',  '60','90', '1000', '20000', '30000', '60000'] # Список модулирующих частот при тестирование шумов режима FM 

############################## FM погрешность
Gen.write('OUTP OFF')
Gen.write('*RST')
Gen.write('FREQ 20 MHz') # устанавливаем частоту генератора
time.sleep(1)
Gen.write('POW 0') # устанавливаем уровень генератора
time.sleep(1)
Gen.write('SOUR:FM:STAT ON') # установка режима FM модуляции
time.sleep(1)
Gen.write('SOUR:FM:SOURce INT')
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 1000')
time.sleep(1)
Gen.write('SOUR:FM:DEV 100kHz')
time.sleep(1)
  

ser.write(b'CONF:MODE FM\n') # Fм режим СК3-50
ser.flush()
time.sleep(5)
 
ser.write(b'CONF:RANG : FM AUTO\n') # автоматическая шкала пределов СК3-50
ser.flush()
time.sleep(5)

ser.write(b'CAL:CURR?\n') # Запуск калибровки FM СК3-50
ser.flush()
time.sleep(20) 

# Ожидаем ответ окончания калибровки
max_attempts = 3
success = False
for attempt in range(max_attempts):
    time.sleep(2)
    response = ser.readline().decode('ascii').strip()
       
    if response == '0':
        print("Получен '0', продолжаем...")
        success = True
        break
    else:
        print(f"Ожидаем '0', текущий ответ: '{response}'")
        time.sleep(1)
if not success:
        print("Не удалось получить '0' за отведённое число попыток.")
        # Завершаем выполнение скрипта
        ser.close()
        sys.exit(0)

Gen.write('OUTP ON') # включаем выход  генератора
time.sleep(1)

# Настройки фильтров
LOW_PASS_FREQ_1 = "CONF:INP:FILT:LPAS 20kHz"
LOW_PASS_FREQ_2 = "CONF:INP:FILT:LPAS 60kHz"
LOW_PASS_FREQ_3 = "CONF:INP:FILT:LPAS 200kHz"

def configure_filter(freq, low_pass_freq):
    ser.write(b'CONF:INP:FILT:HPAS 0.02kHz\n')
    
    ser.flush()
    time.sleep(1)
    ser.write((low_pass_freq + '\n').encode('utf-8'))
    ser.flush()
    time.sleep(1)
   

for n in Fm_list:
    st = str(n)
    stf = float(st)
    fg = "SOUR:LFO:FREQ ss"    # создаем форму команды установки частоты генератора
    s1 = fg.replace("ss", st)  # меняем в форме ss на st
    print(f"f: {st}")
    Gen.write(s1)     # записать команду s1 в Gen 
    time.sleep(1)     # задержка на 1 секунд
    
    # Расчет шумовой добавки в зависимости от установленного фильтра
    if stf in [20, 60, 90, 1000, 6000]:
        delnoise = 4 * (10**(-8)) * 20000000 + 2  
        configure_filter(n, LOW_PASS_FREQ_1)
        filtr = 20
    elif stf in [20000, 30000]:
        delnoise = 1 * (10**(-7)) * 20000000 + 10
        configure_filter(n, LOW_PASS_FREQ_2)
        filtr = 60
    else:
        delnoise = 2 * (10**(-7)) * 20000000 + 40
        configure_filter(n, LOW_PASS_FREQ_3)
        filtr = 200
    if stf in [20, 60]: # Выбор множителя AN в зависимости от модулирующей
        AN = 0.03
    else:
        AN = 0.01
    
    if stf == 1000:
       
        Dfm_k_list = ['1000000', '500000', '100000','30000', '5000','1000', '100' ] # Список значений девиации для измерение погрешности на частоте модулирующей 1кГц
        Dfm_k_nelins = ['1000000', '100000','10000', '1000', '100' ] # Список значений девиации для проверки линейности на частоте модулирующей 1кГц
        
    elif stf == 60000:
        Dfm_k_list = ['1000000', '500000', '100000','30000', '5000','1000' ] # Список значений девиации для измерение погрешности на частоте модулирующей 6кГц
    else:
        Dfm_k_list = ['1000000', '500000', '100000' ] # Список значений девиации для измерение погрешности на других частотах
    
    # Погрешность измерения девиации
    for n in Dfm_k_list:
       st = str(n)
       Dfmk = float(st)
       tolerdFm = AN*Dfmk+3*delnoise # Расчет допуска 
       fg = "SOUR:FM:DEV ss"    # создаем форму команды установки частоты генератора
       s1 = fg.replace("ss", st)  # меняем в форме ss на st
       Gen.write(s1)     # записать команду s1 в Gen 
       print(f"Df: {Dfmk}")
       time.sleep(2)     # задержка на 2 секунд 
       ser.write(b'CONF:POL POS\n')  # Установка измерения положительного пикового значения
       ser.flush()
       time.sleep(10)
       ser.write(b'PEAK?\n') # Измерение пикового значения ЧМ+
       ser.flush()
       time.sleep(1)
       response = ser.readline()
       Fmp = round(float(response), 1)
       print(f"+Fm: {Fmp}")
       dFmp = Fmp - Dfmk   # погрешность +
       ser.write(b'CONF:POL NEG\n') # Установка измерения отрицательного пикового значения
       ser.flush()
       time.sleep(5)
       ser.write(b'PEAK?\n') # Измерение пикового значения ЧМ-
       ser.flush()
       time.sleep(1)
       response = ser.readline()
       Fmm = round(float(response), 1)
       dFmm = Fmm - Dfmk # погрешность -
       max_deviation = max(abs(dFmp), abs(dFmm)) # Поиск максимальной погрешности из + или -
       if max_deviation <= tolerdFm:
           compliance = "Да"
       else:
           compliance = "Нет"
       print(f"-Fm: {Fmm}")
       print(f"Максимальное отклонение: {max_deviation:.1f}")
       print(f"Допустимое отклонение (tolerdFm): {tolerdFm:.1f}")
       rowFmpik = [stf,  Dfmk, Fmp, Fmm, dFmp, dFmm, tolerdFm, compliance, f'0.02-{filtr}' ]
       rowFmpik = [
           round(value / 1000, 3) if isinstance(value, (int, float)) else value
           for value in rowFmpik
       ]
       
       
       rsFmpik.append(rowFmpik)
       
       
    # Проверка линейности шкал: Суть заключается в измерениях вверху шкалы и внизу шкалы не переключая шкалу.
    # Устанавливаем режим ручного управления шкал, устанавливаем шкалу 1МГц, устанавливаем в генераторе девиацию 1 МГц и измеряем СК3-50,
    # Не меняя значение шкалы , устанавливаем в генераторе девиацию 100 кГц и измеряем СК3-50, следующий шаг меняем шкалу на 100кГц и повторяем измерение в вверху шкалы и внизу шкалы.
    if stf == 1000:
        for n in Dfm_k_nelins:
            st = str(n)
            for k in ['1', '10' ]:
                n_value = float(k)
                Dfm_mash = float(st)
                Dfm_nel =  Dfm_mash /n_value
                tolerdFm = AN*Dfm_nel+3*delnoise
                fg = "SOUR:FM:DEV ss"    # создаем форму команды установки частоты генератора
                s1 = fg.replace("ss", str(Dfm_nel))  # меняем в форме ss на st
                Gen.write(s1)     # записать команду s1 в Gen 
                print(f"Df: {Dfm_nel}")
                time.sleep(2)     # задержка на 3 секунд 
                command = f"CONF:RANG:FM {Dfm_mash}\n"
                ser.write(command.encode())
                #ser.write(b'CONF:RANG : FM 1MHZ\n')
                ser.flush()
                time.sleep(2) 
                if Dfm_nel <= 10000:
                    ser.write(b'CONF:INP:FILT:LPAS 3.4kHz\n')
                    filtr = 3.4
                ser.write(b'CONF:POL POS\n')
                ser.flush()
                time.sleep(10)
                ser.write(b'PEAK?\n')
                ser.flush()
                time.sleep(1)
                response = ser.readline()
                Fmpn = round(float(response), 1)
                print(f"+Fm: {Fmpn}")
                dFmpn = Fmpn - Dfm_nel   # погрешность
                ser.write(b'CONF:POL NEG\n')
                ser.flush()
                time.sleep(5)
                ser.write(b'PEAK?\n')
                ser.flush()
                time.sleep(1)
                response = ser.readline()
                Fmmn = round(float(response), 1)
                dFmmn = Fmmn - Dfm_nel
                max_deviation = max(abs(dFmpn), abs(dFmmn))
                if max_deviation <= tolerdFm:
                    compliance = "Да"
                else:
                    compliance = "Нет"
                print(f"-Fm: {Fmmn}")
                print(f"Максимальное отклонение: {max_deviation:.1f}")
                print(f"Допустимое отклонение (tolerdFm): {tolerdFm:.1f}")
               
                rowFmpikn = [stf,  Dfm_nel, Fmpn, Fmmn, dFmpn, dFmmn, tolerdFm, compliance, f'0.02-{filtr}', Dfm_mash]
                rowFmpikn = [
                    round(value / 1000, 3) if isinstance(value, (int, float)) else value
                    for value in rowFmpikn
                ]
                
                rsFmpikn.append(rowFmpikn)
        ser.write(b'CONF:RANG:FM AUTO\n')
        ser.flush()
        time.sleep(5)

############################## end FM погрешность
  
############################## AM погрешность
Gen.write('OUTP OFF')
Gen.write('*RST')
Gen.write('FREQ 20 MHz') # устанавливаем частоту генератора
time.sleep(1)
Gen.write('POW 0') # устанавливаем уровень генератора
time.sleep(1)
Gen.write('SOUR:AM:STAT ON')
time.sleep(1)
Gen.write('SOUR:AM:SOURce INT')
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 1000')
time.sleep(1)
Gen.write('SOUR:AM:DEPT 30')
time.sleep(1)
  

ser.write(b'CONF:MODE AM\n') # АМ режим СК3-50
ser.flush()
time.sleep(5) 

ser.write(b'CAL:CURR?\n') # запускаем  АМ калибровку СК3-50
ser.flush()
time.sleep(20) 

# Ожидаем ответ окончания калибровки
max_attempts = 3
success = False
for attempt in range(max_attempts):
    time.sleep(2)
    response = ser.readline().decode('ascii').strip()
       
    if response == '0':
        print("Получен '0', продолжаем...")
        success = True
        break
    else:
        print(f"Ожидаем '0', текущий ответ: '{response}'")
        time.sleep(1)
if not success:
        print("Не удалось получить '0' за отведённое число попыток.")
        # Завершаем выполнение скрипта
        ser.close()
        sys.exit(0)


Gen.write('OUTP ON')
time.sleep(5)

# Настройки фильтров
LOW_PASS_FREQ_1 = "CONF:INP:FILT:LPAS 20kHz"
LOW_PASS_FREQ_2 = "CONF:INP:FILT:LPAS 60kHz"
LOW_PASS_FREQ_3 = "CONF:INP:FILT:LPAS 200kHz"
LOW_PASS_FREQ_4 = "CONF:INP:FILT:LPAS 1.5kHz"

def configure_filter(freq, low_pass_freq):
    ser.write(b'CONF:INP:FILT:HPAS 0.02kHz\n')
    ser.flush()
    time.sleep(1)
    ser.write((low_pass_freq + '\n').encode('utf-8'))
    ser.flush()
    time.sleep(1)
    
flag_Man_f = 0  # Флаг перехода на ручной ввод несущей, значение Кам выше 60% измериель не корректно мерит несущую, 
# поэтому для больших значений Кам модуляция выключается . измеритель мерит несущую и переводится в ручной режим установки несущей.    
flag_AMT = 0 
flag_Nex_f = 0    
for n in F_listAm:
    stam = str(n)
    fg = "FREQ ss MHz"    # создаем форму команды установки частоты генератора
    s1 = fg.replace("ss", stam)  # меняем в форме ss на st
    Gen.write(s1)     # записать команду s1 в Gen 
    time.sleep(10)     # задержка на 3 секунд
    inpf = float(Gen.ask("FREQ?"))/1000000 # считываем частоту генератора
    flag_Nex_f = not flag_Nex_f
    if  inpf == 20:
        Fm_listAm = ['20', '60', '1000', '30000', '60000']
        #Fm_listAm = ['1000']
        
    elif inpf == 1:
        Fm_listAm = ['20', '60', '1000', '6000']
        #Fm_listAm = [ '1000']
    elif inpf == 4: 
        Fm_listAm = ['1000']
    elif inpf == 0.1: 
        Fm_listAm = ['400']    
    else:
        Fm_listAm = ['1000']
       
    for n in Fm_listAm:
        st = str(n)
        stf = float(st)
        fg = "SOUR:LFO:FREQ ss"    # создаем форму команды установки частоты генератора
        s1 = fg.replace("ss", st)  # меняем в форме ss на st
        print(f"f: {st}")
        Gen.write(s1)     # записать команду s1 в Gen 
        time.sleep(1)     # задержка на 1 секунд
        if stf in [20, 60, 90, 1000, 6000]:
            delnoise = 0.03
            configure_filter(n, LOW_PASS_FREQ_1)
            filtr = 20
        elif stf in [20000, 30000]:
            delnoise = 0.03
            configure_filter(n, LOW_PASS_FREQ_2)
            filtr = 60
        elif stf == 400:
            delnoise = 0.01
            configure_filter(n, LOW_PASS_FREQ_4)
            filtr = 1.5
        else:
            delnoise = 0.03
            configure_filter(n, LOW_PASS_FREQ_3)
            filtr = 200
            
        if stf in [20, 60]:
            Bn = 0.03
        else:
            Bn = 0.01
        
        # Сначала проверяем, нужно ли включить AMT
        if stf in [20, 60, 90]:
            if flag_AMT == 0:  # если ещё не включён
                ser.write(b'CONF:AMT ON\n')
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
            
        if stf == 1000 and inpf != 4:
            Kam_list = ['100', '95', '50', '10', '3', '1']
            #Kam_list = ['95']
        else:
            Kam_list = ['95']
        
        
    
    
         
        for n in Kam_list:
            st = str(n)
            Kamk = float(st)
            
            if Kamk  in [95, 100] :
                if flag_Man_f == 0 :
                    Gen.write('SOUR:AM:STAT OFF')
                    time.sleep(5)
                    ser.write(b'CONF:FREQ:MAN ON\n')
                    ser.flush()
                    flag_Man_f = 1 
                             
                    Gen.write('SOUR:AM:STAT ON')
                    time.sleep(5)
                if  flag_Nex_f == 0:
                    Gen.write('SOUR:AM:STAT OFF')
                    time.sleep(5)
                    ser.write(b'CONF:FREQ:MAN OFF\n')
                    ser.flush()
                    time.sleep(5)
                    ser.write(b'CONF:FREQ:MAN ON\n')
                    ser.flush()
                    time.sleep(5)
                    Gen.write('SOUR:AM:STAT ON')
                    time.sleep(5)
                    flag_Nex_f = 1
             
            else: 
                if flag_Man_f == 1:
                    ser.write(b'CONF:FREQ:MAN OFF\n')
                    ser.flush()
                    time.sleep(10)
                    flag_Man_f = 0
            
                
            
            tolerKam = Bn*Kamk+3*delnoise
            fg = "SOUR:AM:DEPT ss"    # создаем форму команды установки частоты генератора
            s1 = fg.replace("ss", st)  # меняем в форме ss на st
            Gen.write(s1)     # записать команду s1 в Gen 
            print(f"Кам: {Kamk}")
            time.sleep(3)     # задержка на 3 секунд 
            ser.write(b'CONF:POL POS\n')
            ser.flush()
            time.sleep(10)
            ser.write(b'PEAK?\n')
            ser.flush()
            time.sleep(1)
            response = ser.readline()
            Kamp = round(float(response), 2)
            print(f"+Kam: {Kamp}")
            dKamp = Kamp - Kamk   # погрешность
            ser.write(b'CONF:POL NEG\n')
            ser.flush()
            time.sleep(5)
            ser.write(b'PEAK?\n')
            ser.flush()
            time.sleep(1)
            response = ser.readline()
            Kamm = round(float(response), 2)
            dKamm = Kamm - Kamk
            max_kam = max(abs(dKamp), abs(dKamm))
            if max_kam <= tolerKam:
                compliance = "Да"
            else:
                compliance = "Нет"
            print(f"-Кам: {Kamm}")
            print(f"Максимальное отклонение: {max_kam:.1f}")
            print(f"Допустимое отклонение (tolerKam): {tolerKam:.1f}")
            rowАmpik = [inpf, stf,  Kamk, Kamp, Kamm, dKamp, dKamm, tolerKam, compliance, f'0.02-{filtr}' ]
                               
            rsАmpik.append(rowАmpik)
            
ser.write(b'CONF:FREQ:MAN OFF\n')
ser.flush()
time.sleep(10)            
############################## end AM           
 
############################## PM
Gen.write('OUTP OFF')
Gen.write('*RST')
Gen.write('FREQ 20 MHz') # устанавливаем частоту генератора
time.sleep(1)
Gen.write('POW 0') # устанавливаем уровень генератора
time.sleep(1)
Gen.write('SOUR:FM:STAT ON')
time.sleep(1)
Gen.write('SOUR:FM:SOURce INT')
time.sleep(1)
Gen.write('SOUR:LFO:FREQ 1000')
time.sleep(1)
Gen.write('SOUR:FM:DEV 100kHz')
time.sleep(1)
  

ser.write(b'CONF:MODE PM\n') # Pм режим СК3-50
ser.flush()
time.sleep(5) 

ser.write(b'CAL:CURR?\n') # калибровка Pм режим СК3-50
ser.flush()
time.sleep(20) 

max_attempts = 3
success = False
for attempt in range(max_attempts):
    time.sleep(2)
    response = ser.readline().decode('ascii').strip()
       
    if response == '0':
        print("Получен '0', продолжаем...")
        success = True
        break
    else:
        print(f"Ожидаем '0', текущий ответ: '{response}'")
        time.sleep(1)
if not success:
        print("Не удалось получить '0' за отведённое число попыток.")
        # Завершаем выполнение скрипта
        ser.close()
        sys.exit(0)

Gen.write('OUTP ON')
time.sleep(5)

# Настройки фильтров
LOW_PASS_FREQ_1 = "CONF:INP:FILT:LPAS 20kHz"
LOW_PASS_FREQ_2 = "CONF:INP:FILT:LPAS 60kHz"
LOW_PASS_FREQ_3 = "CONF:INP:FILT:LPAS 200kHz"

def configure_filter(freq, low_pass_freq):
    ser.write(b'CONF:INP:FILT:HPAS 0.3kHz\n')
    ser.flush()
    time.sleep(1)
    ser.write((low_pass_freq + '\n').encode('utf-8'))
    ser.flush()
    time.sleep(1)
   

for n in Pm_list:
    st = str(n)
    stf = float(st)
    fg = "SOUR:LFO:FREQ ss"    # создаем форму команды установки частоты генератора
    s1 = fg.replace("ss", st)  # меняем в форме ss на st
    print(f"f: {st}")
    Gen.write(s1)     # записать команду s1 в Gen 
    time.sleep(1)     # задержка на 3 секунд
    if stf in [300]:
        delnoise = 0.003 * 0.02 + 0.003 
        configure_filter(n, LOW_PASS_FREQ_1)
        filtr = 20
    elif stf in [6000]:
        delnoise = 0.003 * 0.02 + 0.004
        configure_filter(n, LOW_PASS_FREQ_2)
        filtr = 60
    else:
        delnoise = 0.003 * 0.02 + 0.005
        configure_filter(n, LOW_PASS_FREQ_3)
        filtr = 200
    
    
    if stf  == 60000 :
        Dpm_k_list = ['10', '1']
    else:
        Dpm_k_list = ['100', '10', '1']
    
    
    for n in Dpm_k_list:
       
        st = str(n)
        stresult = str(int(st) * stf)
        Dpmk = float(st)
           
        tolerdPm = 0.02*Dpmk+3*delnoise
        fg = "SOUR:FM:DEV ss"    # создаем форму команды установки частоты генератора
        s1 = fg.replace("ss", stresult)  # меняем в форме ss на st
        Gen.write(s1)     # записать команду s1 в Gen 
        print(f"Df: {Dpmk}")
        time.sleep(2)     # задержка на 3 секунд 
        ser.write(b'CONF:POL POS\n')
        ser.flush()
        time.sleep(10)
        ser.write(b'PEAK?\n')
        ser.flush()
        time.sleep(1)
        response = ser.readline()
        Pmp = round(float(response), 3)
        print(f"+Pm: {Pmp}")
        dPmp = Pmp - Dpmk   # погрешность
        ser.write(b'CONF:POL NEG\n')
        ser.flush()
        time.sleep(5)
        ser.write(b'PEAK?\n')
        ser.flush()
        time.sleep(1)
        response = ser.readline()
        Pmm = round(float(response), 3)
        dPmm = Pmm - Dpmk
        max_deviation = max(abs(dPmp), abs(dPmm))
        if max_deviation <= tolerdPm:
            compliance = "Да"
        else:
             compliance = "Нет"
        print(f"-Pm: {Pmm}")
        print(f"Максимальное отклонение: {max_deviation:.1f}")
        print(f"Допустимое отклонение (tolerdPm): {tolerdPm:.1f}")
        rowPmpik = [stf,  Dpmk, Pmp, Pmm, dPmp, dPmm, tolerdPm, compliance,  f'0.3-{filtr}' ]
        rowPmpik = [
        round(value, 3) if isinstance(value, (int, float)) else value
        for value in rowPmpik
        ]
            
        rsPmpik.append(rowPmpik)
              
############################## end PM    

 
  dtfFmpik = pd.DataFrame(rsFmpik, columns=['Fm, кГц', 'Дев част, кГц', '+F, кГц','-F, кГц', '+dF, кГц','-dF, кГц','Допуск, кГц', 'Соотвествие', 'Фильтр, кГц'])
  dtfPpik = pd.DataFrame(rsPmpik, columns=['Fm, Гц', 'Дев фаз, рад', '+P, рад','-P, рад', '+dP, рад','-dP, рад','Допуск, рад', 'Соотвествие','Фильтр, кГц'])
  dtfАmpik = pd.DataFrame(rsАmpik, columns=['F несущая МГц','Fm, Гц', 'Кам, %', '+Кам, %','-Кам, %', '+dКам, %','-dКам, %','Допуск, %', 'Соотвествие', 'Фильтр, кГц'])
  dtfFmpikn = pd.DataFrame(rsFmpikn, columns=['Fm, кГц', 'Дев част, кГц', '+F, кГц','-F, кГц', '+dF, кГц','-dF, кГц','Допуск, кГц', 'Соотвествие', 'Фильтр, кГц', 'Шкала, кГц'])

 

 
  dtfFmpik.to_csv("CK350_Fmpik"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
  dtfАmpik.to_csv("CK350_Аmpik"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
  dtfFmpikn.to_csv("CK350_Fmpikn"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv
  dtfPpik.to_csv("CK350_Pmpik"+".csv",index=False, encoding='utf-8') # сохранить датафрейм в csv

 


  with pd.ExcelWriter(safe_filename) as writer:
     
      dtfFmpikn.to_excel(writer, sheet_name='ЧМ_лин', index=False)
     
      dtfFmpik.to_excel(writer, sheet_name='ЧМ', index=False)
      dtfАmpik.to_excel(writer, sheet_name='АМ', index=False)
      dtfPpik.to_excel(writer, sheet_name='PM', index=False)
      
  # # выключение OFF вых мощности
  
  dataFmpik = pd.read_csv("CK350_Fmpik.csv", index_col = 0)
  dataFmpikn = pd.read_csv("CK350_Fmpikn.csv", index_col = 0)
  dataАmpik = pd.read_csv("CK350_Аmpik.csv", index_col = 0)
  dataPpik = pd.read_csv("CK350_Pmpik.csv", index_col = 0)

  