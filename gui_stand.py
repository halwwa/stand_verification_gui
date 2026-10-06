## -*- coding: utf-8 -*-
"""
Стенд автоматизированной поверки радиоприборов.
Версия 2.0 — единый движок MeasurementEngine.
"""

import os
import time
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox

import serial
import serial.tools.list_ports
import pyvisa

from measurement_engine import (
    MeasurementEngine,
    TEST_FREQ, TEST_LEVEL,
    TEST_AM_NOISE, TEST_FM_NOISE, TEST_PM_NOISE,
)


# ============================================================
#                    НАЗВАНИЯ ТЕСТОВ (для GUI)
# ============================================================

# Названия, которые показывает GUI в списке тестов
TEST_NAMES = [
    ("Тест 1: Погрешность измерения частоты входного сигнала", TEST_FREQ),
    ("Тест 2: Погрешность измерения уровня",                    TEST_LEVEL),
    ("Тест 3: К-гармоник (С6-22)",                              None),   # не реализован
    ("Тест 4: СВЧ тракт (SMB100A)",                             None),   # не реализован
    ("Тест 5: Нестабильность частоты",                          TEST_FM_NOISE),  # заглушка
    ("Тест 6: Паразитная девиация",                             TEST_PM_NOISE),  # заглушка
]

# Маппинг: имя теста в GUI → идентификатор в движке
TEST_NAME_TO_ID = {name: tid for name, tid in TEST_NAMES}


# ============================================================
#                    КАРТОЧКА ОДНОГО ПРИБОРА
# ============================================================

class DeviceCard:
    def __init__(self, parent, title, kind, defaults, on_log, on_parsed=None):
        self.title = title
        self.kind = kind
        self.on_log = on_log
        self.on_parsed = on_parsed

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
            ttk.Entry(self.settings, textvariable=self.ip_var, width=16)\
                .grid(row=0, column=1, padx=(4, 12))

            ttk.Label(self.settings, text="Порт:").grid(row=0, column=2, sticky="w")
            self.lanport_var = tk.StringVar(value=str(defaults.get("lan_port", 5025)))
            ttk.Entry(self.settings, textvariable=self.lanport_var, width=8)\
                .grid(row=0, column=3, padx=(4, 12))

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
        ttk.Label(self.frame, textvariable=self.answer_var,
                  foreground="#333", wraplength=500, justify="left")\
            .pack(fill="x", pady=(6, 0))

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
        if len(parts) >= 1:
            result["manufacturer"] = parts[0]
        if len(parts) >= 2:
            result["model"] = parts[1]
        if len(parts) >= 3:
            result["serial"] = parts[2]
        if len(parts) >= 4:
            result["version"] = parts[3]
        return result

    def on_connect_click(self):
        if self.inst is not None:
            self.disconnect()
            return

        self.connect_btn.state(["disabled"])
        self.set_status("● Подключение...", "orange")
        self.answer_var.set("")

        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self):
        try:
            if self.kind == "com":
                port = self.port_var.get().strip()
                baud = int(self.baud_var.get().strip() or "9600")
                if not port:
                    raise ValueError("Не выбран COM-порт")

                inst = serial.Serial(port=port, baudrate=baud, timeout=2)
                inst.write(b"*IDN?\n")
                inst.flush()
                time.sleep(0.3)
                raw = inst.readline()
                idn = raw.decode("utf-8", errors="ignore").strip()
                if not idn:
                    time.sleep(0.3)
                    raw = inst.readline()
                    idn = raw.decode("utf-8", errors="ignore").strip()

                self.inst = inst
                self.rm = None
                self.frame.after(0, lambda: self._on_connected(idn or "(пустой ответ)"))

            else:
                ip = self.ip_var.get().strip()
                port = int(self.lanport_var.get().strip() or "5025")
                if not ip:
                    raise ValueError("Не введён IP-адрес")

                rm = pyvisa.ResourceManager('@py')
                res = f"TCPIP::{ip}::{port}::SOCKET"
                inst = rm.open_resource(res, timeout=5000)
                inst.read_termination = "\n"
                inst.write_termination = "\n"
                idn = inst.query("*IDN?").strip()

                self.rm = rm
                self.inst = inst
                self.frame.after(0, lambda: self._on_connected(idn))

        except Exception as e:
            err = str(e)
            self.frame.after(0, lambda: self._on_error(err))

    def _on_connected(self, idn):
        self.set_status("● Подключён", "green")
        self.answer_var.set(idn)
        self.connect_btn.state(["!disabled"])
        self.connect_btn.configure(text="Отключить")
        self.on_log(f"{self.title}: подключён ({idn})")

        if self.on_parsed is not None:
            try:
                parsed = self._parse_idn(idn)
                self.on_parsed(parsed)
            except Exception as e:
                self.on_log(f"{self.title}: ошибка разбора *IDN? — {e}")

    def _on_error(self, err):
        self.set_status("● Ошибка", "red")
        self.answer_var.set(f"❌ {err}")
        self.connect_btn.state(["!disabled"])
        self.connect_btn.configure(text="Подключить")
        self.on_log(f"{self.title}: ошибка подключения — {err}")

    def disconnect(self):
        try:
            if self.inst is not None:
                self.inst.close()
        except Exception:
            pass
        try:
            if self.rm is not None:
                self.rm.close()
        except Exception:
            pass

        self.inst = None
        self.rm = None
        self.set_status("● Откл.", "gray")
        self.answer_var.set("")
        self.connect_btn.configure(text="Подключить")
        self.on_log(f"{self.title}: отключён")

    def set_status(self, text, color):
        self.status_var.set(text)
        self.status_lbl.configure(foreground=color)

    def is_connected(self):
        return self.inst is not None


# ============================================================
#                    ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================

class StandApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Стенд автоматизированной поверки радиоприборов")
        self.root.geometry("1150x900")
        self.root.minsize(1000, 750)

        self.stop_flag = False
        self.tests_running = False
        self.device_info_user_edited = False

        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")

        cards_container = ttk.Frame(top)
        cards_container.pack(fill="x")

        card_defs = [
            ("СК3-50", "com", {"port": "", "baud": 115200}, "auto_fill"),
            ("С6-22", "com", {"port": "", "baud": 9600}, None),
            ("SMB100A (R&S)", "lan", {"ip": "192.168.0.113", "lan_port": 5025}, None),
        ]

        self.cards = []
        for i, (title, kind, defaults, behavior) in enumerate(card_defs):
            on_parsed = self.on_device_parsed if behavior == "auto_fill" else None
            card = DeviceCard(cards_container, title, kind, defaults,
                              self.log, on_parsed=on_parsed)
            card.frame.grid(row=0, column=i, sticky="nsew", padx=6)
            cards_container.columnconfigure(i, weight=1)
            self.cards.append(card)

        ttk.Button(top, text="🔌  ИНИЦИАЛИЗИРОВАТЬ ВЕСЬ ИЗМЕРИТЕЛЬНЫЙ КОМПЛЕКС",
                   command=self.on_init_all)\
            .pack(pady=(10, 0), ipadx=10, ipady=4)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_graphs = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text="Главная панель")
        self.notebook.add(self.tab_graphs, text="Графики и Таблицы")

        self._build_main_tab()
        self._build_graphs_tab()

        self.sys_status_var = tk.StringVar(value="Система готова к работе.")
        ttk.Label(root, textvariable=self.sys_status_var,
                  relief="sunken", anchor="w", padding=4)\
            .pack(fill="x", side="bottom")

        self.log("Приложение запущено.")
        self.log("Подключите СК3-50 — данные тестируемого прибора подтянутся автоматически.")

    # ===================================================
    #                ГЛАВНАЯ ВКЛАДКА
    # ===================================================

    def _build_main_tab(self):
        info = ttk.LabelFrame(self.tab_main, text="Тестируемый прибор", padding=8)
        info.pack(fill="x", padx=4, pady=(4, 8))

        ttk.Label(info, text="Название:").grid(row=0, column=0, sticky="w")
        self.dev_name_var = tk.StringVar(value="")
        self.dev_name_entry = ttk.Entry(info, textvariable=self.dev_name_var, width=28)
        self.dev_name_entry.grid(row=0, column=1, sticky="w", padx=(4, 16))
        self.dev_name_entry.bind("<KeyRelease>", self._mark_user_edited)

        ttk.Label(info, text="Заводской №:").grid(row=0, column=2, sticky="w")
        self.dev_sn_var = tk.StringVar(value="")
        self.dev_sn_entry = ttk.Entry(info, textvariable=self.dev_sn_var, width=18)
        self.dev_sn_entry.grid(row=0, column=3, sticky="w", padx=(4, 16))
        self.dev_sn_entry.bind("<KeyRelease>", self._mark_user_edited)

        ttk.Label(info, text="Имя файла отчёта:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.report_name_var = tk.StringVar(value="")
        ttk.Entry(info, textvariable=self.report_name_var, width=52)\
            .grid(row=1, column=1, columnspan=3, sticky="we", padx=(4, 0), pady=(6, 0))

        ttk.Label(info, text="Путь сохранения:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.report_path_var = tk.StringVar(value="C:/Reports/Calibration/2026/")
        ttk.Entry(info, textvariable=self.report_path_var, width=42)\
            .grid(row=2, column=1, sticky="we", padx=(4, 6), pady=(6, 0))
        ttk.Button(info, text="Обзор…", command=self.on_browse_path)\
            .grid(row=2, column=2, sticky="w", padx=(0, 6), pady=(6, 0))
        ttk.Button(info, text="↻ Имя файла", command=self.update_report_name)\
            .grid(row=2, column=3, sticky="w", pady=(6, 0))

        info.columnconfigure(1, weight=1)
        info.columnconfigure(3, weight=1)

        tests = ttk.LabelFrame(self.tab_main, text="Список поверочных тестов", padding=8)
        tests.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        columns = ("check", "name", "status")
        self.tests_tree = ttk.Treeview(tests, columns=columns, show="headings",
                                       height=6, selectmode="none")
        self.tests_tree.heading("check", text="✓")
        self.tests_tree.heading("name", text="Тест")
        self.tests_tree.heading("status", text="Статус")

        self.tests_tree.column("check", width=40, anchor="center", stretch=False)
        self.tests_tree.column("name", width=520, anchor="w", stretch=True)
        self.tests_tree.column("status", width=180, anchor="center", stretch=False)

        self.tests_tree.tag_configure("done", foreground="#1b8a1b")
        self.tests_tree.tag_configure("running", foreground="#1e5fbf")
        self.tests_tree.tag_configure("warn", foreground="#c79100")
        self.tests_tree.tag_configure("error", foreground="#c01e1e")
        self.tests_tree.tag_configure("idle", foreground="#666666")

        vsb = ttk.Scrollbar(tests, orient="vertical", command=self.tests_tree.yview)
        self.tests_tree.configure(yscrollcommand=vsb.set)

        self.tests_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        right = ttk.Frame(tests)
        right.pack(side="left", fill="y", padx=(8, 0))

        ttk.Button(right, text="▶ Запустить выбранный",
                   command=self.on_run_selected).pack(fill="x", pady=2)
        ttk.Button(right, text="☑ Выделить все",
                   command=self.on_select_all_tests).pack(fill="x", pady=2)
        ttk.Button(right, text="☐ Снять выделение",
                   command=self.on_deselect_all_tests).pack(fill="x", pady=2)

        # Заполняем список тестов
        self.test_items = []
        for name, test_id in TEST_NAMES:
            item_id = self.tests_tree.insert("", "end",
                                             values=("☑", name, "—"),
                                             tags=("idle",))
            self.test_items.append({
                "id": item_id,
                "name": name,
                "test_id": test_id,   # идентификатор для движка (или None)
                "checked": True,
                "status": "idle",
            })

        self.tests_tree.bind("<Button-1>", self._on_tree_click)

        progress_row = ttk.Frame(self.tab_main)
        progress_row.pack(fill="x", padx=4, pady=(0, 8))

        ttk.Label(progress_row, text="Текущий прогресс:").pack(side="left")
        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(progress_row, variable=self.progress_var,
                        maximum=100, length=300).pack(side="left", padx=8)
        self.progress_lbl_var = tk.StringVar(value="0 из 0")
        ttk.Label(progress_row, textvariable=self.progress_lbl_var).pack(side="left")

        log_frame = ttk.LabelFrame(self.tab_main, text="Журнал измерений (лог)", padding=6)
        log_frame.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, state="disabled",
                                                  font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        globals_row = ttk.Frame(self.tab_main)
        globals_row.pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        self.start_btn = ttk.Button(globals_row,
                                    text="▶  СТАРТ ВСЕХ ВЫБРАННЫХ ТЕСТОВ",
                                    command=self.on_start_all)
        self.start_btn.pack(side="left", ipadx=10, ipady=4)

        self.stop_btn = tk.Button(globals_row, text="■  АВАРИЙНЫЙ СТОП",
                                  bg="#c01e1e", fg="white",
                                  activebackground="#a01818", activeforeground="white",
                                  disabledforeground="#999999",
                                  font=("Segoe UI", 10, "bold"),
                                  command=self.on_emergency_stop,
                                  state="disabled")
        self.stop_btn.pack(side="left", padx=12, ipadx=10, ipady=4)

        self.reset_btn = ttk.Button(globals_row, text="↻  СБРОСИТЬ СТАТУСЫ ТЕСТОВ",
                                    command=self.on_reset_tests)
        self.reset_btn.pack(side="left", padx=8, ipadx=10, ipady=4)

    def _build_graphs_tab(self):
        ttk.Label(self.tab_graphs,
                  text="Здесь будут таблица теста частоты и график теста уровня.\n"
                       "(появятся после реализации — в следующей версии)",
                  font=("Segoe UI", 11, "italic"),
                  foreground="#666",
                  justify="center")\
            .pack(expand=True)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _mark_user_edited(self, event=None):
        self.device_info_user_edited = True

    def on_device_parsed(self, parsed):
        if self.device_info_user_edited:
            self.log("Данные прибора получены, но поля уже правлены вручную — пропускаем.")
            return

        model = parsed.get("model") or parsed.get("manufacturer") or "Unknown"
        serial = parsed.get("serial") or "unknown"

        self.dev_name_var.set(model)
        self.dev_sn_var.set(serial)
        self.update_report_name()

        self.log(f"Автозаполнение: название = «{model}», зав. № = «{serial}»")

    def on_browse_path(self):
        path = filedialog.askdirectory(initialdir=self.report_path_var.get() or "C:/")
        if path:
            self.report_path_var.set(path.replace("\\", "/") + "/")

    def update_report_name(self):
        name = self.dev_name_var.get().strip() or "Device"
        sn = self.dev_sn_var.get().strip() or "unknown"
        ts = datetime.now().strftime("%d%m%Y_%H%M")
        raw = f"{name}_{sn}_{ts}.xlsx"
        safe = "".join(c for c in raw if c.isalnum() or c in ("_", "-", "."))
        self.report_name_var.set(safe)

    def on_init_all(self):
        self.log("Инициализация всего измерительного комплекса…")
        self.sys_status_var.set("Инициализация…")

        def worker():
            for card in self.cards:
                if not card.is_connected():
                    card.on_connect_click()
                    for _ in range(60):
                        if card.is_connected() or "Ошибка" in card.status_var.get():
                            break
                        time.sleep(0.1)

            ok = sum(1 for c in self.cards if c.is_connected())
            total = len(self.cards)
            self.root.after(0, lambda: self.sys_status_var.set(
                f"Комплекс инициализирован: {ok} из {total} приборов подключены."))
            self.root.after(0, lambda: self.log(
                f"Инициализация завершена: {ok}/{total} подключены."))

        threading.Thread(target=worker, daemon=True).start()

    def _on_tree_click(self, event):
        region = self.tests_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tests_tree.identify_column(event.x)
        if col != "#1":
            return
        item_id = self.tests_tree.identify_row(event.y)
        if not item_id:
            return
        for t in self.test_items:
            if t["id"] == item_id:
                t["checked"] = not t["checked"]
                values = self.tests_tree.item(item_id, "values")
                check = "☑" if t["checked"] else "☐"
                self.tests_tree.item(item_id, values=(check, values[1], values[2]))
                break

    def on_select_all_tests(self):
        for t in self.test_items:
            t["checked"] = True
            values = self.tests_tree.item(t["id"], "values")
            self.tests_tree.item(t["id"], values=("☑", values[1], values[2]))

    def on_deselect_all_tests(self):
        for t in self.test_items:
            t["checked"] = False
            values = self.tests_tree.item(t["id"], "values")
            self.tests_tree.item(t["id"], values=("☐", values[1], values[2]))

    # ===================================================
    #        ЗАПУСК ТЕСТОВ
    # ===================================================

    def on_run_selected(self):
        """Запуск ТОЛЬКО выделенных тестов."""
        sel = [t for t in self.test_items if t["checked"]]
        if not sel:
            messagebox.showinfo("Нет тестов", "Не выбран ни один тест.")
            return
        self._start_engine(sel)

    def on_start_all(self):
        """Запуск всех выделенных тестов."""
        sel = [t for t in self.test_items if t["checked"]]
        if not sel:
            messagebox.showinfo("Нет тестов", "Не выбран ни один тест.")
            return
        if not self.report_name_var.get().strip():
            self.update_report_name()
        self._start_engine(sel)

    def _start_engine(self, selected_items):
        """Общая точка запуска движка — и для кнопки «выбранный», и для «всех»."""
        if self.tests_running:
            messagebox.showinfo("Подождите", "Тесты уже выполняются.")
            return

        # Собираем список активных тестов из чек-боксов
        active_ids = []
        not_impl_names = []
        for t in selected_items:
            if t["test_id"] is not None:
                active_ids.append(t["test_id"])
            else:
                not_impl_names.append(t["name"])

        if not active_ids:
            messagebox.showinfo("Нет реализованных тестов",
                                "Все выбранные тесты пока в разработке.\n"
                                "Доступны: «Тест 1: Погрешность измерения частоты входного сигнала»\n"
                                "и «Тест 2: Погрешность измерения уровня».")
            return

        # Проверка подключений
        card_sk3 = self.cards[0]
        card_gen = self.cards[2]
        if not card_sk3.is_connected():
            messagebox.showerror("Не подключён СК3-50",
                                 "Сначала подключите СК3-50 (первая карточка).")
            return
        if not card_gen.is_connected():
            messagebox.showerror("Не подключён SMB100A",
                                 "Сначала подключите SMB100A (третья карточка).")
            return

        # Автосброс статусов, если все уже done
        if all(t["status"] == "done" for t in selected_items):
            self._reset_statuses_silent()

        # Блокируем кнопки
        self.tests_running = True
        self.stop_flag = False
        self.start_btn.state(["disabled"])
        self.reset_btn.state(["disabled"])
        self.stop_btn.configure(state="normal")

        # Помечаем выбранные тесты «выполняется»
        for t in selected_items:
            self._set_test_status(t, "running", "● Ожидание…")

        self.sys_status_var.set("Запуск движка измерений…")
        self.progress_var.set(0)
        self.progress_lbl_var.set("0 из ?")

        threading.Thread(
            target=self._engine_worker,
            args=(card_sk3.inst, card_gen.inst, active_ids,
                  selected_items, not_impl_names),
            daemon=True
        ).start()

    # ===================================================
    #        ФОНОВЫЙ ПОТОК ДВИЖКА
    # ===================================================

    def _engine_worker(self, sk3_inst, gen_inst, active_ids,
                       selected_items, not_impl_names):
        try:
            # Уведомление о нереализованных
            for nm in not_impl_names:
                self.root.after(0, lambda nm=nm: self.log(
                    f"⚠ «{nm}» — в разработке, пропускается."))

            engine = MeasurementEngine(
                gen=gen_inst, sk3=sk3_inst,
                active_tests=active_ids,
                log_callback=lambda msg: self.root.after(0, lambda: self.log(msg)),
            )

            def progress_cb(idx, total, info_str):
                pct = idx / total * 100
                self.root.after(0, lambda: self.progress_var.set(pct))
                self.root.after(0, lambda: self.progress_lbl_var.set(f"{idx} из {total}"))
                self.root.after(0, lambda: self.sys_status_var.set(
                    f"{info_str} ({idx}/{total})"))
                if self.stop_flag:
                    raise InterruptedError("Остановлено оператором")

            results, final_status = engine.run(progress_callback=progress_cb)

            # Сохраняем Excel
            saved_path = self._save_report_to_excel(engine)

                      # Точная покраска КАЖДОГО теста — по его собственным результатам
            self._paint_tests_by_results(engine, selected_items)

            # Сводка
            s = engine.summary()
            self.root.after(0, lambda: self.log(
                f"Движок завершён. Итог: {final_status}."))
            self.root.after(0, lambda: self.log(f"Сводка: {s}"))
            if saved_path:
                self.root.after(0, lambda: self.log(f"Отчёт сохранён: {saved_path}"))
            self.root.after(0, lambda: self.sys_status_var.set(f"Готово. Статус: {final_status}"))

        except InterruptedError:
            for t in selected_items:
                if t["test_id"] is not None:
                    self.root.after(0, lambda t=t: self._set_test_status(
                        t, "warn", "⚠ Остановлен"))
            self.root.after(0, lambda: self.log("⚠ Выполнение прервано оператором."))
            self.root.after(0, lambda: self.sys_status_var.set("Остановлено оператором."))

        except Exception as e:
            err_text = str(e)
            for t in selected_items:
                if t["test_id"] is not None:
                    self.root.after(0, lambda t=t, err=err_text: self._set_test_status(
                        t, "error", f"✖ {err[:30]}"))
            self.root.after(0, lambda err=err_text: self.log(f"❌ Ошибка движка: {err}"))
            self.root.after(0, lambda: self.sys_status_var.set("Ошибка выполнения."))

        finally:
            self.root.after(0, self._finish_run)
            
    def _paint_tests_by_results(self, engine, selected_items):
        """
        Красит статус каждого теста ПО ЕГО РЕЗУЛЬТАТАМ.
        Для каждого активного теста смотрим его строки в engine.results,
        определяем итоговый статус (ok/warn/fail) и применяем цвет.
        """
        from measurement_engine import TEST_FREQ, TEST_LEVEL

        def evaluate_test(rows):
            """
            rows — список строк результатов теста.
            Возвращает (tag, label) — статус для GUI.
            """
            if not rows:
                return "idle", "—"
            codes = [r[5] for r in rows]   # 6-й элемент — status_code
            if 'fail' in codes:
                return "error", "✖ Провален"
            if 'warn' in codes:
                return "warn", "⚠ Внимание"
            return "done", "✔ Пройден"

        for t in selected_items:
            tid = t["test_id"]
            if tid is None:
                continue   # нереализованный тест — не трогаем

            rows = engine.results.get(tid, [])
            tag, label = evaluate_test(rows)
            self.root.after(0, lambda t=t, tag=tag, label=label:
                            self._set_test_status(t, tag, label))

    # ===================================================
    #        СОХРАНЕНИЕ В EXCEL
    # ===================================================

    def _save_report_to_excel(self, engine):
        fname = self.report_name_var.get().strip()
        if not fname:
            self.update_report_name()
            fname = self.report_name_var.get().strip()
        if not fname:
            fname = "report.xlsx"

        folder = self.report_path_var.get().strip() or "./"
        folder = folder.replace("\\", "/")

        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            err_text = str(e)
            self.root.after(0, lambda err=err_text: self.log(
                f"⚠ Не удалось создать папку {folder}: {err}. Сохраняю рядом со скриптом."))
            folder = "."

        full_path = os.path.join(folder, fname)

        try:
            engine.save_to_excel(full_path)
            return full_path
        except Exception as e:
            fallback = os.path.join(".", fname)
            try:
                engine.save_to_excel(fallback)
                self.root.after(0, lambda: self.log(
                    f"⚠ Сохранено по резервному пути: {fallback}"))
                return fallback
            except Exception as e2:
                err_text = str(e2)
                self.root.after(0, lambda err=err_text: self.log(
                    f"❌ Не удалось сохранить отчёт: {err}"))
                return None

    # ===================================================
    #        ВСПОМОГАТЕЛЬНЫЕ
    # ===================================================

    def on_emergency_stop(self):
        if not self.tests_running:
            return
        self.stop_flag = True
        self.log("⚠ АВАРИЙНЫЙ СТОП: остановка тестов по запросу оператора.")
        self.sys_status_var.set("Остановка…")

    def on_reset_tests(self):
        if self.tests_running:
            messagebox.showinfo("Подождите", "Нельзя сбросить, пока идут тесты.")
            return
        self._reset_statuses_silent()
        self.log("Статусы тестов сброшены.")

    def _reset_statuses_silent(self):
        for t in self.test_items:
            self._set_test_status(t, "idle", "—")
        self.progress_var.set(0)
        self.progress_lbl_var.set(f"0 из {len(self.test_items)}")
        self.sys_status_var.set("Система готова к работе.")

    def _finish_run(self):
        self.tests_running = False
        self.start_btn.state(["!disabled"])
        self.reset_btn.state(["!disabled"])
        self.stop_btn.configure(state="disabled")

    def _set_test_status(self, test, tag, label):
        self.tests_tree.item(test["id"], tags=(tag,))
        values = self.tests_tree.item(test["id"], "values")
        self.tests_tree.item(test["id"], values=(values[0], values[1], label))
        test["status"] = tag


# ============================================================
#                    ТОЧКА ВХОДА
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = StandApp(root)

    def on_close():
        for card in app.cards:
            card.disconnect()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()