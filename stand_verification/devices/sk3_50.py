class SK350:
    """SK3-50 request/decode operations; connection ownership stays with caller."""

    def __init__(self, session):
        self.session = session
        self.last_cal_response = ""   # диагностика: последний ответ при калибровке
        self._dead_session = None     # ссылка на отравленный makefile (не даём GC закрыть сокет)
        self._raw_sock = getattr(session, "_raw_sock", None)  # сокет под makefile (LAN)

    # ---------- низкоуровневое чтение строки (COM и LAN) ----------

    @staticmethod
    def _read_raw(session):
        """Выполняет одно чтение доступным способом, вернёт bytes/str/None."""
        readline = getattr(session, "readline", None)
        if callable(readline):
            return readline()
        read = getattr(session, "read", None)
        if callable(read):
            return read()
        recv = getattr(session, "recv", None)
        if callable(recv):
            return recv(4096)
        raise RuntimeError(
            "Сессия не поддерживает ни readline(), ни read(), ни recv()"
        )

    def _read_line(self):
        """
        Читает один ответ прибора. Единая точка входа для разных транспортов:
          * pyserial (COM)   -> session.readline()
          * pyVISA (LAN)     -> session.read()      (у pyVISA НЕТ readline!)
          * raw socket (LAN) -> session.readline()  (makefile('rwb') над сокетом)
        Возвращает строку, очищенную от пробелов/переводов строк.

        После таймаута объект makefile навсегда отравлен: любое чтение даёт
        OSError 'cannot read from timed out object'. Ловим это, пересоздаём
        makefile поверх того же сокета и повторяем чтение один раз.
        """
        try:
            raw = self._read_raw(self.session)
        except OSError as e:
            if "timed out object" not in str(e) or not self._rebind_makefile():
                raise
            raw = self._read_raw(self.session)

        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="ignore")
        else:
            text = "" if raw is None else str(raw)
        return text.strip()

    def _write(self, command):
        self.session.write(command)
        try:
            self.session.flush()
        except Exception:
            pass

    # ---------- управление таймаутом транспорта ----------

    def _get_raw_socket(self):
        """Достаёт настоящий сокет из session.

        open_socket() сохраняет его в session._raw_sock — это основной путь.
        Запасные пути для старых сессий: до Python 3.14 makefile('rwb')
        возвращал io.BufferedRandom (session.raw -> socket.SocketIO,
        у SocketIO сокет в _sock), начиная с 3.14 — io.BufferedRWPair,
        у которого ни .raw, ни settimeout нет. Для pyVISA вернётся None —
        там другой механизм.
        """
        if self._raw_sock is not None:
            return self._raw_sock
        obj = self.session
        raw = getattr(obj, "raw", None)
        if raw is not None:
            for attr in ("_sock", "sock"):
                sock = getattr(raw, attr, None)
                if sock is not None:
                    return sock
            if callable(getattr(raw, "settimeout", None)):
                return raw                     # SocketIO сам умеет settimeout
        if callable(getattr(obj, "settimeout", None)):
            return obj
        return None

    def _set_read_timeout(self, seconds):
        """Поднимает таймаут чтения под длительную операцию.

        socket / pyserial: секунды; pyVISA: миллисекунды.
        Ошибки глушим сознательно: если транспорт не поддерживает смену
        таймаута, ответ всё равно может быть вычитан циклом.
        """
        sock = self._get_raw_socket()
        if sock is not None:
            try:
                sock.settimeout(seconds)
                return
            except Exception:
                pass
        session = self.session
        try:
            if hasattr(session, "timeout") and callable(getattr(session, "read", None)):
                session.timeout = int(seconds * 1000)      # pyVISA: мс
        except Exception:
            pass

    def _flush_input(self):
        """Сбрасывает возможные 'поздние' данные после сорвавшегося чтения.

        Без этого зависший ответ калибровки ('0') остаётся в буфере и
        следующее чтение (например, PEAK?) примет его за свой ответ.
        """
        sock = self._get_raw_socket()
        if sock is not None:
            try:
                old = sock.gettimeout()
                sock.settimeout(0.05)
                while sock.recv(4096):
                    pass
            except Exception:
                pass
            finally:
                try:
                    sock.settimeout(old if old is not None else 5)
                except Exception:
                    pass
            return
        session = self.session
        clear = getattr(session, "clear", None)            # pyVISA: viClear
        if callable(clear):
            try:
                clear()
                return
            except Exception:
                pass
        reset = getattr(session, "reset_input_buffer", None)  # pyserial
        if callable(reset):
            try:
                reset()
            except Exception:
                pass

    def _rebind_makefile(self):
        """Пересоздаёт makefile после отравления по таймауту.

        Объект, полученный через sock.makefile('rwb'), после первого
        socket.timeout становится навсегда неисправным: любое чтение
        даёт OSError 'cannot read from timed out object'. Лечится
        только пересозданием объекта поверх того же сокета.
        Старую ссылку сохраняем, чтобы сборщик мусора не закрыл сокет.
        Возвращает True, если makefile пересоздан.
        """
        sock = self._get_raw_socket()
        if sock is None:
            return False
        try:
            self._dead_session = self.session
            self.session = sock.makefile("rwb")
            self._raw_sock = sock
            return True
        except Exception:
            return False

    # ---------- частота / уровень ----------

    def _read_float(self, command):
        self._write(command)
        return float(self._read_line())

    def read_frequency_hz(self):
        return self._read_float(b"FREQ?\n")

    def read_if_khz(self):
        self._write(b"FREQ:INT?\n")
        try:
            return float(self._read_line()) / 1000.0
        except ValueError as e:
            raise ValueError(f"Некорректный разбор частоты ПЧ: {e}")

    def read_power_dbm(self):
        return self._read_float(b"POW?\n")

    # ---------- режимы модуляции ----------

    def set_mode_am(self):
        self._write(b"CONF:MODE AM\n")

    def set_mode_fm(self):
        self._write(b"CONF:MODE FM\n")

    def set_mode_pm(self):
        self._write(b"CONF:MODE PM\n")

    # ---------- фильтры ----------

    def set_filter_hp_khz(self, value_khz):
        self._write(f"CONF:INP:FILT:HPAS {value_khz:g}kHz\n".encode("utf-8"))

    def set_filter_hp_hz(self, value_hz):
        self._write(f"CONF:INP:FILT:HPAS {value_hz:g}\n".encode("utf-8"))

    def set_filter_lp_khz(self, value_khz):
        self._write(f"CONF:INP:FILT:LPAS {value_khz:g}kHz\n".encode("utf-8"))

    # ---------- СКЗ / пик / КГ ----------

    def read_rms(self):
        return self._read_float(b"RMS?\n")

    def set_polarity_pos(self):
        self._write(b"CONF:POL POS\n")

    def set_polarity_neg(self):
        self._write(b"CONF:POL NEG\n")

    def read_peak(self):
        return self._read_float(b"PEAK?\n")

    def set_thd_on(self):
        self._write(b"CONF:THD ON\n")

    def set_thd_off(self):
        self._write(b"CONF:THD OFF\n")

    def read_thd(self):
        return self._read_float(b"THD?\n")

    def set_freq_manual_on(self):
        self._write(b"CONF:FREQ:MAN ON\n")

    def set_freq_manual_off(self):
        self._write(b"CONF:FREQ:MAN OFF\n")

    def set_amt_on(self):
        self._write(b"CONF:AMT ON\n")

    def set_amt_off(self):
        self._write(b"CONF:AMT OFF\n")

    # ---------- Калибровка и шкалы (для Тестов 9–12) ----------

    def set_range_fm_auto(self):
        """CONF:RANG:FM AUTO — автоматический выбор шкалы девиации."""
        self._write(b"CONF:RANG:FM AUTO\n")

    def set_range_fm_hz(self, value_hz):
        """CONF:RANG:FM <value> — ручная шкала девиации (например 1000000)."""
        self._write(f"CONF:RANG:FM {int(value_hz)}\n".encode("utf-8"))

    def cal_current(self, timeout_s=50.0, attempts=3, attempt_wait_s=2.0):
        """CAL:CURR? — запуск калибровки. Ждёт ответ '0' в течение timeout_s.

        Стратегия — как по COM: короткие чтения-опросы вместо одного
        блокирующего ожидания. По LAN читаем напрямую из сокета
        (recv с таймаутом attempt_wait_s): socket.timeout при опросе
        безопасен для сокета, а объект makefile после первого таймаута
        становится неисправным (OSError 'cannot read from timed out
        object'), поэтому во время калибровки makefile не используется —
        после калибровки он остаётся чистым для обычных измерений.

        Первый опрос — сразу после команды, без начальной паузы.
        Последний ответ сохраняется в self.last_cal_response.
        """
        import time as _time

        self.last_cal_response = ""
        try:
            self._write(b"CAL:CURR?\n")
        except Exception as e:
            self.last_cal_response = f"<write error: {type(e).__name__}: {e}>"
            return False

        sock = self._get_raw_socket()
        if sock is not None:
            # LAN: опрос сокета напрямую, makefile в стороне
            try:
                old_timeout = sock.gettimeout()
            except Exception:
                old_timeout = None
            poll_timeout = attempt_wait_s if attempt_wait_s > 0 else 2.0
            try:
                sock.settimeout(poll_timeout)
            except Exception:
                poll_timeout = old_timeout if old_timeout else 2.0

            deadline = _time.monotonic() + timeout_s
            buf = b""
            try:
                while _time.monotonic() < deadline:
                    try:
                        data = sock.recv(4096)
                    except Exception:
                        continue            # прибор ещё не готов — опрашиваем дальше
                    if not data:
                        self.last_cal_response = "<connection closed by peer>"
                        return False
                    buf += data
                    text = buf.decode("utf-8", errors="ignore")
                    self.last_cal_response = text.strip()

                    # строка, завершённая переводом строки (с \r или без)
                    lines = [ln.strip().lstrip("+")
                             for ln in text.splitlines() if ln.strip()]
                    if any(ln == "0" for ln in lines):
                        return True
                # ответ мог прийти совсем без терминатора
                if text.strip().lstrip("+") == "0":
                    return True
                return False
            finally:
                try:
                    sock.settimeout(old_timeout if old_timeout is not None else 2.0)
                except Exception:
                    pass

        # Fallback: pyserial (COM) и pyVISA — обычный цикл через _read_line
        deadline = _time.monotonic() + timeout_s
        while _time.monotonic() < deadline:
            try:
                response = self._read_line()
            except Exception as e:
                response = ""
                self.last_cal_response = f"<read error: {type(e).__name__}: {e}>"
                continue
            if response:
                self.last_cal_response = response
            if response.strip().lstrip("+") == "0":
                return True
            _time.sleep(attempt_wait_s if attempt_wait_s > 0 else 2.0)
        return False
