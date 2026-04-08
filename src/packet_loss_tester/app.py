from __future__ import annotations

import csv
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .ping_service import PingRequest, PingResult, ProbeStats, ensure_ping_available, run_single_ping


class PacketLossTesterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Win11 丢包测试工具")
        self.geometry("1320x860")
        self.minsize(1120, 760)
        self.configure(bg="#f3f6fb")
        self.option_add("*Font", ("Segoe UI", 10))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.result_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.results: list[PingResult] = []

        self.target_var = tk.StringVar(value="8.8.8.8")
        self.count_var = tk.StringVar(value="20")
        self.interval_var = tk.StringVar(value="1.0")
        self.timeout_var = tk.StringVar(value="1000")
        self.size_var = tk.StringVar(value="32")
        self.continuous_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="就绪")

        self.sent_var = tk.StringVar(value="0")
        self.received_var = tk.StringVar(value="0")
        self.loss_var = tk.StringVar(value="0.00%")
        self.avg_var = tk.StringVar(value="-")
        self.best_var = tk.StringVar(value="-")
        self.worst_var = tk.StringVar(value="-")
        self.jitter_var = tk.StringVar(value="-")

        self._configure_styles()
        self._build_layout()
        self.after(120, self._process_queue)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("App.TFrame", background="#f3f6fb")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Header.TLabel", background="#f3f6fb", foreground="#1a1f36", font=("Segoe UI Semibold", 19))
        style.configure("SubHeader.TLabel", background="#f3f6fb", foreground="#5a6475", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#5a6475", font=("Segoe UI Semibold", 10))
        style.configure("Metric.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 16))
        style.configure("Status.TLabel", background="#f3f6fb", foreground="#334155", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(16, 10), foreground="#ffffff", background="#0f6cbd")
        style.map(
            "Accent.TButton",
            background=[("active", "#115ea3"), ("disabled", "#7db1db")],
            foreground=[("disabled", "#f2f7fb")],
        )
        style.configure("Neutral.TButton", font=("Segoe UI Semibold", 10), padding=(16, 10))
        style.configure("TLabelframe", background="#ffffff")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#344054", font=("Segoe UI Semibold", 10))
        style.configure("Treeview", rowheight=30, font=("Consolas", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.configure("TNotebook", background="#f3f6fb", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 10), font=("Segoe UI Semibold", 10))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Win11 丢包测试工具", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="实时检测目标主机连通性、延迟和丢包率，支持 CSV 导出与 GitHub Actions 自动打包。",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        controls_card = ttk.Frame(root, style="Card.TFrame", padding=18)
        controls_card.pack(fill="x", pady=(18, 12))

        settings_frame = ttk.LabelFrame(controls_card, text="测试设置", padding=14)
        settings_frame.pack(fill="x")

        settings_grid = ttk.Frame(settings_frame, style="Card.TFrame")
        settings_grid.pack(fill="x")
        for column in range(4):
            settings_grid.columnconfigure(column, weight=1, uniform="settings")

        self._add_entry(settings_grid, "目标主机 / IP", self.target_var, 0, 0, 2)
        self.count_entry = self._add_entry(settings_grid, "次数", self.count_var, 0, 2)
        self._add_entry(settings_grid, "间隔(秒)", self.interval_var, 0, 3)
        self._add_entry(settings_grid, "超时(ms)", self.timeout_var, 1, 0)
        self._add_entry(settings_grid, "负载字节", self.size_var, 1, 1)

        continuous_frame = ttk.Frame(settings_grid, style="Card.TFrame", padding=(8, 22, 8, 0))
        continuous_frame.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=(0, 0), pady=(14, 0))
        ttk.Checkbutton(
            continuous_frame,
            text="持续测试直到手动停止",
            variable=self.continuous_var,
            command=self._toggle_count_state,
        ).pack(anchor="w")

        button_bar = ttk.Frame(controls_card, style="Card.TFrame")
        button_bar.pack(fill="x", pady=(14, 0))
        self.start_button = ttk.Button(button_bar, text="开始测试", style="Accent.TButton", command=self._start_test)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(button_bar, text="停止", style="Neutral.TButton", command=self._stop_test, state="disabled")
        self.stop_button.pack(side="left", padx=(10, 0))
        ttk.Button(button_bar, text="清空结果", style="Neutral.TButton", command=self._clear_results).pack(side="left", padx=(10, 0))
        ttk.Button(button_bar, text="导出 CSV", style="Neutral.TButton", command=self._export_csv).pack(side="left", padx=(10, 0))

        status_row = ttk.Frame(controls_card, style="Card.TFrame")
        status_row.pack(fill="x", pady=(10, 0))
        ttk.Label(status_row, textvariable=self.status_var, style="Status.TLabel", wraplength=1100, justify="left").pack(anchor="w")

        metrics = ttk.Frame(root, style="App.TFrame")
        metrics.pack(fill="x", pady=(0, 12))
        for column in range(4):
            metrics.columnconfigure(column, weight=1, uniform="metrics")
        metric_cards = [
            ("已发送", self.sent_var),
            ("已接收", self.received_var),
            ("丢包率", self.loss_var),
            ("平均延迟", self.avg_var),
            ("最低延迟", self.best_var),
            ("最高延迟", self.worst_var),
            ("抖动", self.jitter_var),
        ]
        for index, (title, variable) in enumerate(metric_cards):
            card = ttk.Frame(metrics, style="Card.TFrame", padding=14)
            row, column = divmod(index, 4)
            right_pad = 0 if column == 3 else 10
            bottom_pad = 0 if row == (len(metric_cards) - 1) // 4 else 10
            card.grid(row=row, column=column, sticky="nsew", padx=(0, right_pad), pady=(0, bottom_pad))
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=variable, style="Metric.TLabel").pack(anchor="w", pady=(8, 0))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        log_tab = ttk.Frame(notebook, style="Card.TFrame", padding=14)
        chart_tab = ttk.Frame(notebook, style="Card.TFrame", padding=14)
        raw_tab = ttk.Frame(notebook, style="Card.TFrame", padding=14)
        notebook.add(log_tab, text="实时记录")
        notebook.add(chart_tab, text="趋势图")
        notebook.add(raw_tab, text="原始输出")

        columns = ("sequence", "time", "status", "latency")
        self.tree = ttk.Treeview(log_tab, columns=columns, show="headings")
        self.tree.heading("sequence", text="序号")
        self.tree.heading("time", text="时间")
        self.tree.heading("status", text="状态")
        self.tree.heading("latency", text="RTT")
        self.tree.column("sequence", width=80, anchor="center")
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("status", width=180, anchor="center")
        self.tree.column("latency", width=120, anchor="center")
        tree_scroll = ttk.Scrollbar(log_tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.chart_canvas = tk.Canvas(chart_tab, bg="#fdfefe", bd=0, highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True)
        self.chart_canvas.bind("<Configure>", lambda _event: self._draw_chart())

        self.raw_output = scrolledtext.ScrolledText(
            raw_tab,
            wrap="word",
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            relief="flat",
            padx=12,
            pady=12,
        )
        self.raw_output.pack(fill="both", expand=True)

        self._toggle_count_state()

    def _add_entry(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> ttk.Entry:
        field = ttk.Frame(parent, style="Card.TFrame")
        field.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=(0, 16), pady=(0, 14))
        ttk.Label(field, text=label).pack(anchor="w", pady=(0, 6))
        entry = ttk.Entry(field, textvariable=variable)
        entry.pack(fill="x")
        return entry

    def _toggle_count_state(self) -> None:
        self.count_entry.configure(state="disabled" if self.continuous_var.get() else "normal")

    def _parse_request(self) -> PingRequest:
        target = self.target_var.get().strip()
        if not target:
            raise ValueError("目标主机不能为空。")

        try:
            interval_seconds = float(self.interval_var.get())
        except ValueError as exc:
            raise ValueError("间隔必须是数字。") from exc

        try:
            timeout_ms = int(self.timeout_var.get())
            payload_size = int(self.size_var.get())
        except ValueError as exc:
            raise ValueError("超时和负载字节必须是整数。") from exc

        count = None
        if not self.continuous_var.get():
            try:
                count = int(self.count_var.get())
            except ValueError as exc:
                raise ValueError("次数必须是整数。") from exc
            if count <= 0:
                raise ValueError("次数必须大于 0。")

        if interval_seconds <= 0:
            raise ValueError("间隔必须大于 0。")
        if timeout_ms <= 0:
            raise ValueError("超时必须大于 0。")
        if payload_size < 0:
            raise ValueError("负载字节不能为负数。")

        return PingRequest(
            target=target,
            count=count,
            interval_seconds=interval_seconds,
            timeout_ms=timeout_ms,
            payload_size=payload_size,
        )

    def _start_test(self) -> None:
        try:
            ensure_ping_available()
            request = self._parse_request()
        except (FileNotFoundError, ValueError) as exc:
            messagebox.showerror("无法开始测试", str(exc), parent=self)
            return

        self._clear_results(force=True)
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set(f"测试中: {request.target}")
        self.worker_thread = threading.Thread(target=self._run_probe_loop, args=(request,), daemon=True)
        self.worker_thread.start()

    def _run_probe_loop(self, request: PingRequest) -> None:
        total = request.count
        sequence = 1
        while not self.stop_event.is_set() and (total is None or sequence <= total):
            result = run_single_ping(request, sequence)
            self.result_queue.put(("result", result))
            sequence += 1
            if total is not None and sequence > total:
                break
            sleep_left = request.interval_seconds
            while sleep_left > 0 and not self.stop_event.is_set():
                step = min(0.1, sleep_left)
                time.sleep(step)
                sleep_left -= step

        message = "测试已停止" if self.stop_event.is_set() else "测试完成"
        self.result_queue.put(("finished", message))

    def _stop_test(self) -> None:
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status_var.set("正在停止...")

    def _clear_results(self, force: bool = False) -> None:
        if self.worker_thread and self.worker_thread.is_alive() and not force:
            messagebox.showinfo("测试进行中", "请先停止当前测试。", parent=self)
            return
        self.results.clear()
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        self.raw_output.delete("1.0", "end")
        self._update_metrics()
        self._draw_chart()
        if not force:
            self.status_var.set("结果已清空")

    def _append_result(self, result: PingResult) -> None:
        self.results.append(result)
        latency_text = f"{result.latency_ms:.1f} ms" if result.latency_ms is not None else "-"
        self.tree.insert("", "end", values=(result.sequence, result.sampled_at.strftime("%H:%M:%S"), result.status, latency_text))
        self.tree.yview_moveto(1.0)
        self.raw_output.insert("end", f"[#{result.sequence}] {result.sampled_at:%Y-%m-%d %H:%M:%S} {result.status}\n{result.raw_output}\n\n")
        self.raw_output.see("end")
        self._update_metrics()
        self._draw_chart()

    def _update_metrics(self) -> None:
        stats = ProbeStats.from_results(self.results)
        self.sent_var.set(str(stats.sent))
        self.received_var.set(str(stats.received))
        self.loss_var.set(f"{stats.loss_rate:.2f}%")
        self.avg_var.set(self._format_latency(stats.avg_latency_ms))
        self.best_var.set(self._format_latency(stats.min_latency_ms))
        self.worst_var.set(self._format_latency(stats.max_latency_ms))
        self.jitter_var.set(self._format_latency(stats.jitter_ms))

    @staticmethod
    def _format_latency(value: float | None) -> str:
        return "-" if value is None else f"{value:.1f} ms"

    def _draw_chart(self) -> None:
        canvas = self.chart_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 600)
        height = max(canvas.winfo_height(), 320)

        left, top, right, bottom = 52, 28, 24, 44
        plot_width = width - left - right
        plot_height = height - top - bottom

        if not self.results:
            canvas.create_text(
                width / 2,
                height / 2,
                text="开始测试后，这里会显示最近 60 次探测的 RTT 趋势。",
                fill="#5a6475",
                font=("Segoe UI", 11),
            )
            return

        recent = self.results[-60:]
        latencies = [item.latency_ms for item in recent if item.latency_ms is not None]
        max_latency = max(latencies) if latencies else 10.0
        max_latency = max(max_latency, 10.0)
        step_count = max(len(recent) - 1, 1)

        canvas.create_rectangle(left, top, left + plot_width, top + plot_height, outline="#d7deea", width=1)

        for index in range(5):
            ratio = index / 4
            y = top + plot_height * ratio
            value = max_latency * (1 - ratio)
            canvas.create_line(left, y, left + plot_width, y, fill="#e8edf5")
            canvas.create_text(left - 10, y, text=f"{value:.0f}", fill="#64748b", font=("Segoe UI", 9), anchor="e")

        canvas.create_text(left, height - 16, text="最近 60 次采样", fill="#64748b", font=("Segoe UI", 9), anchor="w")
        canvas.create_text(width - 10, top - 10, text="RTT (ms)", fill="#64748b", font=("Segoe UI", 9), anchor="e")

        previous_success_point: tuple[float, float] | None = None
        for index, result in enumerate(recent):
            x = left + plot_width * (index / step_count)
            if result.success and result.latency_ms is not None:
                y = top + plot_height * (1 - min(result.latency_ms / max_latency, 1))
                if previous_success_point is not None:
                    canvas.create_line(previous_success_point[0], previous_success_point[1], x, y, fill="#0f6cbd", width=2)
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#0f6cbd", outline="#ffffff", width=1)
                previous_success_point = (x, y)
            else:
                miss_top = top + plot_height - 18
                canvas.create_line(x - 6, miss_top, x + 6, miss_top + 12, fill="#c50f1f", width=2)
                canvas.create_line(x + 6, miss_top, x - 6, miss_top + 12, fill="#c50f1f", width=2)

        stats = ProbeStats.from_results(recent)
        summary = f"丢包率 {stats.loss_rate:.2f}% | 平均 {self._format_latency(stats.avg_latency_ms)} | 抖动 {self._format_latency(stats.jitter_ms)}"
        canvas.create_text(left, 10, text=summary, fill="#1f2937", font=("Segoe UI Semibold", 10), anchor="w")

    def _process_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "result":
                    self._append_result(payload)  # type: ignore[arg-type]
                    latest: PingResult = payload  # type: ignore[assignment]
                    self.status_var.set(f"测试中: {latest.target} | 最近结果: {latest.status}")
                elif kind == "finished":
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.status_var.set(str(payload))
        except queue.Empty:
            pass
        finally:
            self.after(120, self._process_queue)

    def _export_csv(self) -> None:
        if not self.results:
            messagebox.showinfo("暂无数据", "没有可以导出的测试结果。", parent=self)
            return

        initial_name = f"packet-loss-report-{self.results[-1].sampled_at:%Y%m%d-%H%M%S}.csv"
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="导出为 CSV",
            defaultextension=".csv",
            initialfile=initial_name,
            filetypes=[("CSV 文件", "*.csv")],
        )
        if not file_path:
            return

        stats = ProbeStats.from_results(self.results)
        with Path(file_path).open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Target", self.results[0].target])
            writer.writerow(["Sent", stats.sent])
            writer.writerow(["Received", stats.received])
            writer.writerow(["Lost", stats.lost])
            writer.writerow(["LossRate", f"{stats.loss_rate:.2f}%"])
            writer.writerow(["AverageLatencyMs", "" if stats.avg_latency_ms is None else f"{stats.avg_latency_ms:.2f}"])
            writer.writerow([])
            writer.writerow(["Sequence", "Timestamp", "Status", "LatencyMs"])
            for result in self.results:
                writer.writerow(
                    [
                        result.sequence,
                        result.sampled_at.isoformat(timespec="seconds"),
                        result.status,
                        "" if result.latency_ms is None else f"{result.latency_ms:.2f}",
                    ]
                )

        self.status_var.set(f"已导出: {file_path}")

    def _on_close(self) -> None:
        self.stop_event.set()
        self.destroy()


def main() -> None:
    app = PacketLossTesterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
