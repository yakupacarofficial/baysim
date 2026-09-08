from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Any
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import (
    RUNTIME_LOG_PATH,
    CheckResult,
    LauncherSettings,
    check_godot,
    check_jsb_forge,
    check_jsbsim,
    check_udp_port,
    launch_godot,
    load_settings,
    save_settings,
    wait_for_telemetry,
    write_runtime_config,
)


BG = "#07101f"
PANEL = "#101b2e"
PANEL_ALT = "#152238"
TEXT = "#e7eef8"
MUTED = "#8fa2ba"
ACCENT = "#29d3b2"
ACCENT_DARK = "#15957f"
SUCCESS = "#42d392"
WARNING = "#f6c85f"
ERROR = "#ff6b7a"


class LauncherApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("BAYSIM Launcher")
        self.root.geometry("1160x820")
        self.root.minsize(1040, 740)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.settings = load_settings()
        self.process: subprocess.Popen[str] | None = None
        self.events: Queue[tuple[str, Any]] = Queue()
        self.status_labels: dict[str, tk.Label] = {}
        self._make_variables()
        self._configure_styles()
        self._build_main_window()
        self._show_splash()
        self.root.after(100, self._poll_events)

    def _make_variables(self) -> None:
        s = self.settings
        self.godot_var = tk.StringVar(value=s.godot_executable)
        self.jsb_forge_var = tk.StringVar(value=s.jsb_forge_path)
        self.jsbsim_python_var = tk.StringVar(value=s.jsbsim_python)
        self.port_var = tk.StringVar(value=str(s.telemetry_port))
        self.position_source_var = tk.StringVar(value=s.position_source)
        self.origin_lat_var = tk.StringVar(value=str(s.origin_lat_deg))
        self.origin_lon_var = tk.StringVar(value=str(s.origin_lon_deg))
        self.origin_alt_var = tk.StringVar(value=str(s.origin_alt_msl_m))
        self.timeout_var = tk.StringVar(value=str(s.connection_timeout_s))
        self.smoothing_var = tk.StringVar(value=str(s.smoothing))
        self.width_var = tk.StringVar(value=str(s.window_width))
        self.height_var = tk.StringVar(value=str(s.window_height))
        self.fullscreen_var = tk.BooleanVar(value=s.fullscreen)
        self.auto_start_var = tk.BooleanVar(value=s.auto_start_renderer)
        self.renderer_status_var = tk.StringVar(value="Renderer kapalı")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Alt.TFrame", background=PANEL_ALT)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 24))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 12))
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#041611",
            borderwidth=0,
            padding=(18, 10),
            font=("Segoe UI Semibold", 10),
        )
        style.map("Accent.TButton", background=[("active", "#5be2c8"), ("disabled", "#315f59")])
        style.configure(
            "Secondary.TButton",
            background=PANEL_ALT,
            foreground=TEXT,
            borderwidth=0,
            padding=(14, 9),
            font=("Segoe UI", 9),
        )
        style.map("Secondary.TButton", background=[("active", "#203554")])
        style.configure("TEntry", fieldbackground="#0a1425", foreground=TEXT, insertcolor=TEXT, padding=7)
        style.configure("TCombobox", fieldbackground="#0a1425", foreground=TEXT, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#0a1425")], foreground=[("readonly", TEXT)])
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", PANEL)], foreground=[("active", TEXT)])

    def _build_main_window(self) -> None:
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=28, pady=(22, 14))
        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="BAYSIM", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="JSBSim görselleştirme kontrol merkezi",
            style="Muted.TLabel",
        ).pack(anchor="w")
        status = tk.Label(
            header,
            textvariable=self.renderer_status_var,
            bg=PANEL_ALT,
            fg=MUTED,
            padx=14,
            pady=7,
            font=("Segoe UI Semibold", 9),
        )
        status.pack(side="right", anchor="n")

        content = ttk.Frame(self.root)
        content.pack(fill="both", expand=True, padx=28)
        content.columnconfigure(0, weight=0, minsize=330)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_status_panel(content)
        self._build_settings_panel(content)
        self._build_footer()

    def _build_status_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=20)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(panel, text="Sistem durumu", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            panel,
            text="Başlatmadan önce gerekli bileşenleri doğrula.",
            style="PanelMuted.TLabel",
            wraplength=280,
        ).pack(anchor="w", pady=(4, 16))

        for key, title in (
            ("godot", "Godot Engine"),
            ("jsb_forge", "jsb-forge projesi"),
            ("jsbsim", "JSBSim Python"),
            ("udp", "UDP dinleme portu"),
        ):
            card = tk.Frame(panel, bg=PANEL_ALT, padx=12, pady=10)
            card.pack(fill="x", pady=5)
            tk.Label(
                card,
                text=title,
                bg=PANEL_ALT,
                fg=TEXT,
                font=("Segoe UI Semibold", 9),
            ).pack(anchor="w")
            label = tk.Label(
                card,
                text="● Henüz kontrol edilmedi",
                bg=PANEL_ALT,
                fg=MUTED,
                font=("Segoe UI", 9),
                justify="left",
                wraplength=270,
            )
            label.pack(anchor="w", pady=(3, 0))
            self.status_labels[key] = label

        self.check_button = ttk.Button(
            panel,
            text="Kontrolleri yenile",
            style="Secondary.TButton",
            command=self._start_checks,
        )
        self.check_button.pack(fill="x", pady=(16, 7))
        self.probe_button = ttk.Button(
            panel,
            text="5 sn telemetri bekle",
            style="Secondary.TButton",
            command=self._start_udp_probe,
        )
        self.probe_button.pack(fill="x")
        ttk.Label(
            panel,
            text="Telemetri testi portu geçici olarak dinler; renderer kapalıyken kullanılır.",
            style="PanelMuted.TLabel",
            wraplength=280,
        ).pack(anchor="w", pady=(8, 0))

    def _build_settings_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=20)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="Başlatma ayarları", style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            panel,
            text="Ayarlar Godot başlamadan önce runtime yapılandırmasına yazılır.",
            style="PanelMuted.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 14))

        row = 2
        row = self._path_row(panel, row, "Godot", self.godot_var, self._browse_godot)
        row = self._path_row(panel, row, "jsb-forge", self.jsb_forge_var, self._browse_jsb_forge)
        row = self._path_row(panel, row, "JSBSim Python", self.jsbsim_python_var, self._browse_python)

        self._separator(panel, row, "Telemetri")
        row += 1
        row = self._field_row(panel, row, "UDP portu", self.port_var)
        row = self._field_row(panel, row, "Zaman aşımı (sn)", self.timeout_var)
        row = self._field_row(panel, row, "Poz yumuşatma", self.smoothing_var)

        ttk.Label(panel, text="Konum kaynağı", style="Panel.TLabel").grid(
            row=row, column=0, sticky="w", pady=5
        )
        source = ttk.Combobox(
            panel,
            textvariable=self.position_source_var,
            values=("local", "wgs84"),
            state="readonly",
            width=18,
        )
        source.grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        self._separator(panel, row, "Dünya orijini")
        row += 1
        row = self._field_row(panel, row, "Enlem (°)", self.origin_lat_var)
        row = self._field_row(panel, row, "Boylam (°)", self.origin_lon_var)
        row = self._field_row(panel, row, "MSL irtifası (m)", self.origin_alt_var)

        self._separator(panel, row, "Görüntü")
        row += 1
        dimensions = ttk.Frame(panel, style="Panel.TFrame")
        ttk.Label(panel, text="Pencere", style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=5)
        dimensions.grid(row=row, column=1, sticky="w", pady=5)
        ttk.Entry(dimensions, textvariable=self.width_var, width=9).pack(side="left")
        ttk.Label(dimensions, text=" × ", style="Panel.TLabel").pack(side="left")
        ttk.Entry(dimensions, textvariable=self.height_var, width=9).pack(side="left")
        row += 1
        ttk.Checkbutton(panel, text="Tam ekran başlat", variable=self.fullscreen_var).grid(
            row=row, column=1, sticky="w", pady=4
        )
        row += 1
        ttk.Checkbutton(
            panel,
            text="Launcher açıldığında renderer'ı otomatik başlat",
            variable=self.auto_start_var,
        ).grid(row=row, column=1, sticky="w", pady=4)

    def _build_footer(self) -> None:
        footer = ttk.Frame(self.root)
        footer.pack(fill="x", padx=28, pady=(14, 22))

        log_frame = tk.Frame(footer, bg=PANEL, padx=12, pady=9)
        log_frame.pack(fill="x", pady=(0, 12))
        self.log_text = tk.Text(
            log_frame,
            height=5,
            bg=PANEL,
            fg=MUTED,
            insertbackground=TEXT,
            borderwidth=0,
            highlightthickness=0,
            font=("Cascadia Mono", 9),
            state="disabled",
        )
        self.log_text.pack(fill="x")

        buttons = ttk.Frame(footer)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text="Ayarları kaydet",
            style="Secondary.TButton",
            command=self._save_only,
        ).pack(side="left")
        self.stop_button = ttk.Button(
            buttons,
            text="Renderer'ı durdur",
            style="Secondary.TButton",
            command=self._stop_renderer,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(8, 0))
        self.start_button = ttk.Button(
            buttons,
            text="BAYSIM'i başlat",
            style="Accent.TButton",
            command=self._start_renderer,
        )
        self.start_button.pack(side="right")

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        title: str,
        variable: tk.StringVar,
        command: Any,
    ) -> int:
        ttk.Label(parent, text=title, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5, padx=(0, 8))
        ttk.Button(parent, text="Seç", style="Secondary.TButton", command=command).grid(
            row=row, column=2, pady=5
        )
        return row + 1

    def _field_row(self, parent: ttk.Frame, row: int, title: str, variable: tk.StringVar) -> int:
        ttk.Label(parent, text=title, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable, width=24).grid(row=row, column=1, sticky="w", pady=5)
        return row + 1

    def _separator(self, parent: ttk.Frame, row: int, title: str) -> None:
        label = tk.Label(
            parent,
            text=title.upper(),
            bg=PANEL,
            fg=ACCENT,
            font=("Segoe UI Semibold", 8),
        )
        label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(14, 4))

    def _show_splash(self) -> None:
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        splash.configure(bg=BG)
        width, height = 700, 390
        x = (splash.winfo_screenwidth() - width) // 2
        y = (splash.winfo_screenheight() - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")
        splash.attributes("-topmost", True)

        canvas = tk.Canvas(splash, width=width, height=height, bg=BG, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_rectangle(0, 0, width, 8, fill=ACCENT, outline="")
        canvas.create_oval(500, -130, 820, 190, fill="#0d2a39", outline="")
        canvas.create_oval(-130, 260, 190, 580, fill="#0b2237", outline="")
        canvas.create_text(62, 118, text="BAYSIM", anchor="w", fill=TEXT, font=("Segoe UI Semibold", 42))
        canvas.create_text(
            65,
            177,
            text="FLIGHT VISUALIZATION SYSTEM",
            anchor="w",
            fill=ACCENT,
            font=("Segoe UI Semibold", 11),
        )
        canvas.create_text(
            65,
            215,
            text="JSBSim telemetrisi · gerçek dünya · replay",
            anchor="w",
            fill=MUTED,
            font=("Segoe UI", 12),
        )
        canvas.create_rectangle(65, 310, 635, 316, fill="#1b2b41", outline="")
        progress = canvas.create_rectangle(65, 310, 65, 316, fill=ACCENT, outline="")
        status = canvas.create_text(
            65,
            340,
            text="Başlatıcı hazırlanıyor…",
            anchor="w",
            fill=MUTED,
            font=("Segoe UI", 9),
        )

        def advance(value: int = 0) -> None:
            if not splash.winfo_exists():
                return
            canvas.coords(progress, 65, 310, 65 + 570 * value / 100.0, 316)
            if value < 100:
                message = "Sistem yolları denetleniyor…" if value > 45 else "Başlatıcı hazırlanıyor…"
                canvas.itemconfigure(status, text=message)
                splash.after(18, advance, value + 2)
                return
            canvas.itemconfigure(status, text="Hazır")
            splash.after(180, finish)

        def finish() -> None:
            splash.destroy()
            self.root.deiconify()
            self.root.lift()
            self._append_log("Launcher hazır. Renderer kullanıcı komutu bekliyor.")
            self._start_checks()
            if self.auto_start_var.get():
                self.root.after(500, self._start_renderer)

        advance()

    def _collect_settings(self) -> LauncherSettings:
        try:
            settings = LauncherSettings(
                godot_executable=self.godot_var.get().strip(),
                jsb_forge_path=self.jsb_forge_var.get().strip(),
                jsbsim_python=self.jsbsim_python_var.get().strip(),
                world_id=self.settings.world_id,
                telemetry_port=int(self.port_var.get()),
                position_source=self.position_source_var.get(),
                origin_lat_deg=float(self.origin_lat_var.get()),
                origin_lon_deg=float(self.origin_lon_var.get()),
                origin_alt_msl_m=float(self.origin_alt_var.get()),
                connection_timeout_s=float(self.timeout_var.get()),
                smoothing=float(self.smoothing_var.get()),
                fullscreen=self.fullscreen_var.get(),
                window_width=int(self.width_var.get()),
                window_height=int(self.height_var.get()),
                auto_start_renderer=self.auto_start_var.get(),
            )
        except ValueError as exc:
            raise ValueError("Sayısal ayarlardan biri geçersiz.") from exc
        errors = settings.validation_errors()
        if errors:
            raise ValueError("\n".join(errors))
        return settings

    def _save_only(self) -> None:
        try:
            settings = self._collect_settings()
            save_settings(settings)
            write_runtime_config(settings)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ayarlar kaydedilemedi", str(exc), parent=self.root)
            return
        self.settings = settings
        self._append_log("Ayarlar ve Godot runtime yapılandırması kaydedildi.")

    def _start_checks(self) -> None:
        if self.check_button.instate(["disabled"]):
            return
        self.check_button.configure(state="disabled")
        self._append_log("Sistem kontrolleri başlatıldı.")
        godot = self.godot_var.get().strip()
        jsb_forge = self.jsb_forge_var.get().strip()
        jsb_python = self.jsbsim_python_var.get().strip()
        try:
            port = int(self.port_var.get())
        except ValueError:
            port = 0

        def worker() -> None:
            results = {
                "godot": check_godot(godot),
                "jsb_forge": check_jsb_forge(jsb_forge),
                "jsbsim": check_jsbsim(jsb_python),
                "udp": check_udp_port(port),
            }
            self.events.put(("checks", results))

        Thread(target=worker, daemon=True).start()

    def _start_udp_probe(self) -> None:
        if self.process is not None and self.process.poll() is None:
            messagebox.showinfo(
                "Renderer çalışıyor",
                "Godot UDP portunu kullanırken launcher aynı portu dinleyemez.",
                parent=self.root,
            )
            return
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Geçersiz port", "UDP portu sayı olmalı.", parent=self.root)
            return
        self.probe_button.configure(state="disabled")
        self._set_status("udp", CheckResult(False, "Telemetri bekleniyor…"), pending=True)
        self._append_log(f"UDP {port} üzerinde 5 saniye telemetri bekleniyor.")

        def worker() -> None:
            self.events.put(("probe", wait_for_telemetry(port, 5.0)))

        Thread(target=worker, daemon=True).start()

    def _start_renderer(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self._append_log("Renderer zaten çalışıyor.")
            return
        try:
            settings = self._collect_settings()
            save_settings(settings)
            config_path = write_runtime_config(settings)
            self.process = launch_godot(settings, config_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("BAYSIM başlatılamadı", str(exc), parent=self.root)
            return

        self.settings = settings
        self.renderer_status_var.set("● Renderer çalışıyor")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.probe_button.configure(state="disabled")
        self._append_log(f"Godot başlatıldı (PID {self.process.pid}, UDP {settings.telemetry_port}).")
        Thread(target=self._read_renderer_output, args=(self.process,), daemon=True).start()

    def _read_renderer_output(self, process: subprocess.Popen[str]) -> None:
        RUNTIME_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RUNTIME_LOG_PATH.open("w", encoding="utf-8") as log_file:
            if process.stdout is not None:
                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()
                    self.events.put(("log", line.rstrip()))
        return_code = process.wait()
        self.events.put(("renderer_exit", return_code))

    def _stop_renderer(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self._append_log("Renderer durduruluyor…")
        self.process.terminate()

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "checks":
                    for key, result in payload.items():
                        self._set_status(key, result)
                    self.check_button.configure(state="normal")
                    self._append_log("Sistem kontrolleri tamamlandı.")
                elif kind == "probe":
                    self._set_status("udp", payload)
                    self.probe_button.configure(state="normal")
                    self._append_log(f"Telemetri testi: {payload.summary} {payload.detail}".strip())
                elif kind == "log":
                    if payload:
                        self._append_log(f"Godot · {payload}")
                elif kind == "renderer_exit":
                    self.renderer_status_var.set(f"Renderer kapalı · çıkış {payload}")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.probe_button.configure(state="normal")
                    self.process = None
                    self._append_log(f"Godot kapandı (çıkış kodu {payload}).")
        except Empty:
            pass
        self.root.after(100, self._poll_events)

    def _set_status(self, key: str, result: CheckResult, pending: bool = False) -> None:
        color = WARNING if pending else (SUCCESS if result.ok else ERROR)
        detail = f"\n{result.detail}" if result.detail else ""
        self.status_labels[key].configure(text=f"● {result.summary}{detail}", fg=color)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _browse_godot(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Godot çalıştırılabilir dosyasını seç",
            filetypes=(("Executable", "*.exe"), ("All files", "*.*")),
        )
        if selected:
            self.godot_var.set(selected)

    def _browse_jsb_forge(self) -> None:
        selected = filedialog.askdirectory(parent=self.root, title="jsb-forge klasörünü seç")
        if selected:
            self.jsb_forge_var.set(selected)
            candidate = Path(selected) / "venvbaykar" / "Scripts" / "python.exe"
            if candidate.is_file():
                self.jsbsim_python_var.set(str(candidate))

    def _browse_python(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="JSBSim Python çalıştırıcısını seç",
            filetypes=(("Python", "python.exe"), ("Executable", "*.exe")),
        )
        if selected:
            self.jsbsim_python_var.set(selected)

    def _on_close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            should_close = messagebox.askyesno(
                "BAYSIM çalışıyor",
                "Renderer'ı durdurup launcher'ı kapatmak istiyor musunuz?",
                parent=self.root,
            )
            if not should_close:
                return
            self.process.terminate()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    LauncherApp().run()
