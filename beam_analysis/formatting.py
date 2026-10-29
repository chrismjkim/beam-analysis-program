"""터미널과 GUI에서 공유하는 결과 포매팅."""

from __future__ import annotations

from unicodedata import east_asian_width

from .models import AnalysisResult, Beam, Material


def _display_width(text: str) -> int:
    return sum(2 if east_asian_width(character) in {"W", "F"} else 1 for character in text)


def _pad(text: str, width: int, align: str = "left") -> str:
    padding = max(0, width - _display_width(text))
    if align == "center":
        left = padding // 2
        return " " * left + text + " " * (padding - left)
    return text + " " * padding


def _wrap_display(text: str, width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    current_width = 0
    for character in text:
        char_width = 2 if east_asian_width(character) in {"W", "F"} else 1
        if current and current_width + char_width > width:
            lines.append(current)
            current = character
            current_width = char_width
        else:
            current += character
            current_width += char_width
    lines.append(current)
    return lines


def _rows(label: str, value: str, width: int = 88) -> list[str]:
    label_width = 23
    value_width = width - 2 - label_width - 1
    wrapped = _wrap_display(value, value_width)
    rows: list[str] = []
    for index, part in enumerate(wrapped):
        row_label = label if index == 0 else ""
        content = f"  {_pad(row_label, label_width)} {_pad(part, value_width)}"
        rows.append(f"│{content}│")
    return rows


def format_result(beam: Beam, result: AnalysisResult, title: str | None = None) -> str:
    """계산 근거와 판정이 보이는 고정폭 보고서를 만든다."""
    width = 88
    heading = title or result.beam_type
    lines = [
        "┌" + "─" * width + "┐",
        f"│{_pad('RC BEAM ANALYZER · ' + heading, width, 'center')}│",
        "├" + "─" * width + "┤",
    ]
    if result.values.get("root_method") == "bisect":
        lines.extend(_rows("해석 방법", "Root Finding · Bisection Method(이분법)", width))
        convergence = "수렴" if result.values.get("root_converged") else "미수렴"
        lines.extend(
            _rows(
                "평형해 수렴",
                f"{convergence} · {float(result.values['root_iterations']):.0f}회 반복 · "
                f"|P| = {abs(float(result.values['root_residual_n'])):.2e} N",
                width,
            )
        )
    lines.extend(_rows("해석 모델", result.beam_type, width))
    lines.extend(_rows("판정", "적합" if result.valid else "부적합 — 강도 0 처리", width))
    lines.extend(_rows("공칭휨강도 Mn", f"{result.nominal_strength:,.3f} kN·m", width))
    lines.extend(_rows("설계휨강도 φMn", f"{result.design_strength:,.3f} kN·m", width))
    lines.extend(_rows("순인장변형률 εt", f"{float(result.values['eps_t']):.6f}", width))
    lines.extend(
        _rows(
            "강도감소계수 φ",
            f"{float(result.values['phi']):.3f} ({result.values['strain_region']})",
            width,
        )
    )
    lines.append("├" + "─" * width + "┤")
    lines.extend(_rows("인장철근비 ρ", f"{float(result.values['rho']) * 100:.4f} %", width))
    if "rho_effective" in result.values:
        lines.extend(_rows("유효철근비 ρ-ρ'", f"{float(result.values['rho_effective']) * 100:.4f} %", width))
        lines.extend(_rows("유효 ρmin", f"{float(result.values['rho_min']) * 100:.4f} %", width))
        lines.extend(_rows("유효 ρmax", f"{float(result.values['rho_max']) * 100:.4f} %", width))
    else:
        lines.extend(_rows("최소철근비 ρmin", f"{float(result.values['rho_min']) * 100:.4f} %", width))
        lines.extend(_rows("최대철근비 ρmax", f"{float(result.values['rho_max']) * 100:.4f} %", width))
    if result.violations:
        lines.append("├" + "─" * width + "┤")
        for violation in result.violations:
            lines.extend(_rows("한계 위반", violation, width))

    lines.append("├" + "─" * width + "┤")
    lines.extend(_rows("계산 과정", "", width))
    for index, step in enumerate(result.steps, start=1):
        lines.extend(_rows(f"{index:02d}", step, width))
    lines.append("├" + "─" * width + "┤")
    lines.extend(
        _rows(
            "재료/계수",
            (
                f"fck={beam.material.fck:g} MPa, fy={beam.material.fy:g} MPa, "
                f"εcu={beam.material.eps_cu:g}, β1={beam.material.beta1:g}"
            ),
            width,
        )
    )
    lines.append("└" + "─" * width + "┘")
    return "\n".join(lines)


def format_material(material: Material) -> str:
    return (
        f"fck={material.fck:g} MPa | fy={material.fy:g} MPa | "
        f"Es={material.es:,.0f} MPa | εcu={material.eps_cu:g} | "
        f"β1={material.beta1:g} | φ={material.phi_min:g}~{material.phi:g}"
    )

