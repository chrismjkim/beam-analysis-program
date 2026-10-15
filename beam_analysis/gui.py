"""Tkinter 기반 데스크톱 사용자 인터페이스."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from examples.textbook_examples import TEXTBOOK_EXAMPLES, example_4_2

from .formatting import format_result
from .models import Beam, DoublyReinforcedBeam, Material, SinglyReinforcedBeam, TBeam
from .plotting import COLORS, create_analysis_figure


FIELD_SETS: dict[str, tuple[tuple[str, str, float | None], ...]] = {
    "단근 직사각형보": (
        ("b", "보 폭 b [mm]", 300.0),
        ("h", "전체 높이 h [mm]", 600.0),
        ("d", "유효깊이 d [mm]", 515.0),
        ("d_t", "최외단 깊이 dt [mm] (빈칸=h-60)", None),
        ("as_tension", "인장철근 As [mm²]", 1800.0),
    ),
    "복근 직사각형보": (
        ("b", "보 폭 b [mm]", 300.0),
        ("h", "전체 높이 h [mm]", 600.0),
        ("d", "유효깊이 d [mm]", 515.0),
        ("d_t", "최외단 깊이 dt [mm] (빈칸=h-60)", None),
        ("d_prime", "압축철근 깊이 d' [mm]", 60.0),
        ("as_tension", "인장철근 As [mm²]", 8 * 387.1),
        ("as_compression", "압축철근 As' [mm²]", 2 * 387.1),
    ),
    "T형보": (
        ("bf", "플랜지 폭 bf [mm]", 600.0),
        ("bw", "복부 폭 bw [mm]", 300.0),
        ("hf", "플랜지 두께 hf [mm]", 120.0),
        ("h", "전체 높이 h [mm]", 600.0),
        ("d", "유효깊이 d [mm]", 510.0),
        ("d_t", "최외단 깊이 dt [mm] (빈칸=h-60)", None),
        ("as_tension", "인장철근 As [mm²]", 8 * 506.7),
    ),
}


class BeamAnalyzerApp:
    """입력, 해석 결과, Matplotlib 그래프를 한 창에 통합한다."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("RC Beam Analyzer · 철근콘크리트 보 해석")
        self.root.geometry("1440x900")
        self.root.minsize(1120, 720)
        self.root.configure(bg="#edf3f7")
        self._maximize_window()

        self.material_entries: dict[str, ttk.Entry] = {}
        self.section_entries: dict[str, ttk.Entry] = {}
        self.figure_canvas: FigureCanvasTkAgg | None = None
        self.toolbar: NavigationToolbar2Tk | None = None

        self._configure_style()
        self._build_layout()
        self.load_example("예제 4-2 (복근보, 압축철근 2-D22)")

    def _maximize_window(self) -> None:
        """제목 표시줄과 작업 표시줄을 유지한 채 시작 창을 최대화한다."""
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError:
                # 일부 창 관리자에서는 최대화 속성을 지원하지 않는다.
                pass

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Header.TLabel", font=("Malgun Gothic", 21, "bold"), foreground=COLORS["navy"], background="#edf3f7")
        style.configure("Sub.TLabel", font=("Malgun Gothic", 10), foreground="#4c6070", background="#edf3f7")
        style.configure("Card.TFrame", background="white", relief="flat")
        style.configure("Card.TLabel", background="white", foreground=COLORS["navy"], font=("Malgun Gothic", 10))
        style.configure("CardTitle.TLabel", background="white", foreground=COLORS["navy"], font=("Malgun Gothic", 12, "bold"))
        style.configure("Accent.TButton", font=("Malgun Gothic", 11, "bold"), padding=(12, 9))

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, padding=(24, 18, 24, 10))
        header.pack(fill="x")
        ttk.Label(header, text="RC Beam Analyzer", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="단근보 · 복근보 · T형보",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        left = ttk.Frame(body, style="Card.TFrame", padding=18, width=365)
        right = ttk.Panedwindow(body, orient="vertical")
        body.add(left, weight=0)
        body.add(right, weight=1)

        self._build_input_panel(left)

        self.plot_frame = ttk.Frame(right, style="Card.TFrame", padding=8)
        result_frame = ttk.Frame(right, style="Card.TFrame", padding=12)
        right.add(self.plot_frame, weight=3)
        right.add(result_frame, weight=2)

        ttk.Label(result_frame, text="계산 리포트", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 7))
        text_wrap = ttk.Frame(result_frame)
        text_wrap.pack(fill="both", expand=True)
        self.output = tk.Text(
            text_wrap,
            wrap="none",
            font=("Consolas", 10),
            bg="#0f1f2d",
            fg="#e9f2f7",
            insertbackground="white",
            relief="flat",
            padx=12,
            pady=10,
        )
        y_scroll = ttk.Scrollbar(text_wrap, orient="vertical", command=self.output.yview)
        x_scroll = ttk.Scrollbar(text_wrap, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.output.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        text_wrap.rowconfigure(0, weight=1)
        text_wrap.columnconfigure(0, weight=1)

    def _build_input_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="해석 설정", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Separator(parent).pack(fill="x", pady=10)

        ttk.Label(parent, text="교재 예제", style="Card.TLabel").pack(anchor="w")
        self.example_var = tk.StringVar(value=next(iter(TEXTBOOK_EXAMPLES)))
        examples = ttk.Combobox(parent, textvariable=self.example_var, state="readonly", values=list(TEXTBOOK_EXAMPLES), width=38)
        examples.pack(fill="x", pady=(3, 6))
        examples.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.load_example(self.example_var.get()),
        )

        ttk.Separator(parent).pack(fill="x", pady=13)
        ttk.Label(parent, text="보 형식", style="Card.TLabel").pack(anchor="w")
        self.beam_type_var = tk.StringVar(value="복근 직사각형보")
        beam_selector = ttk.Combobox(parent, textvariable=self.beam_type_var, state="readonly", values=list(FIELD_SETS), width=38)
        beam_selector.pack(fill="x", pady=(3, 6))
        beam_selector.bind("<<ComboboxSelected>>", lambda _event: self._rebuild_section_fields())

        self.section_fields_frame = ttk.Frame(parent, style="Card.TFrame")
        self.section_fields_frame.pack(fill="x", pady=(4, 0))

        ttk.Separator(parent).pack(fill="x", pady=13)
        ttk.Label(parent, text="재료", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 5))
        for key, label, default in (("fck", "fck [MPa] (≤ 40)", 21.0), ("fy", "fy [MPa]", 400.0)):
            row = ttk.Frame(parent, style="Card.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, style="Card.TLabel").pack(side="left")
            entry = ttk.Entry(row, width=12, justify="right")
            entry.insert(0, str(default))
            entry.pack(side="right")
            self.material_entries[key] = entry

        note = (
            "고정 기준\n"
            "일반 콘크리트 λ = 1.0\n"
            "εcu = 0.0033 · β1 = 0.8\n"
            "dt 미입력 시 h-60 mm\n"
            "φ = εt에 따라 0.65~0.85"
        )
        ttk.Label(parent, text=note, style="Card.TLabel", justify="left").pack(anchor="w", pady=(10, 12))
        ttk.Button(parent, text="분석 실행", style="Accent.TButton", command=self.run_analysis).pack(fill="x")
        self.status_var = tk.StringVar(value="입력 대기")
        ttk.Label(parent, textvariable=self.status_var, style="Card.TLabel", wraplength=320).pack(anchor="w", pady=(9, 0))
        self._rebuild_section_fields()

    def _rebuild_section_fields(self) -> None:
        for child in self.section_fields_frame.winfo_children():
            child.destroy()
        self.section_entries.clear()
        for key, label, default in FIELD_SETS[self.beam_type_var.get()]:
            row = ttk.Frame(self.section_fields_frame, style="Card.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, style="Card.TLabel").pack(side="left")
            entry = ttk.Entry(row, width=12, justify="right")
            if default is not None:
                entry.insert(0, f"{default:g}")
            entry.pack(side="right")
            self.section_entries[key] = entry

    def _set_entry(self, entry: ttk.Entry, value: float | None) -> None:
        entry.delete(0, "end")
        if value is not None:
            entry.insert(0, f"{value:g}")

    def load_example(self, name: str) -> None:
        beam = TEXTBOOK_EXAMPLES[name]()
        if isinstance(beam, DoublyReinforcedBeam):
            beam_type = "복근 직사각형보"
            values = {
                "b": beam.b,
                "h": beam.h,
                "d": beam.d,
                "d_t": beam.d_t,
                "d_prime": beam.d_prime,
                "as_tension": beam.as_tension,
                "as_compression": beam.as_compression,
            }
        elif isinstance(beam, TBeam):
            beam_type = "T형보"
            values = {
                "bf": beam.bf,
                "bw": beam.bw,
                "hf": beam.hf,
                "h": beam.h,
                "d": beam.d,
                "d_t": beam.d_t,
                "as_tension": beam.as_tension,
            }
        else:
            raise TypeError("지원하지 않는 예제 형식입니다.")

        self.beam_type_var.set(beam_type)
        self._rebuild_section_fields()
        for key, value in values.items():
            self._set_entry(self.section_entries[key], value)
        self._set_entry(self.material_entries["fck"], beam.material.fck)
        self._set_entry(self.material_entries["fy"], beam.material.fy)
        self.example_var.set(name)
        self.run_analysis(title=name)

    def _read_float(self, entry: ttk.Entry, label: str) -> float:
        try:
            return float(entry.get().replace(",", ""))
        except ValueError as error:
            raise ValueError(f"{label}에 숫자를 입력하세요.") from error

    def _build_beam(self) -> Beam:
        material = Material(
            fck=self._read_float(self.material_entries["fck"], "fck"),
            fy=self._read_float(self.material_entries["fy"], "fy"),
        )
        values: dict[str, float | None] = {}
        for key, entry in self.section_entries.items():
            if key == "d_t" and not entry.get().strip():
                values[key] = None
            else:
                values[key] = self._read_float(entry, key)
        beam_type = self.beam_type_var.get()
        if beam_type == "단근 직사각형보":
            return SinglyReinforcedBeam(material=material, **values)
        if beam_type == "복근 직사각형보":
            return DoublyReinforcedBeam(material=material, **values)
        if beam_type == "T형보":
            return TBeam(material=material, **values)
        raise ValueError("지원하지 않는 보 형식입니다.")

    def run_analysis(self, title: str | None = None) -> None:
        try:
            beam = self._build_beam()
            result = beam.analyze()
            report = format_result(beam, result, title)
        except (ValueError, TypeError) as error:
            self.status_var.set(f"입력 오류: {error}")
            messagebox.showerror("입력값 확인", str(error), parent=self.root)
            return

        print(report)
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", report)
        self.output.configure(state="disabled")
        self.status_var.set(
            f"{'적합' if result.valid else '부적합'} · φMn = {result.design_strength:,.2f} kN·m"
        )
        self._show_figure(beam, result)

    def _show_figure(self, beam: Beam, result) -> None:
        if self.figure_canvas is not None:
            self.figure_canvas.get_tk_widget().destroy()
        if self.toolbar is not None:
            self.toolbar.destroy()
        figure = create_analysis_figure(beam, result)
        self.figure_canvas = FigureCanvasTkAgg(figure, master=self.plot_frame)
        self.figure_canvas.draw()
        self.figure_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.figure_canvas, self.plot_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(fill="x")


def launch() -> None:
    root = tk.Tk()
    BeamAnalyzerApp(root)
    root.mainloop()

