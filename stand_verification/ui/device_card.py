import threading
import tkinter as tk
from tkinter import ttk

import serial.tools.list_ports
import pyvisa

from stand_verification.devices.connections import (
    close_resources, open_serial, open_visa,
)


class DeviceCard:
    def __init__(self, parent, title, kind, defaults, on_log, on_parsed=None,
                 dispatch=None):
        self.title = title
        self.kind = kind
        self.on_log = on_log
        self.on_parsed = on_parsed
        self.dispatch = dispatch
        self.worker = None
        self.locked = False
        self.inst = None
        self.rm = None
        self.frame = ttk.LabelFrame(parent, text=title, padding=10)
        self.settings = ttk.Frame(self.frame)
        self.settings.pack(fill="x")
        if kind == "com":
            ttk.Label(self.settings, text="Порт:").grid(row=0, column=0, sticky="w")
            self.port_var = tk.StringVar(value=defaults.get("port", ""))
            self.port_cb = ttk.Combobox(self.settings, textvariable=self.port_var,
                                        values=self._list_ports(), width=10)
            self.port_cb.grid(row=0, column=1, padx=(4, 12))
            ttk.Label(self.settings, text="Baud:").grid(row=0, column=2, sticky="w")
            self.baud_var = tk.StringVar(value=str(defaults.get("baud", 9600)))
            self.baud_cb = ttk.Combobox(self.settings, textvariable=self.baud_var,
                                        values=["9600", "19200", "38400", "57600", "115200"],
                                        width=8)
            self.baud_cb.grid(row=0, column=3, padx=(4, 12))
        else:
            ttk.Label(self.settings, text="IP:").grid(row=0, column=0, sticky="w")
            self.ip_var = tk.StringVar(value=defaults.get("ip", "192.168.0.113"))
            ttk.Entry(self.settings, textvariable=self.ip_var, width=16).grid(
                row=0, column=1, padx=(4, 12))
            ttk.Label(self.settings, text="Порт:").grid(row=0, column=2, sticky="w")
            self.lanport_var = tk.StringVar(value=str(defaults.get("lan_port", 5025)))
            ttk.Entry(self.settings, textvariable=self.lanport_var, width=8).grid(
                row=0, column=3, padx=(4, 12))
        self.status_row = ttk.Frame(self.frame)
        self.status_row.pack(fill="x", pady=(8, 0))
        ttk.Label(self.status_row, text="Статус:").pack(side="left")
        self.status_var = tk.StringVar(value="● Откл.")
        self.status_lbl = ttk.Label(self.status_row, textvariable=self.status_var,
                                    foreground="gray")
        self.status_lbl.pack(side="left", padx=(6, 0))
        self.connect_btn = ttk.Button(self.status_row, text="Подключить",
                                      command=self.on_connect_click)
        self.connect_btn.pack(side="right")
        self.answer_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.answer_var, foreground="#333",
                  wraplength=500, justify="left").pack(fill="x", pady=(6, 0))

    @staticmethod
    def _list_ports():
        try:
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    @staticmethod
    def _parse_idn(idn_str):
        parts = [p.strip() for p in idn_str.split(",")]
        result = {"manufacturer": "", "model": "", "serial": "", "version": "", "raw": idn_str}
        for key, index in (("manufacturer", 0), ("model", 1), ("serial", 2), ("version", 3)):
            if len(parts) > index:
                result[key] = parts[index]
        return result

    def on_connect_click(self):
        if self.locked or (self.worker and self.worker.is_alive()):
            return
        if self.inst is not None:
            self.disconnect()
            return
        self.connect_btn.state(["disabled"])
        self.set_status("● Подключение...", "orange")
        self.answer_var.set("")
        try:
            settings = ((self.port_var.get().strip(), int(self.baud_var.get().strip() or '9600'))
                        if self.kind == 'com' else
                        (self.ip_var.get().strip(), int(self.lanport_var.get().strip() or '5025')))
        except ValueError as e:
            self._on_error(str(e))
            return
        self.worker = threading.Thread(target=self._connect_worker, args=(settings,))
        self.worker.start()

    def _connect_worker(self, settings):
        inst = rm = None
        try:
            if self.kind == "com":
                port, baud = settings
                if not port:
                    raise ValueError("Не выбран COM-порт")
                inst, idn = open_serial(serial, port, baud)
            else:
                ip, port = settings
                if not ip:
                    raise ValueError("Не введён IP-адрес")
                rm, inst, idn = open_visa(pyvisa, ip, port)
            self.inst, self.rm = inst, rm
            shown_idn = idn or "(пустой ответ)" if self.kind == "com" else idn
            self.dispatch(lambda: self._on_connected(shown_idn))
        except Exception as e:
            close_resources(inst, rm)
            err = str(e)
            self.dispatch(lambda: self._on_error(err))

    def _on_connected(self, idn):
        self.set_status("● Подключён", "green")
        self.answer_var.set(idn)
        self.connect_btn.state(["disabled" if self.locked else "!disabled"])
        self.connect_btn.configure(text="Отключить")
        self.on_log(f"{self.title}: подключён ({idn})")
        if self.on_parsed is not None:
            try:
                self.on_parsed(self._parse_idn(idn))
            except Exception as e:
                self.on_log(f"{self.title}: ошибка разбора *IDN? — {e}")

    def _on_error(self, err):
        self.set_status("● Ошибка", "red")
        self.answer_var.set(f"❌ {err}")
        self.connect_btn.state(["disabled" if self.locked else "!disabled"])
        self.connect_btn.configure(text="Подключить")
        self.on_log(f"{self.title}: ошибка подключения — {err}")

    def disconnect(self):
        if self.locked or (self.worker and self.worker.is_alive()):
            return
        close_resources(self.inst, self.rm)
        self.inst = self.rm = None
        self.set_status("● Откл.", "gray")
        self.answer_var.set("")
        self.connect_btn.configure(text="Подключить")
        self.on_log(f"{self.title}: отключён")

    def set_status(self, text, color):
        self.status_var.set(text)
        self.status_lbl.configure(foreground=color)

    def is_connected(self):
        return self.inst is not None
