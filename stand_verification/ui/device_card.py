import socket
import threading
import tkinter as tk
from tkinter import ttk

import serial.tools.list_ports
import pyvisa

from stand_verification.devices.connections import (
    close_resources, open_serial, open_socket, open_visa,
)


PORT_POLL_INTERVAL_MS = 1000


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

        self.connection_var = tk.StringVar(value="LAN" if kind == "lan" else "COM")
        self.port_var = tk.StringVar(value=defaults.get("port", ""))
        self.baud_var = tk.StringVar(value=str(defaults.get("baud", 9600)))
        self.ip_var = tk.StringVar(value=defaults.get("ip", ""))
        self.lanport_var = tk.StringVar(value=str(defaults.get("lan_port", 5025)))
        self.connection_cb = None
        self._shown_transport = None
        self._ports = self._list_ports() if kind in ("com", "com_lan") else []

        if kind == "com_lan":
            ttk.Label(self.settings, text="Подключение:").grid(
                row=0, column=0, sticky="w")
            self.connection_cb = ttk.Combobox(
                self.settings, textvariable=self.connection_var,
                values=("COM", "LAN"), state="readonly", width=8)
            self.connection_cb.grid(row=0, column=1, sticky="w", padx=(4, 12))
            self.connection_cb.bind("<<ComboboxSelected>>", self._on_connection_changed)

        self.com_frame = ttk.Frame(self.settings)
        ttk.Label(self.com_frame, text="Порт:").grid(row=0, column=0, sticky="w")
        self.port_cb = ttk.Combobox(
            self.com_frame, textvariable=self.port_var, values=self._ports,
            width=10, postcommand=self.refresh_ports)
        self.port_cb.grid(row=0, column=1, padx=(4, 4))
        ttk.Button(self.com_frame, text="↻", width=3,
                   command=self.refresh_ports).grid(row=0, column=2, padx=(0, 12))
        ttk.Label(self.com_frame, text="Baud:").grid(row=0, column=3, sticky="w")
        self.baud_cb = ttk.Combobox(
            self.com_frame, textvariable=self.baud_var,
            values=["9600", "19200", "38400", "57600", "115200"], width=8)
        self.baud_cb.grid(row=0, column=4, padx=(4, 0))

        self.lan_frame = ttk.Frame(self.settings)
        ttk.Label(self.lan_frame, text="IP/Hostname:").grid(
            row=0, column=0, sticky="w")
        ttk.Entry(self.lan_frame, textvariable=self.ip_var, width=16).grid(
            row=0, column=1, padx=(4, 12))
        ttk.Label(self.lan_frame, text="Порт:").grid(row=0, column=2, sticky="w")
        ttk.Entry(self.lan_frame, textvariable=self.lanport_var, width=8).grid(
            row=0, column=3, padx=(4, 0))

        self.load_settings()
        self._show_connection_settings()

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

        if kind in ("com", "com_lan"):
            self.frame.after(PORT_POLL_INTERVAL_MS, self._poll_ports)

    @staticmethod
    def _list_ports():
        try:
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def refresh_ports(self):
        ports = self._list_ports()
        if ports != self._ports:
            self._ports = ports
            self.port_cb.configure(values=ports)
        return ports

    def _poll_ports(self):
        try:
            if not self.frame.winfo_exists():
                return
            self.refresh_ports()
            self.frame.after(PORT_POLL_INTERVAL_MS, self._poll_ports)
        except tk.TclError:
            pass

    def connection_kind(self):
        if self.kind == "com_lan":
            return "socket" if self.connection_var.get() == "LAN" else "com"
        return "visa" if self.kind == "lan" else "com"

    def _show_connection_settings(self):
        transport = self.connection_kind()
        self._shown_transport = transport
        self.com_frame.grid_remove()
        self.lan_frame.grid_remove()
        if transport == "com":
            self.com_frame.grid(row=1, column=0, columnspan=5, sticky="ew")
        else:
            self.lan_frame.grid(row=1, column=0, columnspan=5, sticky="ew")

    def _on_connection_changed(self, event=None):
        if self.locked or self.inst is not None or (self.worker and self.worker.is_alive()):
            self.connection_var.set("COM" if self._shown_transport == "com" else "LAN")
            return
        self._show_connection_settings()
        if self.connection_kind() == "com":
            self.refresh_ports()

    def load_settings(self):
        try:
            from .user_config import load_config
            cfg = load_config()
            if self.kind in ("com", "com_lan"):
                if cfg.get(f"{self.title}_port"):
                    self.port_var.set(cfg[f"{self.title}_port"])
                if cfg.get(f"{self.title}_baud"):
                    self.baud_var.set(cfg[f"{self.title}_baud"])
            if self.kind in ("lan", "com_lan"):
                if cfg.get(f"{self.title}_ip"):
                    self.ip_var.set(cfg[f"{self.title}_ip"])
                if cfg.get(f"{self.title}_lan_port"):
                    self.lanport_var.set(cfg[f"{self.title}_lan_port"])
            connection = cfg.get(f"{self.title}_connection")
            if self.kind == "com_lan" and connection in ("COM", "LAN"):
                self.connection_var.set(connection)
        except Exception:
            pass

    def update_config(self, cfg):
        if self.kind in ("com", "com_lan"):
            cfg[f"{self.title}_port"] = self.port_var.get()
            cfg[f"{self.title}_baud"] = self.baud_var.get()
        if self.kind in ("lan", "com_lan"):
            cfg[f"{self.title}_ip"] = self.ip_var.get()
            cfg[f"{self.title}_lan_port"] = self.lanport_var.get()
        if self.kind == "com_lan":
            cfg[f"{self.title}_connection"] = self.connection_var.get()

    def save_settings(self):
        try:
            from .user_config import load_config, save_config
            cfg = load_config()
            self.update_config(cfg)
            save_config(cfg)
        except Exception:
            pass

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
        transport = self.connection_kind()
        self.connect_btn.state(["disabled"])
        if self.connection_cb is not None:
            self.connection_cb.state(["disabled"])
        self.set_status("● Подключение...", "orange")
        self.answer_var.set("")
        try:
            if transport == "com":
                self.refresh_ports()
                settings = (self.port_var.get().strip(),
                            int(self.baud_var.get().strip() or "9600"))
            else:
                settings = (self.ip_var.get().strip(),
                            int(self.lanport_var.get().strip() or "5025"))
        except ValueError as e:
            self._on_error(str(e))
            return
        self.worker = threading.Thread(
            target=self._connect_worker, args=(transport, settings))
        self.worker.start()

    def _connect_worker(self, transport, settings):
        inst = rm = None
        try:
            if transport == "com":
                port, baud = settings
                if not port:
                    raise ValueError("Не выбран COM-порт")
                inst, idn = open_serial(serial, port, baud)
            elif transport == "socket":
                ip, port = settings
                if not ip:
                    raise ValueError("Не введён IP-адрес")
                rm, inst, idn = open_socket(socket, ip, port)
            else:
                ip, port = settings
                if not ip:
                    raise ValueError("Не введён IP-адрес")
                rm, inst, idn = open_visa(pyvisa, ip, port)
            self.inst, self.rm = inst, rm
            shown_idn = (idn or "(пустой ответ)") if transport in ("com", "socket") else idn
            self.dispatch(lambda: self._on_connected(shown_idn))
        except Exception as e:
            close_resources(inst, rm)
            err = str(e)
            self.dispatch(lambda: self._on_error(err))

    def _on_connected(self, idn):
        self.set_status("● Подключён", "green")
        self.save_settings()
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
        if self.connection_cb is not None:
            self.connection_cb.state(["!disabled"])
        self.connect_btn.configure(text="Подключить")
        self.on_log(f"{self.title}: ошибка подключения — {err}")

    def disconnect(self):
        if self.locked or (self.worker and self.worker.is_alive()):
            return
        close_resources(self.inst, self.rm)
        self.inst = self.rm = None
        self.set_status("● Откл.", "gray")
        self.answer_var.set("")
        if self.connection_cb is not None:
            self.connection_cb.state(["!disabled"])
        self.connect_btn.configure(text="Подключить")
        self.on_log(f"{self.title}: отключён")

    def set_status(self, text, color):
        self.status_var.set(text)
        self.status_lbl.configure(foreground=color)

    def is_connected(self):
        return self.inst is not None
