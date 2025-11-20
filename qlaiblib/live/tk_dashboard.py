"""Enhanced Tkinter live dashboard with multi-tab layout."""

from __future__ import annotations

import itertools
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ..coincidence.specs import DEFAULT_SPECS
from ..data.models import CoincidenceResult, MetricValue
from ..plotting import static as static_plots
from ..plotting import timeseries as ts_plots
from ..io import coincfinder_backend as cf_backend
from ..utils import settings as settings_store
from .controller import LiveAcquisition, LiveUpdate
from .history import HistoryBuffer

PLOT_MODES = {
    "1": "singles",
    "2": "coincidences",
    "3": "singles+coincidences",
    "4": "metrics",
    "5": "all",
    "6": "chsh_full",
}

BASE_COINCIDENCE_LABELS = ["HH", "VV", "HV", "VH", "DD", "AA", "DA", "AD"]
CHSH_LABELS = [
    "HH", "HV", "VH", "VV",
    "HD", "HA", "VD", "VA",
    "DH", "DV", "AH", "AV",
    "DD", "DA", "AD", "AA",
]

COLOR_PALETTE = [
    "#FF595E",
    "#FFCA3A",
    "#8AC926",
    "#1982C4",
    "#6A4C93",
    "#FF924C",
    "#9D4EDD",
    "#2EC4B6",
    "#E71D36",
    "#F15BB5",
    "#00BBF9",
    "#00F5D4",
]

COLOR_BG = "#474747"
COLOR_GRID = "#ff646f6d"
LEGEND_KW = {"facecolor": COLOR_BG, "edgecolor": "white", "labelcolor": "white"}

class DashboardApp(tk.Tk):
    def __init__(self, controller: LiveAcquisition, history_points: int = 500):
        super().__init__()
        self.title("QLaib Live Dashboard")
        self.controller = controller
        self.controller.subscribe(self._enqueue_update)
        self._queue: "queue.Queue[LiveUpdate]" = queue.Queue()
        self.history = HistoryBuffer(max_points=history_points)
        self._view_mode = "5"
        self.settings = settings_store.load()
        self.specs = controller.pipeline.specs if controller.pipeline.specs else DEFAULT_SPECS
        self.max_points_var = tk.IntVar(value=history_points)
        self.hist_auto_var = tk.BooleanVar(value=True)
        self.hist_pair_var = tk.StringVar(value=self.specs[0].label)
        self.hist_window_ps = tk.DoubleVar(value=200.0)
        self.hist_start_ps = tk.DoubleVar(value=-8000.0)
        self.hist_end_ps = tk.DoubleVar(value=8000.0)
        self.hist_step_ps = tk.DoubleVar(value=50.0)
        self.coinc_window_ps = tk.DoubleVar(value=200.0)
        self.timeseries_chunk = tk.DoubleVar(value=controller.exposure_sec)
        self._latest_batch = None
        self._latest_flatten = {}
        self._elapsed = 0.0
        self._last_counts: dict[str, int] = {}
        self._last_metrics: list[MetricValue] = []
        self.delay_vars = {ch: tk.DoubleVar(value=self.settings.get("delays_ps", {}).get(str(ch), 0.0)) for ch in range(1, 9)}
        for ch, var in self.delay_vars.items():
            var.trace_add("write", lambda *_args, ch=ch: self._update_delay_setting(ch))
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._pending_histogram = None
        self._color_cache = {"singles": {}, "coincidences": {}, "chsh_counts": {}, "chsh": {}}
        self._chsh_errorbar = None

        self._build_ui()
        self._running = False
        self.after(200, self._poll_updates)
        for key in PLOT_MODES:
            self.bind(key, lambda e, mode=key: self._set_view_mode(mode))
        self.bind("q", lambda e: self.on_close())

    # --------------------------- UI construction ---------------------------
    def _build_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.plot_tab = ttk.Frame(self.notebook)
        self.hist_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.export_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.plot_tab, text="Plots")
        self.notebook.add(self.hist_tab, text="Histograms")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.export_tab, text="Data / Export")
        self._build_plot_tab()
        self._build_hist_tab()
        self._build_settings_tab()
        self._build_export_tab()

    def _build_plot_tab(self):
        controls = ttk.Frame(self.plot_tab)
        controls.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(controls, text="Start", command=self.start).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Stop", command=self.stop).pack(side=tk.LEFT, padx=4)
        ttk.Label(controls, text="Exposure (s)").pack(side=tk.LEFT, padx=(16, 4))
        self.exposure_var = tk.DoubleVar(value=self.controller.exposure_sec)
        ttk.Spinbox(
            controls,
            from_=0.1,
            to=60.0,
            increment=0.1,
            textvariable=self.exposure_var,
            width=6,
            command=self._update_exposure,
        ).pack(side=tk.LEFT)
        ttk.Label(controls, text="Timeseries view (keys 1-6)").pack(side=tk.RIGHT, padx=8)

        self.figure = plt.Figure(figsize=(10, 7), dpi=100)
        self.figure.patch.set_facecolor(COLOR_BG)
        self.ax_singles = None
        self.ax_coinc = None
        self.ax_metrics = None
        self.ax_metrics_secondary = None
        self.ax_chsh_counts = None
        self.ax_chsh_s = None
        self._current_layout: tuple[str, ...] = ()
        self._lines = {
            "singles": {},
            "coincidences": {},
            "visibility": None,
            "qber": None,
        }
        self._chsh_fill = None
        self._chsh_errorbar = None
        self._chsh_count_lines: dict[str, any] = {}
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_tab)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.figure.tight_layout()

    def _build_hist_tab(self):
        top = ttk.Frame(self.hist_tab)
        top.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(top, text="Pair").pack(side=tk.LEFT)
        ttk.Combobox(top, values=[spec.label for spec in self.specs], textvariable=self.hist_pair_var, state="readonly", width=10).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="Window ps").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.hist_window_ps, width=7).pack(side=tk.LEFT, padx=2)
        ttk.Label(top, text="Start ps").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.hist_start_ps, width=7).pack(side=tk.LEFT, padx=2)
        ttk.Label(top, text="End ps").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.hist_end_ps, width=7).pack(side=tk.LEFT, padx=2)
        ttk.Label(top, text="Step ps").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.hist_step_ps, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Compute", command=self._refresh_histogram).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(top, text="Auto-refresh", variable=self.hist_auto_var).pack(side=tk.LEFT, padx=4)

        self.hist_fig = plt.Figure(figsize=(8, 4), dpi=100)
        self.hist_ax = self.hist_fig.add_subplot(111)
        self.hist_canvas = FigureCanvasTkAgg(self.hist_fig, master=self.hist_tab)
        self.hist_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.hist_fig.tight_layout()

    def _build_settings_tab(self):
        frame = ttk.Frame(self.settings_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Label(frame, text="Per-channel delays (ps)").grid(row=0, column=0, sticky="w")
        for ch in range(1, 9):
            ttk.Label(frame, text=f"Ch {ch}").grid(row=ch, column=0, sticky="w")
            ttk.Entry(frame, textvariable=self.delay_vars[ch], width=8).grid(row=ch, column=1, sticky="w", padx=4)
        ttk.Label(frame, text="Coincidence window (ps)").grid(row=10, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.coinc_window_ps, width=8).grid(row=10, column=1, sticky="w")

    def _build_export_tab(self):
        frame = ttk.Frame(self.export_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Label(frame, text="History length (points)").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(frame, from_=50, to=2000, increment=50, textvariable=self.max_points_var, width=8, command=self._update_history_length).grid(row=0, column=1, sticky="w")
        ttk.Button(frame, text="Export history to CSV", command=self._export_history).grid(row=1, column=0, pady=8, sticky="w")
        ttk.Button(frame, text="Record raw BIN", command=self._record_raw).grid(row=1, column=1, pady=8, sticky="w")
        ttk.Label(frame, text="Timeseries chunk (s)").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.timeseries_chunk, width=8).grid(row=2, column=1, sticky="w")

    # ------------------------------ Callbacks ------------------------------
    def start(self):
        if self._running:
            return
        self._running = True
        self.controller.start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        self.controller.stop()

    def _update_exposure(self):
        value = float(self.exposure_var.get())
        self.controller.exposure_sec = value

    def _update_history_length(self):
        self.history.resize(int(self.max_points_var.get()))

    def _export_history(self):
        if not self.history.times:
            messagebox.showinfo("Export", "No history to export yet.")
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", title="Save history")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            header = ["time"] + [f"S{ch}" for ch in sorted(self.history.singles)] + list(self.history.coincidences.keys()) + list(self.history.metrics.keys())
            fh.write(",".join(header) + "\n")
            for idx, t in enumerate(self.history.times):
                row = [f"{t:.3f}"]
                for ch in sorted(self.history.singles):
                    data = list(self.history.singles[ch])
                    row.append(str(data[idx]) if idx < len(data) else "")
                for label in self.history.coincidences:
                    data = list(self.history.coincidences[label])
                    row.append(str(data[idx]) if idx < len(data) else "")
                for name in self.history.metrics:
                    data = list(self.history.metrics[name])
                    row.append(str(data[idx]) if idx < len(data) else "")
                fh.write(",".join(row) + "\n")
        messagebox.showinfo("Export", f"History written to {path}")

    def _record_raw(self):
        backend = getattr(self.controller, "backend", None)
        if backend is None or not hasattr(backend, "record_raw"):
            messagebox.showwarning("Record", "Current backend does not support raw recording.")
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".bin", title="Select BIN output")
        if not path:
            return
        duration = simple_prompt(self, "Recording duration (s)", str(self.controller.exposure_sec))
        try:
            dur = float(duration)
        except (TypeError, ValueError):
            messagebox.showerror("Record", "Invalid duration.")
            return
        try:
            backend.record_raw(path, dur)
            messagebox.showinfo("Record", f"Saved raw timestamps to {path}")
        except Exception as exc:
            messagebox.showerror("Record", f"Failed to record: {exc}")

    def _update_delay_setting(self, ch: int):
        value = float(self.delay_vars[ch].get())
        self.settings.setdefault("delays_ps", {})[str(ch)] = value
        settings_store.save(self.settings)

    # ------------------------------ Updates ------------------------------
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

    def _apply_update(self, update: LiveUpdate):
        self._latest_batch = update.batch
        singles_counts = {ch: float(len(arr)) for ch, arr in update.batch.singles.items()}
        self._elapsed += update.batch.duration_sec
        self.history.append(self._elapsed, singles_counts, update.coincidences, update.metrics)
        self._latest_flatten = {ch: arr.copy() for ch, arr in update.batch.singles.items()}
        self._last_counts = dict(update.coincidences.counts)
        self._last_metrics = list(update.metrics)
        self._refresh_plots()
        if self.hist_auto_var.get():
            self._refresh_histogram()

    def _refresh_plots(self):
        times = list(self.history.times)
        if not times:
            return
        layout_map = {
            "1": ("singles",),
            "2": ("coincidences",),
            "3": ("singles", "coincidences"),
            "4": ("metrics",),
            "5": ("singles", "coincidences", "metrics"),
            "6": ("chsh_counts", "chsh_s"),
        }
        layout = layout_map[self._view_mode]
        self._ensure_axes(layout)

        if self.ax_singles is not None and "singles" in layout:
            ax = self.ax_singles
            for ch, values in sorted(self.history.singles.items()):
                data = list(values)
                line = self._lines["singles"].get(ch)
                if line is None:
                    color = self._color_for("singles", ch)
                    (line,) = ax.plot([], [], label=f"Ch {ch}", color=color)
                    self._lines["singles"][ch] = line
                if data:
                    ts, ys = self._downsample_series(times, data)
                    line.set_data(ts, ys)
                else:
                    line.set_data([], [])
            self._set_xlimits(ax, times)
            ax.relim()
            ax.autoscale_view(True, True, True)
            ax.set_ylabel("Singles")
            ax.legend(ncol=4, fontsize=7, **LEGEND_KW)
            ax.grid(True, color=COLOR_GRID, alpha=0.3)
            ax.margins(x=0.02)
            self._style_axis(ax)

        if self.ax_coinc is not None and "coincidences" in layout:
            ax = self.ax_coinc
            for label, values in self.history.coincidences.items():
                if label not in BASE_COINCIDENCE_LABELS:
                    continue
                data = list(values)
                line = self._lines["coincidences"].get(label)
                if line is None:
                    color = self._color_for("coincidences", label)
                    (line,) = ax.plot([], [], label=label, color=color)
                    self._lines["coincidences"][label] = line
                contrast = self._contrast_for_label(label)
                heralding = self._heralding_for_label(label)
                display = f"{label} (C={data[-1] if data else 0}, H={heralding:.1f}%, V={contrast:.2f})"
                line.set_label(display)
                if data:
                    ts, ys = self._downsample_series(times, data)
                    line.set_data(ts, ys)
                else:
                    line.set_data([], [])
            self._set_xlimits(ax, times)
            ax.relim()
            ax.autoscale_view(True, True, True)
            ax.set_ylabel("Coincidences")
            ax.legend(ncol=2, fontsize=7, **LEGEND_KW)
            ax.grid(True, color=COLOR_GRID, alpha=0.3)
            ax.margins(x=0.02)
            self._style_axis(ax)

        if self.ax_metrics is not None and "metrics" in layout:
            vis_ax = self.ax_metrics
            qber_ax = self.ax_metrics_secondary or vis_ax.twinx()
            self.ax_metrics_secondary = qber_ax
            vis_data = list(self.history.metrics.get("visibility", []))
            qber_data = list(self.history.metrics.get("QBER_total", []))
            if self._lines["visibility"] is None:
                (self._lines["visibility"],) = vis_ax.plot([], [], label="Visibility", color="#00a6ff")
            if self._lines["qber"] is None:
                (self._lines["qber"],) = qber_ax.plot([], [], label="QBER", color="#ff006e")
            if vis_data:
                ts, ys = self._downsample_series(times, vis_data)
                self._lines["visibility"].set_data(ts, ys)
                vis_label = f"Visibility ({ys[-1]:.3f})" if ys else "Visibility"
            else:
                self._lines["visibility"].set_data([], [])
                vis_label = "Visibility"
            self._lines["visibility"].set_label(vis_label)
            if qber_data:
                ts, ys = self._downsample_series(times, qber_data)
                self._lines["qber"].set_data(ts, ys)
                qber_label = f"QBER ({ys[-1]:.3f})" if ys else "QBER"
            else:
                self._lines["qber"].set_data([], [])
                qber_label = "QBER"
            self._lines["qber"].set_label(qber_label)
            self._set_xlimits(vis_ax, times)
            if vis_data:
                vmin, vmax = min(vis_data), max(vis_data)
                if vmin == vmax:
                    vmin -= 0.05
                    vmax += 0.05
                vis_ax.set_ylim(max(0.0, vmin - 0.05), min(1.0, vmax + 0.05))
            else:
                vis_ax.set_ylim(0, 1)
            vis_ax.set_ylabel("Visibility")
            vis_ax.grid(True, color=COLOR_GRID, alpha=0.3)
            if qber_data:
                qmin, qmax = min(qber_data), max(qber_data)
                if qmin == qmax:
                    qmin -= 0.05
                    qmax += 0.05
                qber_ax.set_ylim(max(0.0, qmin - 0.05), min(1.0, qmax + 0.05))
            else:
                qber_ax.set_ylim(0, 1)
            self._set_xlimits(qber_ax, times)
            qber_ax.set_ylabel("QBER")
            lines, labels = vis_ax.get_legend_handles_labels()
            lines2, labels2 = qber_ax.get_legend_handles_labels()
            vis_ax.legend(lines + lines2, labels + labels2, fontsize=8, loc="upper right", **LEGEND_KW)
            vis_ax.margins(x=0.02)
            qber_ax.margins(x=0.02)
            self._style_axis(vis_ax)
            self._style_axis(qber_ax)

        if self.ax_chsh_counts is not None and "chsh_counts" in layout:
            ax = self.ax_chsh_counts
            for label in CHSH_LABELS:
                series = self.history.coincidences.get(label)
                line = self._chsh_count_lines.get(label)
                if line is None:
                    color = self._color_for("chsh_counts", label)
                    (line,) = ax.plot([], [], label=label, color=color)
                    self._chsh_count_lines[label] = line
                if series:
                    ts, ys = self._downsample_series(times, list(series))
                    line.set_data(ts, ys)
                else:
                    line.set_data([], [])
            self._set_xlimits(ax, times)
            ax.relim()
            ax.autoscale_view(True, True, True)
            ax.set_ylabel("Coincidences")
            ax.grid(True, color=COLOR_GRID, alpha=0.3)
            ax.legend(ncol=4, fontsize=7, **LEGEND_KW)
            ax.margins(x=0.02)
            self._style_axis(ax)

        if self.ax_chsh_s is not None and "chsh_s" in layout:
            ax = self.ax_chsh_s
            data = list(self.history.metrics.get("CHSH_S", []))
            sigmas = list(self.history.metric_sigmas.get("CHSH_S", []))
            if data:
                ts, ys, idx = self._downsample_series(times, data, return_indices=True)
                if self._chsh_errorbar:
                    line, caplines, barcols = self._chsh_errorbar
                    line.remove()
                    for cap in caplines:
                        cap.remove()
                    if isinstance(barcols, (list, tuple)):
                        for col in barcols:
                            if hasattr(col, "remove"):
                                col.remove()
                    elif hasattr(barcols, "remove"):
                        barcols.remove()
                color = self._color_for("chsh", "S")
                yerr = None
                ymin, ymax = min(ys), max(ys)
                if ymin == ymax:
                    ymin -= 0.05
                    ymax += 0.05
                ax.set_ylim(ymin - 0.05, ymax + 0.05)
                self._set_xlimits(ax, ts)
                if sigmas and len(sigmas) >= len(data):
                    sigma_arr = np.asarray(sigmas[-len(data):], dtype=float)
                    sigma_arr = sigma_arr[idx]
                    yerr = sigma_arr
                label = f"CHSH S ({ys[-1]:.3f}"
                if yerr is not None and len(yerr):
                    label += f"±{yerr[-1]:.3f}"
                label += ")"
                self._chsh_errorbar = ax.errorbar(
                    ts,
                    ys,
                    yerr=yerr,
                    fmt="-o",
                    color=color,
                    ecolor=color,
                    capsize=3,
                    label=label,
                )
                handle = self._chsh_errorbar[0]
                handle.set_label(label)
            else:
                if self._chsh_errorbar:
                    line, caplines, barcols = self._chsh_errorbar
                    line.remove()
                    for cap in caplines:
                        cap.remove()
                    if isinstance(barcols, (list, tuple)):
                        for col in barcols:
                            if hasattr(col, "remove"):
                                col.remove()
                    elif hasattr(barcols, "remove"):
                        barcols.remove()
                    self._chsh_errorbar = None
                ax.set_ylim(-0.1, 0.1)
            ax.set_ylabel("CHSH S")
            ax.grid(True, color=COLOR_GRID, alpha=0.3)
            if self._chsh_errorbar:
                handle = self._chsh_errorbar[0]
                ax.legend(handles=[handle], labels=[handle.get_label()], loc="upper right", **LEGEND_KW)
            ax.margins(x=0.02)
            self._style_axis(ax)

        self.canvas.draw_idle()

    def _ensure_axes(self, layout: tuple[str, ...]):
        if layout == self._current_layout:
            return
        self._current_layout = layout
        self.figure.clf()
        self.ax_singles = None
        self.ax_coinc = None
        self.ax_metrics = None
        self.ax_metrics_secondary = None
        self.ax_chsh_counts = None
        self.ax_chsh_s = None
        count = len(layout)
        sharex = None
        for idx, name in enumerate(layout):
            ax = self.figure.add_subplot(count, 1, idx + 1, sharex=sharex)
            if sharex is None:
                sharex = ax
            ax.set_facecolor(COLOR_BG)
            if name == "singles":
                self.ax_singles = ax
            elif name == "coincidences":
                self.ax_coinc = ax
            elif name == "metrics":
                self.ax_metrics = ax
                self.ax_metrics_secondary = ax.twinx()
                self._lines["visibility"] = None
                self._lines["qber"] = None
            elif name == "chsh_counts":
                self.ax_chsh_counts = ax
                self._chsh_count_lines = {}
            elif name == "chsh_s":
                self.ax_chsh_s = ax
        self._lines["singles"] = {}
        self._lines["coincidences"] = {}
        self._lines["visibility"] = None
        self._lines["qber"] = None
        self._chsh_errorbar = None
        self._chsh_fill = None
        self.figure.tight_layout()
        self.figure.subplots_adjust(left=0.12, right=0.98)

    def _downsample_series(self, times: list[float], data: list[float], limit: int | None = None, return_indices: bool = False):
        if not data:
            return ([], [], np.array([], dtype=int)) if return_indices else ([], [])
        limit = limit or min(self.history.max_points, 600)
        series_times = np.asarray(times[-len(data):], dtype=float)
        series_values = np.asarray(data, dtype=float)
        if series_values.size <= limit:
            idx = np.arange(series_values.size, dtype=int)
        else:
            idx = np.linspace(0, series_values.size - 1, limit, dtype=int)
        sampled_times = series_times[idx]
        sampled_values = series_values[idx]
        if return_indices:
            return sampled_times.tolist(), sampled_values.tolist(), idx
        return sampled_times.tolist(), sampled_values.tolist()

    def _color_for(self, kind: str, key) -> str:
        cache = self._color_cache.setdefault(kind, {})
        if key not in cache:
            cache[key] = COLOR_PALETTE[len(cache) % len(COLOR_PALETTE)]
        return cache[key]

    @staticmethod
    def _set_xlimits(ax, times):
        if not times:
            return
        if len(times) == 1:
            t = times[-1]
            ax.set_xlim(t - 1e-6, t + 1e-6)
        else:
            ax.set_xlim(times[0], times[-1])

    def _style_axis(self, ax, rotate_y=True):
        ax.set_facecolor(COLOR_BG)
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white", labelrotation=45 if rotate_y else 0)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_color("white")

    def _refresh_histogram(self):
        if not self._latest_flatten or self._pending_histogram:
            return
        label = self.hist_pair_var.get()
        spec = next((s for s in self.specs if s.label == label), None)
        if not spec or len(spec.channels) != 2:
            return
        ch_a, ch_b = spec.channels
        trace_a = self._latest_flatten.get(ch_a)
        trace_b = self._latest_flatten.get(ch_b)
        if trace_a is None or trace_b is None or not len(trace_a) or not len(trace_b):
            return
        params = (
            trace_a.copy(),
            trace_b.copy(),
            float(self.hist_window_ps.get()),
            float(self.hist_start_ps.get()),
            float(self.hist_end_ps.get()),
            float(self.hist_step_ps.get()),
            label,
        )
        self._pending_histogram = self.executor.submit(self._compute_histogram, params)
        self._pending_histogram.add_done_callback(lambda fut: self.after(0, self._update_histogram_plot, fut))

    @staticmethod
    def _compute_histogram(args):
        trace_a, trace_b, window_ps, start_ps, end_ps, step_ps, label = args
        offsets, counts = cf_backend.compute_histogram(
            trace_a,
            trace_b,
            window_ps=window_ps,
            delay_start_ps=start_ps,
            delay_end_ps=end_ps,
            delay_step_ps=step_ps,
        )
        return label, offsets, counts

    def _update_histogram_plot(self, future):
        self._pending_histogram = None
        if future.cancelled():
            return
        try:
            label, offsets, counts = future.result()
        except Exception as exc:
            print(f"Histogram computation failed: {exc}")
            return
        self.hist_ax.clear()
        self.hist_ax.plot(offsets, counts)
        self.hist_ax.set_xlabel("Delay (ps)")
        self.hist_ax.set_ylabel("Counts")
        self.hist_ax.set_title(f"Histogram {label}")
        self.hist_ax.grid(True, alpha=0.2)
        self.hist_canvas.draw_idle()

    def _contrast_for_label(self, label: str) -> float:
        counts = self._last_counts
        if not counts:
            return 0.0
        if label in {"HH", "VV", "HV", "VH"}:
            like = counts.get("HH", 0) + counts.get("VV", 0)
            cross = counts.get("HV", 0) + counts.get("VH", 0)
            return like / cross if cross else float(like)
        if label in {"DD", "AA", "DA", "AD"}:
            like = counts.get("DD", 0) + counts.get("AA", 0)
            cross = counts.get("DA", 0) + counts.get("AD", 0)
            return like / cross if cross else float(like)
        return 0.0

    def _heralding_for_label(self, label: str) -> float:
        try:
            ch_a, ch_b = next(spec.channels for spec in self.specs if spec.label == label)
        except StopIteration:
            return 0.0
        singles_a = self.history.singles.get(ch_a)
        singles_b = self.history.singles.get(ch_b)
        coincid = self.history.coincidences.get(label)
        if not singles_a or not singles_b or not coincid:
            return 0.0
        sa = singles_a[-1]
        sb = singles_b[-1]
        c = coincid[-1]
        if sa <= 0 or sb <= 0 or c <= 0:
            return 0.0
        return float(c) / ((sa * sb) ** 0.5) * 100.0

    def _set_view_mode(self, mode: str):
        if mode not in PLOT_MODES:
            return
        self._view_mode = mode
        self._refresh_plots()

    def on_close(self):
        try:
            self.stop()
        finally:
            try:
                self.controller.close()
            except Exception as exc:
                print(f"Failed to close controller: {exc}")
        self.executor.shutdown(wait=False)
        self.destroy()


def simple_prompt(parent, title: str, default: str) -> str | None:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    entry = ttk.Entry(dialog)
    entry.insert(0, default)
    entry.pack(padx=10, pady=10)
    value = {"result": None}

    def accept():
        value["result"] = entry.get()
        dialog.destroy()

    ttk.Button(dialog, text="OK", command=accept).pack(pady=5)
    dialog.grab_set()
    parent.wait_window(dialog)
    return value["result"]


def run_dashboard(controller: LiveAcquisition, history_points: int = 500):
    app = DashboardApp(controller, history_points=history_points)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
