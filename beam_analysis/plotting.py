"""Matplotlib 단면도와 철근비-휨강도 그래프."""

from __future__ import annotations

from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from matplotlib.ticker import FormatStrFormatter

from .models import AnalysisResult, Beam, DoublyReinforcedBeam, SinglyReinforcedBeam, TBeam


COLORS = {
    "navy": "#17324d",
    "blue": "#176b87",
    "cyan": "#64ccc5",
    "orange": "#ff9f1c",
    "red": "#d1495b",
    "concrete": "#dfe7ec",
    "steel": "#252a34",
    "grid": "#d8e1e8",
}


def configure_font() -> bool:
    """한글 글꼴이 있으면 적용하고, 없으면 영문 표기를 사용하도록 알린다."""
    candidates = ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR")
    for family in candidates:
        try:
            font_manager.findfont(family, fallback_to_default=False)
        except ValueError:
            continue
        import matplotlib

        matplotlib.rcParams["font.family"] = family
        matplotlib.rcParams["axes.unicode_minus"] = False
        return True
    return False


def _bar_positions(count: int, width: float, y: float) -> list[tuple[float, float]]:
    display_count = max(1, min(count, 8))
    if display_count == 1:
        return [(width / 2.0, y)]
    margin = width * 0.14
    spacing = (width - 2 * margin) / (display_count - 1)
    return [(margin + index * spacing, y) for index in range(display_count)]


def _draw_bars(axis, positions: list[tuple[float, float]], radius: float) -> None:
    for x, y in positions:
        axis.add_patch(Circle((x, y), radius, color=COLORS["steel"], zorder=4))


def draw_section(axis, beam: Beam, korean: bool) -> None:
    axis.set_aspect("equal")
    axis.axis("off")
    title = "철근콘크리트 단면" if korean else "RC section"
    axis.set_title(title, fontsize=11, fontweight="bold", color=COLORS["navy"], pad=8)

    if isinstance(beam, TBeam):
        web_left = (beam.bf - beam.bw) / 2.0
        axis.add_patch(
            Rectangle((0, 0), beam.bf, beam.hf, facecolor=COLORS["concrete"], edgecolor=COLORS["navy"], lw=1.6)
        )
        axis.add_patch(
            Rectangle((web_left, beam.hf), beam.bw, beam.h - beam.hf, facecolor=COLORS["concrete"], edgecolor=COLORS["navy"], lw=1.6)
        )
        y_steel = beam.d
        count = max(1, round(beam.as_tension / 500.0))
        local = _bar_positions(count, beam.bw, y_steel)
        _draw_bars(axis, [(web_left + x, y) for x, y in local], max(5.0, beam.bw * 0.025))
        if beam.as_compression:
            compression_count = max(1, round(beam.as_compression / 500.0))
            _draw_bars(
                axis, _bar_positions(compression_count, beam.bf, beam.d_prime),
                max(5.0, beam.bw * 0.025),
            )
        width = beam.bf
        width_label = f"bf = {beam.bf:,.2f} mm"
        axis.text(width / 2.0, beam.h * 1.10, f"b = bw = {beam.bw:,.2f} mm", ha="center", fontsize=8, color=COLORS["navy"])
        axis.annotate(
            f"hf = {beam.hf:,.2f} mm", (0, beam.hf / 2.0),
            xytext=(-width * 0.63, -beam.h * 0.075), ha="left", va="center",
            fontsize=8, color=COLORS["navy"],
            arrowprops={"arrowstyle": "-", "color": COLORS["navy"], "lw": 0.7},
        )
        footer_y = 1.23
    else:
        assert isinstance(beam, (SinglyReinforcedBeam, DoublyReinforcedBeam))
        width = beam.b
        width_label = f"b = {beam.b:,.2f} mm"
        axis.add_patch(
            Rectangle((0, 0), beam.b, beam.h, facecolor=COLORS["concrete"], edgecolor=COLORS["navy"], lw=1.6)
        )
        tension_count = max(1, round(beam.as_tension / 400.0))
        _draw_bars(axis, _bar_positions(tension_count, beam.b, beam.d), max(4.0, beam.b * 0.025))
        if isinstance(beam, DoublyReinforcedBeam):
            compression_count = max(1, round(beam.as_compression / 400.0))
            _draw_bars(axis, _bar_positions(compression_count, beam.b, beam.d_prime), max(4.0, beam.b * 0.025))
        footer_y = 1.11

    axis.text(width / 2.0, -beam.h * 0.07, width_label, ha="center", fontsize=8, color=COLORS["navy"])
    for x, depth, label, offset in (
        (-width * 0.34, beam.h, "h", -width * 0.12),
        (width * 1.22, beam.d, "d", width * 0.13),
    ):
        axis.annotate("", (x, 0), (x, depth), arrowprops={"arrowstyle": "<->", "color": COLORS["navy"], "lw": 0.8})
        axis.text(x + offset, depth / 2.0, f"{label} = {depth:,.2f} mm", rotation=90, ha="center", va="center", fontsize=8, color=COLORS["navy"])
    compression_area = getattr(beam, "as_compression", 0.0)
    compression_depth = f"{beam.d_prime:,.2f} mm" if compression_area else "—"
    footer = (
        f"d' = {compression_depth}",
        f"As = {beam.as_tension:,.2f} mm²",
        f"As' = {compression_area:,.2f} mm²",
    )
    for index, label in enumerate(footer):
        axis.text(width / 2.0, beam.h * (footer_y + index * 0.12), label, ha="center", fontsize=8, color=COLORS["navy"])
    axis.set_xlim(-width * 0.65, width * 1.55)
    axis.set_ylim(beam.h * (footer_y + 0.34), -beam.h * 0.17)


def create_section_figure(beam: Beam) -> Figure:
    """예제의 치수와 철근량을 표시하는 사이드바 단면도를 반환한다."""
    figure = Figure(figsize=(3.4, 2.8), dpi=100, facecolor="white")
    axis = figure.add_subplot(111)
    draw_section(axis, beam, configure_font())
    figure.subplots_adjust(left=0.03, right=0.97, top=0.88, bottom=0.02)
    return figure


def draw_bisection_curve(axis, beam: Beam, result: AnalysisResult, korean: bool) -> None:
    """이분법에 사용한 평형식과 반올림 전 순인장변형률의 근을 표시한다."""
    low = float(result.values["root_bracket_low"])
    high = float(result.values["root_bracket_high"])
    root_eps_t = float(result.values["root_eps_t"])
    parameters = {
        "bw": beam.reference_width,
        "as_compression": getattr(beam, "as_compression", 0.0),
        "d_prime": getattr(beam, "d_prime", 0.0),
    }
    if isinstance(beam, TBeam):
        parameters.update(bw=beam.bw, bf=beam.bf, hf=beam.hf)
    strains = [low + (high - low) * index / 240 for index in range(241)]
    residuals = [beam.axial_force_residual(value, **parameters) / 1000.0 for value in strains]
    axis.plot([value * 1000.0 for value in strains], residuals, color=COLORS["blue"], lw=2.0, label="P = Cc + Cs' - T")
    axis.axhline(0.0, color=COLORS["steel"], lw=1.0)
    axis.scatter(
        [low * 1000.0, high * 1000.0], [residuals[0], residuals[-1]],
        color=COLORS["orange"], s=35, zorder=4,
        label="초기 탐색 구간" if korean else "Initial bracket",
    )
    root_residual = float(result.values["root_residual_n"]) / 1000.0
    axis.axvline(root_eps_t * 1000.0, color=COLORS["red"], ls="--", lw=1.0)
    axis.scatter([root_eps_t * 1000.0], [root_residual], color=COLORS["red"], edgecolor="white", s=60, zorder=5)
    axis.annotate(
        f"εt = {root_eps_t:.2e}\nP = {root_residual:.2e} kN",
        (root_eps_t * 1000.0, root_residual),
        xytext=(0.96, 0.94), textcoords="axes fraction", ha="right", va="top",
        fontsize=9, fontweight="bold", color=COLORS["red"],
        arrowprops={"arrowstyle": "->", "color": COLORS["red"]},
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": COLORS["red"]},
    )
    axis.set_title("Bisection Method", fontsize=13, fontweight="bold", color=COLORS["navy"], pad=12)
    axis.set_xlabel(("순인장변형률 " if korean else "Tensile strain ") + r"$\varepsilon_t$ [$\times 10^{-3}$]")
    axis.set_ylabel("축력 잔차 P [kN]" if korean else "Axial force residual P [kN]")
    axis.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    axis.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    axis.tick_params(labelsize=8)
    axis.grid(True, color=COLORS["grid"], lw=0.8)
    axis.legend(loc="lower left", fontsize=8, frameon=False)


def draw_strength_curve(axis, beam: Beam, result: AnalysisResult, korean: bool) -> None:
    ratios, nominal, design = beam.strength_curve()
    graph_result = beam.analyze(use_textbook_rounding=False)
    axis.plot(ratios, nominal, color=COLORS["blue"], lw=2.2, label="공칭강도 Mn" if korean else "Nominal Mn")
    axis.plot(ratios, design, color=COLORS["orange"], lw=2.2, label="설계강도 φMn" if korean else "Design φMn")
    rho_min = float(
        graph_result.values.get("rho_graph_min", graph_result.values["rho_min"])
    ) * 100.0
    rho_max = float(
        graph_result.values.get("rho_graph_max", graph_result.values["rho_max"])
    ) * 100.0
    axis.axvspan(0, min(rho_min, 3.0), color=COLORS["red"], alpha=0.08)
    if rho_max < 3.0:
        axis.axvspan(rho_max, 3.0, color=COLORS["red"], alpha=0.08)
    axis.axvline(rho_min, color=COLORS["red"], ls="--", lw=1.2, label="철근비 한계" if korean else "Ratio limits")
    axis.axvline(rho_max, color=COLORS["red"], ls="--", lw=1.2)
    limit_label_style = {
        "textcoords": "offset points",
        "fontsize": 8.5,
        "fontweight": "bold",
        "color": COLORS["red"],
        "bbox": {"boxstyle": "round,pad=0.25", "fc": "white", "ec": COLORS["red"], "alpha": 0.9},
    }
    axis.annotate(
        ("최소 " if korean else "Min ") + f"ρ = {rho_min:.3f}%",
        (rho_min, 0.98),
        xycoords=axis.get_xaxis_transform(),
        xytext=(6, 0),
        ha="left",
        va="top",
        **limit_label_style,
    )
    axis.annotate(
        ("최대 " if korean else "Max ") + f"ρ = {rho_max:.3f}%",
        (rho_max, 0.98),
        xycoords=axis.get_xaxis_transform(),
        xytext=(-6, 0),
        ha="right",
        va="top",
        **limit_label_style,
    )
    current_rho = beam.reinforcement_ratio() * 100.0
    axis.scatter(
        [current_rho],
        [graph_result.design_strength],
        s=68,
        color=COLORS["red"],
        edgecolor="white",
        linewidth=0.8,
        zorder=5,
    )
    annotation_offset = (-78, 12) if current_rho > 2.4 else (10, 12)
    axis.annotate(
        f"ρ={current_rho:.3f}%\nφMn={result.design_strength:.1f}",
        (current_rho, graph_result.design_strength),
        xytext=annotation_offset,
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        color=COLORS["red"],
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": COLORS["red"], "alpha": 0.9},
    )
    axis.set_xlim(0, 3)
    axis.set_ylim(bottom=0)
    axis.set_xlabel("인장철근비 As/(bd) [%]" if korean else "Tension steel ratio As/(bd) [%]")
    axis.set_ylabel("휨강도 [kN·m]" if korean else "Flexural strength [kN·m]")
    axis.set_title(
        "철근비 0~3%에 따른 휨강도" if korean else "Flexural strength for 0–3% steel ratio",
        fontsize=13,
        fontweight="bold",
        color=COLORS["navy"],
        pad=12,
    )
    axis.grid(True, color=COLORS["grid"], lw=0.8)
    axis.legend(loc="lower center", frameon=False, ncol=1)


def create_analysis_figure(beam: Beam, result: AnalysisResult | None = None) -> Figure:
    """이분법 평형 그래프와 기존 강도곡선을 포함한 Figure를 반환한다."""
    korean = configure_font()
    analysis = result or beam.analyze()
    figure = Figure(figsize=(11.5, 5.5), dpi=100, facecolor="#f7fafc")
    grid = figure.add_gridspec(1, 2, width_ratios=(1.0, 1.65), wspace=0.32)
    bisection_axis = figure.add_subplot(grid[0, 0])
    curve_axis = figure.add_subplot(grid[0, 1])
    draw_bisection_curve(bisection_axis, beam, analysis, korean)
    draw_strength_curve(curve_axis, beam, analysis, korean)
    figure.subplots_adjust(left=0.085, right=0.975, top=0.90, bottom=0.14)
    return figure

