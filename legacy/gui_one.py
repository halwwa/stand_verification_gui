import tkinter as tk
from tkinter import ttk
import threading
import pyvisa


class DeviceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Подключение к прибору")
        self.root.geometry("560x260")
        self.root.resizable(False, False)

        # VISA-сессия
        self.inst = None
        self.rm = None

        # ---- Виджеты ----
        main = ttk.Frame(root, padding=16)
        main.pack(fill="both", expand=True)

        # Строка 1: IP + кнопка
        ttk.Label(main, text="IP-адрес:").grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.ip_var = tk.StringVar(value="192.168.0.106")
        self.ip_entry = ttk.Entry(main, textvariable=self.ip_var, width=24)
        self.ip_entry.grid(row=0, column=1, sticky="w")

        self.connect_btn = ttk.Button(main, text="Подключить", command=self.on_connect_click)
        self.connect_btn.grid(row=0, column=2, padx=(10, 0))

        # Строка 2: статус
        ttk.Label(main, text="Статус:").grid(row=1, column=0, sticky="w", pady=(16, 0))

        self.status_var = tk.StringVar(value="не подключён")
        self.status_lbl = ttk.Label(main, textvariable=self.status_var, foreground="gray")
        self.status_lbl.grid(row=1, column=1, columnspan=2, sticky="w", pady=(16, 0))

        # Строка 3: ответ
        ttk.Label(main, text="Ответ прибора:").grid(row=2, column=0, sticky="nw", pady=(16, 0))

        self.answer_var = tk.StringVar(value="")
        self.answer_entry = ttk.Entry(main, textvariable=self.answer_var,
                                      state="readonly", width=48)
        self.answer_entry.grid(row=2, column=1, columnspan=2, sticky="we", pady=(16, 0))

        main.columnconfigure(1, weight=1)

    # ---------- Подключение ----------

    def on_connect_click(self):
        # Если уже подключены — отключаемся
        if self.inst is not None:
            self.disconnect()
            return

        ip = self.ip_var.get().strip()
        if not ip:
            self.set_status("введите IP-адрес", "red")
            return

        # Блокируем кнопку и поле на время подключения
        self.connect_btn.state(["disabled"])
        self.ip_entry.state(["disabled"])
        self.set_status("подключение...", "orange")
        self.answer_var.set("")

        # Подключение — в отдельном потоке
        threading.Thread(target=self._connect_worker, args=(ip,), daemon=True).start()

    def _connect_worker(self, ip):
        try:
            rm = pyvisa.ResourceManager('@py')
            resource_name = f"TCPIP::{ip}::inst0::INSTR"
            inst = rm.open_resource(resource_name, timeout=5000)
            inst.read_termination = '\n'
            inst.write_termination = '\n'

            idn = inst.query("*IDN?").strip()

            self.rm = rm
            self.inst = inst

            # Обновляем GUI из главного потока
            self.root.after(0, lambda: self.on_connected(idn))

        except Exception as e:
            err_text = str(e)
            self.root.after(0, lambda: self.on_error(err_text))

    def on_connected(self, idn):
        self.set_status("подключён", "green")
        self.answer_var.set(idn)
        self.connect_btn.state(["!disabled"])
        self.connect_btn.configure(text="Отключить")
        self.ip_entry.state(["!disabled"])  # можно менять (на случай смены прибора)

    def on_error(self, err_text):
        self.set_status("ошибка", "red")
        self.answer_var.set(f"❌ {err_text}")
        self.connect_btn.state(["!disabled"])
        self.connect_btn.configure(text="Подключить")
        self.ip_entry.state(["!disabled"])

    # ---------- Отключение ----------

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

        self.set_status("не подключён", "gray")
        self.answer_var.set("")
        self.connect_btn.configure(text="Подключить")

    # ---------- Утилита ----------

    def set_status(self, text, color):
        self.status_var.set(text)
        self.status_lbl.configure(foreground=color)


if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceApp(root)

    # Корректно закрываем сессию при закрытии окна
    def on_close():
        app.disconnect()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
