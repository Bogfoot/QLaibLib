"""Tkinter-based live dashboard."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..data.models import MetricValue
from ..io import coincfinder_backend as cf_backend
from ..plotting import static as static_plots
from ..utils import settings as settings_store
from .controller import LiveAcquisition, LiveUpdate


class DashboardApp(tk.Tk):
    def __init__(self, controller: LiveAcquisition):
        super().__init__()
        self.title("QLaib Live Dashboard")
        self.controller = controller
        self.controller.subscribe(self._enqueue_update)
        self._queue: "queue.Queue[LiveUpdate]" = queue.Queue()
        self._latest_update: LiveUpdate | None = None
        self._latest_batch = None
        self.settings = settings_store.load()
        self.channel_vars: dict[int, tk.BooleanVar] = {}
        self.pair_vars: dict[str, tk.BooleanVar] = {}
        self.delay_vars: dict[str, tk.StringVar] = {}

        self._build_widgets()
        self._running = False
        self.after(200, self._poll_updates)

    def _build_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.live_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.live_tab, text="Live")
        self.notebook.add(self.settings_tab, text="Settings / Histogram")

        top = ttk.Frame(self.live_tab)
        top.pack(fill=tk.X, padx=10, pady=5)

        self.exposure_var = tk.DoubleVar(value=self.controller.exposure_sec)
        ttk.Label(top, text="Exposure (s)").pack(side=tk.LEFT)
        spin = ttk.Spinbox(top, from_=0.1, to=60.0, increment=0.1,
                            textvariable=self.exposure_var, width=6,
                            command=self._update_exposure)
        spin.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(top, text="Start", command=self.start)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Stop", command=self.stop).pack(side=tk.LEFT)

        self.metrics_var = tk.StringVar(value="Metrics will appear here")
        ttk.Label(self.live_tab, textvariable=self.metrics_var).pack(fill=tk.X, padx=10, pady=5)

        fig = Figure(figsize=(8, 5), dpi=100)
        self.ax_singles = fig.add_subplot(211)
        self.ax_coinc = fig.add_subplot(212)
        self.canvas = FigureCanvasTkAgg(fig, master=self.live_tab)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        fig.tight_layout()

        self._build_settings_tab()

    def _build_settings_tab(self):
        channels = sorted({ch for spec in self.controller.pipeline.specs for ch in spec.channels})
        pairs = [spec.label for spec in self.controller.pipeline.specs]

        channel_box = ttk.LabelFrame(self.settings_tab, text="Channels")
        channel_box.pack(fill=tk.X, padx=10, pady=5)
        for ch in channels:
            var = tk.BooleanVar(value=self.settings["channels"].get(str(ch), True))
            self.channel_vars[ch] = var
            ttk.Checkbutton(
                channel_box,
                text=f"Ch {ch}",
                variable=var,
                command=lambda ch=ch: self._on_channel_toggle(ch),
            ).pack(side=tk.LEFT, padx=2, pady=2)

        pairs_box = ttk.LabelFrame(self.settings_tab, text="Coincidence pairs")
        pairs_box.pack(fill=tk.X, padx=10, pady=5)
        for label in pairs:
            var = tk.BooleanVar(value=self.settings["pairs"].get(label, True))
            self.pair_vars[label] = var
            ttk.Checkbutton(
                pairs_box,
                text=label,
                variable=var,
                command=lambda lbl=label: self._on_pair_toggle(lbl),
            ).pack(side=tk.LEFT, padx=2, pady=2)

        delay_box = ttk.LabelFrame(self.settings_tab, text="Manual delays (ps)")
        delay_box.pack(fill=tk.X, padx=10, pady=5)
        for idx, spec in enumerate(self.controller.pipeline.specs):
            ttk.Label(delay_box, text=spec.label).grid(row=idx, column=0, sticky="w", padx=5, pady=2)
            default = self.settings["delays_ps"].get(spec.label, spec.delay_ps or 0.0)
            var = tk.StringVar(value=str(default))
            self.delay_vars[spec.label] = var
            entry = ttk.Entry(delay_box, width=10, textvariable=var)
            entry.grid(row=idx, column=1, padx=5, pady=2, sticky="w")
            var.trace_add("write", lambda *_args, lbl=spec.label: self._on_delay_change(lbl))
            if default is not None:
                self.controller.pipeline.update_delay(spec.label, float(default))

        hist_box = ttk.LabelFrame(self.settings_tab, text="Histogram")
        hist_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        form = ttk.Frame(hist_box)
        form.pack(fill=tk.X, pady=5)
        self.hist_pair_var = tk.StringVar(value=pairs[0] if pairs else "")
        ttk.Label(form, text="Pair").grid(row=0, column=0, padx=5, sticky="w")
        ttk.Combobox(form, values=pairs, textvariable=self.hist_pair_var, state="readonly", width=8).grid(row=0, column=1, padx=5)

        hist_defaults = self.settings.get("histogram", {})
        self.hist_start_var = tk.StringVar(value=str(hist_defaults.get("start_ps", -8000.0)))
        self.hist_end_var = tk.StringVar(value=str(hist_defaults.get("end_ps", 8000.0)))
        self.hist_step_var = tk.StringVar(value=str(hist_defaults.get("step_ps", 50.0)))

        ttk.Label(form, text="Start ps").grid(row=1, column=0, padx=5)
        ttk.Entry(form, textvariable=self.hist_start_var, width=10).grid(row=1, column=1, padx=5)
        ttk.Label(form, text="End ps").grid(row=1, column=2, padx=5)
        ttk.Entry(form, textvariable=self.hist_end_var, width=10).grid(row=1, column=3, padx=5)
        ttk.Label(form, text="Step ps").grid(row=1, column=4, padx=5)
        ttk.Entry(form, textvariable=self.hist_step_var, width=10).grid(row=1, column=5, padx=5)

        ttk.Button(form, text="Compute histogram", command=self._compute_histogram).grid(row=0, column=6, rowspan=2, padx=10)

        self.hist_fig = Figure(figsize=(6, 3), dpi=100)
        self.hist_ax = self.hist_fig.add_subplot(111)
        self.hist_canvas = FigureCanvasTkAgg(self.hist_fig, master=hist_box)
        self.hist_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.hist_ax.set_title("Histogram")
        self.hist_ax.set_xlabel("Delay (ps)")
        self.hist_ax.set_ylabel("Coincidences")

    def _update_exposure(self):
        self.controller.exposure_sec = float(self.exposure_var.get())
        self._save_settings()

    def _on_channel_toggle(self, ch: int):
        self.settings["channels"][str(ch)] = self.channel_vars[ch].get()
        self._save_settings()
        self._redraw_last_update()

    def _on_pair_toggle(self, label: str):
        self.settings["pairs"][label] = self.pair_vars[label].get()
        self._save_settings()
        self._redraw_last_update()

    def _on_delay_change(self, label: str):
        var = self.delay_vars[label]
        try:
            value = float(var.get())
        except ValueError:
            return
        self.controller.pipeline.update_delay(label, value)
        self.settings["delays_ps"][label] = value
        self._save_settings()

    def _save_settings(self):
        settings_store.save(self.settings)

    def _redraw_last_update(self):
        if self._latest_update is not None:
            self._apply_update(self._latest_update, store=False)

    def _enqueue_update(self, update: LiveUpdate):
        self._queue.put(update)

    def _poll_updates(self):
        while True:
            try:
                update = self._queue.get_nowait()
            except queue.Empty:
                break
            self._apply_update(update)
        self.after(200, self._poll_updates)

    def _apply_update(self, update: LiveUpdate, store: bool = True):
        self._latest_update = update
        self._latest_batch = update.batch
        active_channels = [ch for ch, var in self.channel_vars.items() if var.get()] or list(self.channel_vars.keys())
        active_pairs = [lbl for lbl, var in self.pair_vars.items() if var.get()] or self.controller.pipeline.labels()
        self.ax_singles.clear()
        static_plots.plot_singles(update.batch, channels=active_channels, ax=self.ax_singles)
        self.ax_coinc.clear()
        static_plots.plot_coincidences(update.coincidences, labels=active_pairs, ax=self.ax_coinc)
        self.canvas.draw_idle()
        self.metrics_var.set(_format_metrics(update.metrics))

    def start(self):
        if self._running:
            return
        self._running = True
        self.controller.start()
        self.start_btn.configure(state=tk.DISABLED)

    def stop(self):
        if not self._running:
            return
        self.controller.stop()
        self._running = False
        self.start_btn.configure(state=tk.NORMAL)

    def on_close(self):
        self.stop()
        self.controller.close()
        self.destroy()

    def _compute_histogram(self):
        if self._latest_batch is None:
            messagebox.showinfo("Histogram", "No data yet. Start the live view first.")
            return
        label = self.hist_pair_var.get()
        spec = next((s for s in self.controller.pipeline.specs if s.label == label), None)
        if spec is None:
            messagebox.showerror("Histogram", "Invalid pair selected.")
            return
        try:
            start = float(self.hist_start_var.get())
            end = float(self.hist_end_var.get())
            step = float(self.hist_step_var.get())
        except ValueError:
            messagebox.showerror("Histogram", "Invalid histogram parameters.")
            return
        arr_a = self._latest_batch.flatten(spec.channels[0])
        arr_b = self._latest_batch.flatten(spec.channels[1])
        if len(arr_a) == 0 or len(arr_b) == 0:
            messagebox.showinfo("Histogram", "Selected channels have no events in the latest batch.")
            return
        offsets, counts = cf_backend.compute_histogram(
            arr_a,
            arr_b,
            window_ps=spec.window_ps,
            delay_start_ps=start,
            delay_end_ps=end,
            delay_step_ps=step,
        )
        self.hist_ax.clear()
        self.hist_ax.plot(offsets, counts)
        self.hist_ax.set_title(f"Histogram {label}")
        self.hist_ax.set_xlabel("Delay (ps)")
        self.hist_ax.set_ylabel("Coincidences")
        self.hist_canvas.draw_idle()
        self.settings["histogram"] = {"start_ps": start, "end_ps": end, "step_ps": step}
        self._save_settings()


def _format_metrics(values: list[MetricValue]) -> str:
    parts = [f"{val.name}: {val.value:.3f}" for val in values]
    return " | ".join(parts)


def run_dashboard(controller: LiveAcquisition):
    app = DashboardApp(controller)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
