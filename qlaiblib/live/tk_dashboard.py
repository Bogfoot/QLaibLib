"""Enhanced Tkinter live dashboard with multi-tab layout."""

from __future__ import annotations

import itertools
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
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
}


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
        ttk.Label(controls, text="Timeseries view (keys 1-5)").pack(side=tk.RIGHT, padx=8)

        self.figure = plt.Figure(figsize=(10, 7), dpi=100)
        self.ax_singles = None
        self.ax_coinc = None
        self.ax_metrics = None
        self._current_layout: tuple[str, ...] = ()
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
        }
        layout = layout_map[self._view_mode]
        self._ensure_axes(layout)

        if self.ax_singles is not None and "singles" in layout:
            ax = self.ax_singles
            ax.clear()
            for ch, values in sorted(self.history.singles.items()):
                ax.plot(times[: len(values)], list(values), label=f"Ch {ch}")
            ax.set_ylabel("Singles")
            ax.legend(ncol=4, fontsize=7)
            ax.grid(True, alpha=0.2)

        if self.ax_coinc is not None and "coincidences" in layout:
            self.ax_coinc.clear()
            for label, values in self.history.coincidences.items():
                contrast = self._contrast_for_label(label)
                heralding = self._heralding_for_label(label)
                latest = values[-1] if values else 0
                display = f"{label} (C={latest}, H={heralding:.1f}%, V={contrast:.2f})"
                self.ax_coinc.plot(times[: len(values)], list(values), label=display)
            self.ax_coinc.set_ylabel("Coincidences")
            self.ax_coinc.legend(ncol=2, fontsize=7)
            self.ax_coinc.grid(True, alpha=0.2)

        if self.ax_metrics is not None and "metrics" in layout:
            vis_ax = self.ax_metrics
            vis_ax.clear()
            vis_ax.set_ylabel("Visibility")
            vis_ax.set_ylim(0, 1)
            vis_ax.grid(True, alpha=0.2)
            vis_ax.plot(times[: len(self.history.metrics.get("visibility", []))], list(self.history.metrics.get("visibility", [])), label="Visibility", color="#00a6ff")
            qber_ax = vis_ax.twinx()
            qber_ax.set_ylabel("QBER")
            qber_ax.set_ylim(0, 1)
            qber_ax.plot(times[: len(self.history.metrics.get("QBER_total", []))], list(self.history.metrics.get("QBER_total", [])), label="QBER", color="#ff006e")
            lines, labels = vis_ax.get_legend_handles_labels()
            lines2, labels2 = qber_ax.get_legend_handles_labels()
            vis_ax.legend(lines + lines2, labels + labels2, fontsize=8, loc="upper right")

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _ensure_axes(self, layout: tuple[str, ...]):
        if layout == self._current_layout:
            return
        self._current_layout = layout
        self.figure.clf()
        self.ax_singles = None
        self.ax_coinc = None
        self.ax_metrics = None
        count = len(layout)
        sharex = None
        for idx, name in enumerate(layout):
            ax = self.figure.add_subplot(count, 1, idx + 1, sharex=sharex)
            if sharex is None:
                sharex = ax
            if name == "singles":
                self.ax_singles = ax
            elif name == "coincidences":
                self.ax_coinc = ax
            elif name == "metrics":
                self.ax_metrics = ax
        self.figure.tight_layout()

    def _refresh_histogram(self):
        if not self._latest_flatten:
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
        offsets, counts = cf_backend.compute_histogram(
            trace_a,
            trace_b,
            window_ps=float(self.hist_window_ps.get()),
            delay_start_ps=float(self.hist_start_ps.get()),
            delay_end_ps=float(self.hist_end_ps.get()),
            delay_step_ps=float(self.hist_step_ps.get()),
        )
        self.hist_ax.clear()
        self.hist_ax.plot(offsets, counts)
        self.hist_ax.set_xlabel("Delay (ps)")
        self.hist_ax.set_ylabel("Counts")
        self.hist_ax.set_title(f"Histogram {label}")
        self.hist_ax.grid(True, alpha=0.2)
        self.hist_fig.tight_layout()
        self.hist_canvas.draw_idle()

    def _contrast_for_label(self, label: str) -> float:
        counts = self._last_counts
        if not counts:
            return 0.0
        if label in {"HH", "VV", "HV", "VH"}:
            like = counts.get("HH", 0) + counts.get("VV", 0)
            cross = counts.get("HV", 0) + counts.get("VH", 0)
            denom = like + cross
            return (like - cross) / denom if denom else 0.0
        if label in {"DD", "AA", "DA", "AD"}:
            like = counts.get("DD", 0) + counts.get("AA", 0)
            cross = counts.get("DA", 0) + counts.get("AD", 0)
            denom = like + cross
            return (like - cross) / denom if denom else 0.0
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
