# -*- coding: utf-8 -*-
"""
Стенд автоматизированной поверки радиоприборов.
Версия 2.3 — добавлен тест 6 (Переход АМ↔ЧМ).
"""

import os
import threading
import queue
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox

from stand_verification.measurement.engine import (
    MeasurementEngine,
    TEST_FREQ, TEST_LEVEL,
    TEST_AM_NOISE, TEST_FM_NOISE, TEST_PM_NOISE,
    TEST_AM_FM_TRANSITION,
)
from stand_verification.ui.device_card import DeviceCard
from stand_verification.config import DEVICE_DEFAULTS, REPORT_PATH_DEFAULT
from stand_verification.reports.excel import export_excel


# ============================================================
#                    НАЗВАНИЯ ТЕСТОВ (для GUI)
# ============================================================

TEST_NAMES = [
    ("Тест 1: Погрешность измерения частоты входного сигнала", TEST_FREQ),
    ("Тест 2: Погрешность измерения уровня",                    TEST_LEVEL),
    ("Тест 3: АМ шум",                                          TEST_AM_NOISE),
    ("Тест 4: ЧМ шум",                                          TEST_FM_NOISE),
    ("Тест 5: ФМ шум",                                          TEST_PM_NOISE),
    ("Тест 6: Переход АМ-ЧМ, ЧМ-АМ",                            TEST_AM_FM_TRANSITION),
]


class StandApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Стенд автоматизированной поверки радиоприборов")
        self.root.geometry("1150x900")
        self.root.minsize(1000, 750)

        self.stop_event = threading.Event()
        self.engine_thread = None
        self.retry_thread = None
        self.engine = None
        self.close_requested = False
        self.close_after_retry = False
        self.shutdown_blocked = False
        self.initializing = False
        self.report_result = None
        self.callbacks = queue.Queue()
        self.tests_running = False
        self.device_info_user_edited = False

        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")

        cards_container = ttk.Frame(top)
        cards_container.pack(fill="x")

        self.cards = []
        for i, (title, kind, defaults, behavior) in enumerate(DEVICE_DEFAULTS):
            on_parsed = self.on_device_parsed if behavior == "auto_fill" else None
            card = DeviceCard(cards_container, title, kind, defaults,
                              self.log, on_parsed=on_parsed,
                              dispatch=self.callbacks.put)
            card.frame.grid(row=0, column=i, sticky="nsew", padx=6)
            cards_container.columnconfigure(i, weight=1)
            self.cards.append(card)

        self.init_btn = ttk.Button(
            top, text="🔌  ИНИЦИАЛИЗИРОВАТЬ ВЕСЬ ИЗМЕРИТЕЛЬНЫЙ КОМПЛЕКС",
            command=self.on_init_all)
        self.init_btn.pack(pady=(10, 0), ipadx=10, ipady=4)

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
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.root.after(50, self._drain_callbacks)

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
        self.report_path_var = tk.StringVar(value=REPORT_PATH_DEFAULT)
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
                                       height=7, selectmode="none")
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

        self.test_items = []
        for name, test_id in TEST_NAMES:
            item_id = self.tests_tree.insert("", "end",
                                             values=("☑", name, "—"),
                                             tags=("idle",))
            self.test_items.append({
                "id": item_id,
                "name": name,
                "test_id": test_id,
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

        self.stop_btn = tk.Button(globals_row, text="■  СТОП",
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
        self.retry_btn = ttk.Button(globals_row, text="Повторить OUTP OFF",
                                    command=self.on_retry_shutdown, state='disabled')
        self.retry_btn.pack(side='left', padx=8)

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
        if self._controls_busy() or self.initializing:
            return
        self.initializing = True
        self.log("Инициализация всего измерительного комплекса…")
        self.sys_status_var.set("Инициализация…")
        for card in self.cards:
            if not card.is_connected():
                card.on_connect_click()
        self._set_controls_locked(True)
        self.root.after(100, self._poll_initialization)

    def _poll_initialization(self):
        if self._connections_active():
            self.root.after(100, self._poll_initialization)
            return
        self.initializing = False
        self._set_controls_locked(self._controls_busy())
        if not self.close_requested:
            ok = sum(c.is_connected() for c in self.cards)
            self.sys_status_var.set(f"Комплекс инициализирован: {ok}/{len(self.cards)}.")

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

    def on_run_selected(self):
        sel = [t for t in self.test_items if t["checked"]]
        if not sel:
            messagebox.showinfo("Нет тестов", "Не выбран ни один тест.")
            return
        self._start_engine(sel)

    def on_start_all(self):
        sel = [t for t in self.test_items if t["checked"]]
        if not sel:
            messagebox.showinfo("Нет тестов", "Не выбран ни один тест.")
            return
        if not self.report_name_var.get().strip():
            self.update_report_name()
        self._start_engine(sel)

    def _start_engine(self, selected_items):
        if self._controls_busy() or self.initializing or self._connections_active():
            messagebox.showinfo("Подождите", "Тесты уже выполняются.")
            return

        active_ids = []
        not_impl_names = []
        for t in selected_items:
            if t["test_id"] is not None:
                active_ids.append(t["test_id"])
            else:
                not_impl_names.append(t["name"])

        if not active_ids:
            messagebox.showinfo("Нет реализованных тестов",
                                "Все выбранные тесты пока в разработке.")
            return

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

        if all(t["status"] == "done" for t in selected_items):
            self._reset_statuses_silent()

        self.tests_running = True
        self.stop_event = threading.Event()
        self.report_result = None
        if not self.report_name_var.get().strip():
            self.update_report_name()
        report_target = (self.report_path_var.get().strip() or './',
                         self.report_name_var.get().strip() or 'report.xlsx')
        self.report_target = report_target
        self._set_controls_locked(True)
        self.start_btn.state(["disabled"])
        self.reset_btn.state(["disabled"])
        self.stop_btn.configure(state="normal")

        for t in selected_items:
            self._set_test_status(t, "running", "● Ожидание…")

        self.sys_status_var.set("Запуск движка измерений…")
        self.progress_var.set(0)
        self.progress_lbl_var.set("0 из ?")

        self.engine_thread = threading.Thread(
            target=self._engine_worker,
            args=(card_sk3.inst, card_gen.inst, active_ids,
                  selected_items, not_impl_names, report_target),
        )
        self.engine_thread.start()

    def _confirm_fail_sync(self, freq_mhz, level_dbm, error_value,
                           tolerance_value, stage):
        if self.close_requested or self.stop_event.is_set():
            return True
        result_holder = {'decision': True}
        done_event = threading.Event()

        def show_dialog():
            try:
                if stage == 'freq':
                    title = 'Провал допуска — частота'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"Погрешность: {error_value:+.2f} Гц\n"
                            f"Допуск: ±{tolerance_value:.2f} Гц")
                elif stage == 'level':
                    title = 'Провал допуска — уровень'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"Уровень: {level_dbm:+.0f} dBm\n"
                            f"Погрешность: {error_value:+.2f} дБ\n"
                            f"Допуск: ±{tolerance_value:.2f} дБ")
                elif stage == 'am_noise':
                    title = 'Провал допуска — АМ шум'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"СКЗ шум: {error_value:.3f} %\n"
                            f"Допуск: ±{tolerance_value:.3f} %")
                elif stage == 'fm_noise':
                    title = 'Провал допуска — ЧМ шум'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"СКЗ шум: {error_value:.1f} Гц\n"
                            f"Допуск: ±{tolerance_value:.1f} Гц")
                elif stage == 'pm_noise':
                    title = 'Провал допуска — ФМ шум'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"СКЗ шум: {error_value:.3f} рад\n"
                            f"Допуск: ±{tolerance_value:.3f} рад")
                elif stage == 'am_fm_transition':
                    title = 'Провал допуска — Переход АМ↔ЧМ'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"Коэффициент: {error_value}\n"
                            f"Допуск: {tolerance_value}")
                else:
                    title = 'Провал допуска'
                    body = (f"Частота: {freq_mhz:g} МГц\n"
                            f"Значение: {error_value}\n"
                            f"Допуск: {tolerance_value}")

                self.log(f"🔴 Провал: {body.replace(chr(10), ' | ')}")

                answer = messagebox.askyesno(
                    title,
                    f"{body}\n\n"
                    f"Продолжить выполнение теста?\n\n"
                    f"«Да» — продолжить (итог теста всё равно будет красным).\n"
                    f"«Нет» — остановить прогон."
                )
                result_holder['decision'] = bool(answer)
                if not answer:
                    self.log("⏹ Оператор выбрал «Остановить» при провале.")
                else:
                    self.log("▶ Оператор выбрал «Продолжить» при провале.")
            except Exception as e:
                self.log(f"⚠ Ошибка в диалоге провала: {e}")
            finally:
                done_event.set()

        self.callbacks.put(show_dialog)
        done_event.wait(timeout=600)
        return result_holder['decision']

    def _engine_worker(self, sk3_inst, gen_inst, active_ids,
                       selected_items, not_impl_names, report_target):
        engine = MeasurementEngine(
            gen=gen_inst, sk3=sk3_inst, active_tests=active_ids,
            stop_event=self.stop_event,
            confirm_callback=self._confirm_fail_sync,
            log_callback=lambda msg: self.callbacks.put(lambda: self.log(msg)),
        )
        self.engine = engine
        try:
            for nm in not_impl_names:
                self.callbacks.put(lambda nm=nm: self.log(
                    f"⚠ «{nm}» — в разработке, пропускается."))

            def progress_cb(idx, total, info_str):
                pct = idx / total * 100
                self.callbacks.put(lambda: self.progress_var.set(pct))
                self.callbacks.put(lambda: self.progress_lbl_var.set(f"{idx} из {total}"))
                self.callbacks.put(lambda: self.sys_status_var.set(
                    "Безопасное завершение…" if self.close_requested else
                    f"{info_str} ({idx}/{total})"))

            results, final_status = engine.run(progress_callback=progress_cb)

        except Exception as e:
            engine.final_status = 'error'
            engine.termination_reason = str(e)
        finally:
            self.report_result = self._save_report_to_excel(engine, report_target)
            self.callbacks.put(lambda: self._on_engine_finished(engine, selected_items))

    def _on_engine_finished(self, engine, selected_items):
        if self.engine_thread.is_alive():
            self.root.after(50, lambda: self._on_engine_finished(engine, selected_items))
            return
        self._paint_tests_by_results(engine, selected_items)
        self.shutdown_blocked = engine.shutdown_success is False
        self._finish_run()
        saved_path, save_error = self.report_result
        self.log(f"Движок завершён. Итог: {engine.final_status}. {engine.termination_reason}")
        if saved_path:
            self.log(f"Отчёт сохранён: {saved_path}")
        else:
            self.log(f"Ошибка сохранения отчёта: {save_error}")
            if not self.close_requested:
                messagebox.showerror('Отчёт не сохранён', save_error)
        if self.shutdown_blocked:
            self._warn_shutdown()
        elif not self.close_requested:
            self.sys_status_var.set(f"Итог: {engine.final_status}" +
                                    ('' if saved_path else '. Отчёт не сохранён.'))

    def _paint_tests_by_results(self, engine, selected_items):
        def evaluate_test(info):
            return {
                'not_started': ('idle', 'Не начат'),
                'incomplete': ('warn', 'Прерван / неполный'),
                'error': ('error', 'Ошибка / провален'),
                'warn': ('warn', 'Внимание'),
                'done': ('done', 'Пройден'),
            }.get(info.get('status'), ('idle', 'Не реализован'))

        summary = engine.summary()
        for t in selected_items:
            tid = t["test_id"]
            if tid is None:
                continue
            tag, label = evaluate_test(summary.get(tid, {}))
            self._set_test_status(t, tag, label)

    def _save_report_to_excel(self, engine, report_target):
        folder, fname = report_target
        folder = folder.replace("\\", "/")
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            err_text = str(e)
            self.callbacks.put(lambda err=err_text, folder=folder: self.log(
                f"⚠ Не удалось создать папку {folder}: {err}. Сохраняю рядом со скриптом."))
            folder = "."
        full_path = os.path.join(folder, fname)
        try:
            if not export_excel(engine.snapshot(), full_path, engine._log):
                raise RuntimeError('Экспорт не подтвердил запись отчёта')
            return full_path, None
        except Exception as e:
            fallback = os.path.join(".", fname)
            try:
                if not export_excel(engine.snapshot(), fallback, engine._log):
                    raise RuntimeError('Экспорт не подтвердил запись отчёта')
                self.callbacks.put(lambda: self.log(
                    f"⚠ Сохранено по резервному пути: {fallback}"))
                return fallback, None
            except Exception as e2:
                err_text = str(e2)
                self.callbacks.put(lambda err=err_text: self.log(
                    f"❌ Не удалось сохранить отчёт: {err}"))
                return None, f'{e}; резервный путь: {e2}'

    def on_emergency_stop(self):
        if not self.tests_running:
            return
        self.stop_event.set()
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
        self._set_controls_locked(self._controls_busy())
        self.stop_btn.configure(state="disabled")

    def _drain_callbacks(self):
        try:
            while True:
                try:
                    callback = self.callbacks.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback()
                except Exception as e:
                    self.root.report_callback_exception(type(e), e, e.__traceback__)
        finally:
            self.root.after(50, self._drain_callbacks)

    def _connections_active(self):
        return any(c.worker and c.worker.is_alive() for c in self.cards)

    def _controls_busy(self):
        return (self.tests_running or self.close_requested or self.shutdown_blocked
                or bool(self.retry_thread and self.retry_thread.is_alive()))

    def _set_controls_locked(self, locked):
        state = ['disabled' if locked else '!disabled']
        self.start_btn.state(state)
        self.reset_btn.state(state)
        self.init_btn.state(state)
        for card in self.cards:
            card.locked = locked
            card.connect_btn.state(['disabled' if locked or
                                    (card.worker and card.worker.is_alive()) else '!disabled'])
        retry_allowed = (self.shutdown_blocked and not self.tests_running and
                         not (self.engine_thread and self.engine_thread.is_alive()) and
                         not (self.retry_thread and self.retry_thread.is_alive()))
        self.retry_btn.state(['!disabled' if retry_allowed else 'disabled'])

    def on_close(self):
        if self.close_requested:
            return
        if self.retry_thread and self.retry_thread.is_alive():
            self.close_after_retry = True
            return
        if self.shutdown_blocked:
            self.close_after_retry = True
            self._warn_shutdown()
            return
        if self.tests_running:
            if not messagebox.askyesno('Остановить измерения?',
                                      'Остановить прогон, выключить выход и сохранить '
                                      'частичный отчёт перед выходом?'):
                return
            self.stop_event.set()
        self.close_requested = True
        self._set_controls_locked(True)
        self.sys_status_var.set('Безопасное завершение. Ожидание текущих операций…')
        self.root.after(50, self._poll_close)

    def _poll_close(self):
        if not self.close_requested:
            return
        if (self.tests_running or self.initializing or self._connections_active() or
                (self.engine_thread and self.engine_thread.is_alive()) or
                (self.retry_thread and self.retry_thread.is_alive()) or
                not self.callbacks.empty()):
            self.root.after(50, self._poll_close)
            return
        if self.shutdown_blocked:
            self._warn_shutdown()
            return
        if self.report_result is not None and not self.report_result[0]:
            if not messagebox.askyesno('Отчёт не сохранён',
                                      f'{self.report_result[1]}\n\nВыйти без отчёта?'):
                self.close_requested = False
                self._set_controls_locked(False)
                self.sys_status_var.set('Отчёт не сохранён. Выход отменён.')
                return
        for card in self.cards:
            card.locked = False
            card.disconnect()
        self.root.destroy()

    def _warn_shutdown(self):
        self.close_after_retry = self.close_after_retry or self.close_requested
        self.close_requested = False
        self._set_controls_locked(True)
        self.sys_status_var.set('Ошибка OUTP OFF: выход может оставаться включённым.')
        messagebox.showwarning(
            'Выход может быть включён',
            f'Не удалось отправить OUTP OFF: {self.engine.shutdown_error}\n'
            'Окно и соединения остаются открытыми. Повторите выключение кнопкой '
            '«Повторить OUTP OFF». Проверьте фактическое состояние выхода на приборе.')

    def on_retry_shutdown(self):
        if (not self.shutdown_blocked or self.tests_running or
                (self.engine_thread and self.engine_thread.is_alive()) or
                (self.retry_thread and self.retry_thread.is_alive())):
            return
        self.sys_status_var.set('Повторная отправка OUTP OFF…')
        def worker():
            success, error = self.engine._deinit_generator()
            self.report_result = self._save_report_to_excel(self.engine, self.report_target)
            self.callbacks.put(lambda: self._on_retry_finished(success, error))
        self.retry_thread = threading.Thread(target=worker)
        self.retry_thread.start()
        self._set_controls_locked(True)

    def _on_retry_finished(self, success, error):
        if self.retry_thread.is_alive():
            self.root.after(50, lambda: self._on_retry_finished(success, error))
            return
        self.shutdown_blocked = not success
        if not success:
            self._warn_shutdown()
            return
        self.log('OUTP OFF отправлена. Фактическое выключение проверьте на приборе.')
        self._set_controls_locked(False)
        self.sys_status_var.set('OUTP OFF отправлена; аппаратное подтверждение не получено.')
        if not self.report_result[0] and not self.close_after_retry:
            messagebox.showerror('Отчёт не сохранён', self.report_result[1])
        if self.close_after_retry:
            self.close_after_retry = False
            self.close_requested = True
            self._set_controls_locked(True)
            self.root.after(50, self._poll_close)

    def _set_test_status(self, test, tag, label):
        self.tests_tree.item(test["id"], tags=(tag,))
        values = self.tests_tree.item(test["id"], "values")
        self.tests_tree.item(test["id"], values=(values[0], values[1], label))
        test["status"] = tag


def main():
    root = tk.Tk()
    StandApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()