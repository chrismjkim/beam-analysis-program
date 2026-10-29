"""철근콘크리트 보의 휨강도 계산 모델.

계산 기준
---------
* 등가직사각형 응력블록과 변형률 적합조건
* 일반 콘크리트(lambda = 1.0)
* epsilon_cu = 0.0033
* f_ck <= 40 MPa에서 beta_1 = 0.8
* 순인장변형률에 따른 강도감소계수 phi = 0.65~0.85

모든 길이와 면적은 mm, mm², 응력은 MPa, 모멘트는 kN·m 단위이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from math import isfinite, sqrt
from typing import Iterable

from scipy.optimize import root_scalar


@dataclass(frozen=True, slots=True)
class Material:
    """일반 콘크리트와 철근의 재료 정수."""

    fck: float = 21.0
    fy: float = 400.0
    es: float = 200_000.0
    phi: float = 0.85
    phi_min: float = 0.65
    eps_cu: float = 0.0033
    beta1: float = 0.8
    lambda_: float = 1.0
    eps_t_tension_limit: float = 0.005

    def __post_init__(self) -> None:
        if not 0 < self.fck <= 40:
            raise ValueError("이 프로그램은 0 < fck <= 40 MPa인 일반 콘크리트만 지원합니다.")
        if self.fy <= 0 or self.es <= 0:
            raise ValueError("fy와 Es는 0보다 커야 합니다.")
        if not 0 < self.phi_min <= self.phi <= 1:
            raise ValueError("phi의 범위는 0 < phi_min <= phi <= 1이어야 합니다.")
        if self.eps_cu <= 0 or self.beta1 <= 0 or self.eps_t_tension_limit <= 0:
            raise ValueError("epsilon_cu, beta1, 인장지배 한계변형률은 0보다 커야 합니다.")

    @property
    def eps_y(self) -> float:
        return self.fy / self.es

    @property
    def eps_t_min(self) -> float:
        return max(0.004, 2.0 * self.eps_y)

    def strength_reduction_factor(
        self, eps_t: float, *, use_textbook_rounding: bool = True
    ) -> tuple[float, str]:
        """순인장변형률에 따른 phi와 단면의 변형률 구간을 반환한다."""
        if eps_t <= self.eps_y:
            return self.phi_min, "압축지배단면"
        if eps_t >= self.eps_t_tension_limit:
            return self.phi, "인장지배단면"
        transition = (eps_t - self.eps_y) / (
            self.eps_t_tension_limit - self.eps_y
        )
        phi = self.phi_min + (self.phi - self.phi_min) * transition
        return (round(phi, 3) if use_textbook_rounding else phi), "변화구간단면"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """해석 결과와 터미널·GUI 출력에 필요한 중간 계산값."""

    beam_type: str
    nominal_strength: float
    design_strength: float
    raw_nominal_strength: float
    raw_design_strength: float
    valid: bool
    violations: tuple[str, ...]
    values: dict[str, float | str | bool]
    steps: tuple[str, ...]


class Beam(ABC):
    """보 해석 모델의 공통 인터페이스."""

    material: Material
    h: float
    d: float
    d_t: float | None
    as_tension: float

    @abstractmethod
    def analyze(self, *, use_textbook_rounding: bool = True) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def with_tension_area(self, as_tension: float) -> "Beam":
        raise NotImplementedError

    @abstractmethod
    def reinforcement_ratio(self) -> float:
        raise NotImplementedError

    def strength_curve(
        self, start: float = 0.0, stop: float = 0.03, points: int = 151
    ) -> tuple[list[float], list[float], list[float]]:
        """인장철근비 변화에 따른 제한 적용 후 Mn, phiMn 곡선을 반환한다."""
        if points < 2:
            raise ValueError("그래프 점의 개수는 2 이상이어야 합니다.")
        ratios: list[float] = []
        nominal: list[float] = []
        design: list[float] = []
        reference_area = self.reference_width * self.d
        for index in range(points):
            rho = start + (stop - start) * index / (points - 1)
            result = self.with_tension_area(rho * reference_area).analyze(
                use_textbook_rounding=False
            )
            ratios.append(rho * 100.0)
            nominal.append(result.nominal_strength)
            design.append(result.design_strength)
        return ratios, nominal, design

    @property
    @abstractmethod
    def reference_width(self) -> float:
        raise NotImplementedError

    @staticmethod
    def _validate_positive(items: Iterable[tuple[str, float]]) -> None:
        invalid = [name for name, value in items if value <= 0]
        if invalid:
            raise ValueError(f"0보다 커야 하는 값: {', '.join(invalid)}")

    def _rectangular_rho_min(self) -> float:
        """일반 콘크리트의 최소철근비."""
        material = self.material
        root_term = 1.0 - 0.432 * material.lambda_ / sqrt(material.fck)
        return (
            0.85
            * material.fck
            / material.fy
            * (1.0 - sqrt(max(0.0, root_term)))
        )

    def _rectangular_rho_max(self, dt: float | None = None) -> float:
        """최외단 인장철근의 최소 허용변형률에서 구한 최대철근비."""
        material = self.material
        dt_value = self.d if dt is None else dt
        c_over_d = (
            material.eps_cu
            / (material.eps_cu + material.eps_t_min)
            * dt_value
            / self.d
        )
        return (
            0.85
            * material.fck
            * material.beta1
            / material.fy
            * c_over_d
        )

    @property
    def tension_steel_depth(self) -> float:
        """직접 입력한 d_t 또는 과제 기본값 h-60 mm를 반환한다."""
        return self.h - 60.0 if self.d_t is None else self.d_t

    def _validate_tension_depth(self) -> None:
        if not 0 < self.tension_steel_depth < self.h:
            raise ValueError("최외단 인장철근 깊이 d_t는 0 < d_t < h여야 합니다.")

    def axial_force_residual(
        self, eps_t: float, *, bw: float, bf: float | None = None,
        hf: float = 0.0, as_tension: float | None = None,
        as_compression: float = 0.0, d_prime: float = 0.0,
    ) -> float:
        """주어진 순인장변형률에서 압축력과 인장력의 차이를 N으로 반환한다."""
        material = self.material
        area = self.as_tension if as_tension is None else as_tension
        flange_width = bw if bf is None else bf
        c = material.eps_cu * self.tension_steel_depth / (material.eps_cu + eps_t)
        a = material.beta1 * c
        concrete_area = bw * a + (flange_width - bw) * min(a, hf)
        eps_prime = material.eps_cu * (c - d_prime) / c
        fs_prime = max(-material.fy, min(material.fy, material.es * eps_prime))
        return (0.85 * material.fck * concrete_area
                + as_compression * fs_prime - area * material.fy)

    def _root_equilibrium(
        self, *, bw: float, bf: float | None = None, hf: float = 0.0,
        as_tension: float | None = None, as_compression: float = 0.0,
        d_prime: float = 0.0,
    ) -> dict[str, float | str | bool]:
        """세 보 형식의 축력 평형을 순인장변형률에 대한 이분법으로 푼다."""
        material = self.material
        area = self.as_tension if as_tension is None else as_tension

        def axial_force(eps_t: float) -> float:
            return self.axial_force_residual(
                eps_t, bw=bw, bf=bf, hf=hf, as_tension=as_tension,
                as_compression=as_compression, d_prime=d_prime,
            )

        high_c = max(self.h, self.d, self.tension_steel_depth)
        low_eps = material.eps_cu * (self.tension_steel_depth / high_c - 1.0)
        while axial_force(low_eps) < 0:
            high_c *= 2.0
            if high_c > self.h * 1.0e6:
                raise ValueError("중립축을 찾을 수 없습니다. 입력값을 확인하세요.")
            low_eps = material.eps_cu * (self.tension_steel_depth / high_c - 1.0)
        high_eps = max(0.01, material.eps_cu)
        for _ in range(128):
            if axial_force(high_eps) <= 0:
                break
            high_eps *= 2.0
        else:
            raise ValueError("순인장변형률의 근 탐색 구간을 찾을 수 없습니다.")
        solution = root_scalar(
            axial_force, method="bisect", bracket=(low_eps, high_eps),
            xtol=1.0e-15, rtol=1.0e-14, maxiter=200,
        )
        if not solution.converged:
            raise ValueError("축력 평형의 이분법 계산이 수렴하지 않았습니다.")
        eps_t = float(solution.root)
        c = material.eps_cu * self.tension_steel_depth / (material.eps_cu + eps_t)
        residual = axial_force(eps_t)
        if not isfinite(c) or abs(residual) > max(1.0e-5, area * material.fy * 1.0e-10):
            raise ValueError("축력 평형의 수치 오차가 허용치를 초과했습니다.")
        iterations = 0 if eps_t in (low_eps, high_eps) else solution.iterations
        return {
            "root_method": "bisect", "root_converged": True,
            "root_iterations": float(iterations), "root_residual_n": residual,
            "root_c_mm": c, "root_a_mm": material.beta1 * c, "root_eps_t": eps_t,
            "root_bracket_low": low_eps, "root_bracket_high": high_eps,
        }

    @staticmethod
    def _root_steps(solution: dict[str, float | str | bool]) -> tuple[str, ...]:
        return (
            "Root Finding: scipy.optimize.root_scalar(method='bisect')",
            "축력 평형식: P(epsilon_t) = C_c + C_s' - T = 0",
            f"반올림 전 평형해: epsilon_t = {float(solution['root_eps_t']):.6f}",
            (f"이분법 수렴: {float(solution['root_iterations']):.0f}회, "
             f"축력 잔차 = {float(solution['root_residual_n']):.3e} N"),
        )

    def _tension_strain_and_phi(
        self, c: float, *, use_textbook_rounding: bool = True
    ) -> tuple[float, float, str]:
        """중립축 c에서 최외단 인장철근의 순인장변형률과 phi를 계산한다."""
        if c <= 0:
            raise ValueError("중립축 깊이 c는 0보다 커야 합니다.")
        eps_t = self.material.eps_cu * (self.tension_steel_depth - c) / c
        phi, strain_region = self.material.strength_reduction_factor(
            eps_t, use_textbook_rounding=use_textbook_rounding
        )
        return eps_t, phi, strain_region

    def _strength_reduction_steps(
        self,
        c: float,
        eps_t: float,
        phi: float,
        strain_region: str,
        *,
        use_textbook_rounding: bool = True,
    ) -> tuple[str, ...]:
        """계산 리포트에 공통으로 사용하는 변형률 및 phi 검토 과정을 만든다."""
        material = self.material
        steps = [
            (
                f"d_t = h-60 = {self.h:.2f}-60 = {self.tension_steel_depth:.2f} mm"
                if self.d_t is None
                else f"d_t = {self.tension_steel_depth:.2f} mm (직접 입력)"
            ),
            "epsilon_t = epsilon_cu(d_t-c)/c",
            (
                f"epsilon_t = {material.eps_cu:.4f}"
                f"({self.tension_steel_depth:.2f}-{c:.2f})/{c:.2f} = {eps_t:.6f}"
            ),
        ]
        if strain_region == "인장지배단면":
            steps.append(
                f"epsilon_t 비교: {eps_t:.6f} >= "
                f"{material.eps_t_tension_limit:.3f}"
            )
            steps.append(f"판정 = {strain_region}")
            steps.append(f"phi = {phi:.3f}")
        elif strain_region == "압축지배단면":
            steps.append(
                f"epsilon_t 비교: {eps_t:.6f} <= epsilon_y = "
                f"{material.eps_y:.6f} < {material.eps_t_tension_limit:.3f}"
            )
            steps.append(f"판정 = {strain_region}")
            steps.append(f"phi = {phi:.3f}")
        else:
            steps.append(
                f"epsilon_t 비교: epsilon_y = {material.eps_y:.6f} < "
                f"{eps_t:.6f} < {material.eps_t_tension_limit:.3f}"
            )
            steps.append(f"판정 = {strain_region}")
            steps.append(
                "변화구간 공식: phi = 0.65 + 0.20R"
            )
            steps.append("R = (epsilon_t-epsilon_y)/(0.005-epsilon_y)")
            steps.append(
                f"phi = 0.65 + 0.20({eps_t:.6f}-{material.eps_y:.6f})/"
                f"(0.005-{material.eps_y:.6f}) = {phi:.3f}"
            )
        return tuple(steps)


@dataclass(frozen=True, slots=True)
class SinglyReinforcedBeam(Beam):
    """단근 직사각형보."""

    b: float
    h: float
    d: float
    as_tension: float
    material: Material = Material()
    d_t: float | None = None

    def __post_init__(self) -> None:
        self._validate_positive(
            (("b", self.b), ("h", self.h), ("d", self.d), ("As", self.as_tension))
        )
        if self.d >= self.h:
            raise ValueError("유효깊이 d는 전체 높이 h보다 작아야 합니다.")
        self._validate_tension_depth()

    @property
    def reference_width(self) -> float:
        return self.b

    def reinforcement_ratio(self) -> float:
        return self.as_tension / (self.b * self.d)

    def with_tension_area(self, as_tension: float) -> "SinglyReinforcedBeam":
        # 그래프의 0% 지점을 허용하기 위해 아주 작은 양수로 계산한다.
        return replace(self, as_tension=max(as_tension, 1.0e-9))

    def analyze(self, *, use_textbook_rounding: bool = True) -> AnalysisResult:
        material = self.material
        rho = self.reinforcement_ratio()
        rho_min = self._rectangular_rho_min()
        rho_max = self._rectangular_rho_max(self.tension_steel_depth)
        equilibrium = self._root_equilibrium(bw=self.b)
        a = float(equilibrium["root_a_mm"])
        c = float(equilibrium["root_c_mm"])
        eps_t, phi, strain_region = self._tension_strain_and_phi(
            c, use_textbook_rounding=use_textbook_rounding
        )
        raw_mn = self.as_tension * material.fy * (self.d - a / 2.0) * 1.0e-6
        raw_mn = max(0.0, raw_mn)

        violations: list[str] = []
        if rho < rho_min:
            violations.append("최소철근비 미달")
        if rho > rho_max:
            violations.append("최대철근비 초과")
        valid = not violations
        mn = raw_mn if valid else 0.0
        raw_phi_mn = phi * raw_mn
        phi_mn = raw_phi_mn if valid else 0.0

        values: dict[str, float | str | bool] = {
            "rho": rho,
            "rho_min": rho_min,
            "rho_max": rho_max,
            "a_mm": a,
            "c_mm": c,
            "d_t_mm": self.tension_steel_depth,
            "eps_t": eps_t,
            "phi": phi,
            "strain_region": strain_region,
        }
        values.update(equilibrium)
        steps = [
            *self._root_steps(equilibrium),
            f"rho = As/(bd) = {rho:.6f} ({rho * 100:.3f}%)",
            f"a = As*fy/(0.85*fck*b) = {a:.3f} mm",
            f"c = a/beta1 = {c:.3f} mm",
            f"Mn = As*fy*(d-a/2) = {raw_mn:.3f} kN·m",
        ]
        steps.extend(
            self._strength_reduction_steps(
                c,
                eps_t,
                phi,
                strain_region,
                use_textbook_rounding=use_textbook_rounding,
            )
        )
        steps.append(f"phi*Mn = {phi:.3f}*Mn = {raw_phi_mn:.3f} kN·m")
        return AnalysisResult(
            "단근 직사각형보",
            mn,
            phi_mn,
            raw_mn,
            raw_phi_mn,
            valid,
            tuple(violations),
            values,
            tuple(steps),
        )


@dataclass(frozen=True, slots=True)
class DoublyReinforcedBeam(Beam):
    """복근 직사각형보.

    압축철근 응력은 변형률 적합조건으로 계산하고 ±fy에서 제한한다. 따라서
    압축철근의 항복·비항복 상태를 하나의 평형식으로 안정적으로 처리한다.
    """

    b: float
    h: float
    d: float
    d_prime: float
    as_tension: float
    as_compression: float
    material: Material = Material()
    d_t: float | None = None

    def __post_init__(self) -> None:
        self._validate_positive(
            (
                ("b", self.b),
                ("h", self.h),
                ("d", self.d),
                ("d'", self.d_prime),
                ("As", self.as_tension),
                ("As'", self.as_compression),
            )
        )
        if not self.d_prime < self.d < self.h:
            raise ValueError("d' < d < h 조건을 만족해야 합니다.")
        self._validate_tension_depth()

    @property
    def reference_width(self) -> float:
        return self.b

    def reinforcement_ratio(self) -> float:
        return self.as_tension / (self.b * self.d)

    def effective_reinforcement_ratio(self) -> float:
        return (self.as_tension - self.as_compression) / (self.b * self.d)

    def with_tension_area(self, as_tension: float) -> "DoublyReinforcedBeam":
        return replace(self, as_tension=max(as_tension, 1.0e-9))

    def _steel_stress(self, c: float) -> tuple[float, float]:
        material = self.material
        eps_s = material.eps_cu * (c - self.d_prime) / c
        fs = max(-material.fy, min(material.fy, material.es * eps_s))
        return eps_s, fs

    def _neutral_axis(self) -> float:
        return float(self._equilibrium_solution()["root_c_mm"])

    def _equilibrium_solution(self) -> dict[str, float | str | bool]:
        return self._root_equilibrium(
            bw=self.b, as_compression=self.as_compression, d_prime=self.d_prime,
        )

    def analyze(self, *, use_textbook_rounding: bool = True) -> AnalysisResult:
        material = self.material
        rho = self.reinforcement_ratio()
        rho_compression = self.as_compression / (self.b * self.d)
        rho_effective = self.effective_reinforcement_ratio()
        rho_min = self._rectangular_rho_min()
        rho_max = self._rectangular_rho_max(self.tension_steel_depth)

        # 압축철근의 항복을 먼저 가정한 a를 검토용으로 계산한다.
        a_assumed_yield = (
            (self.as_tension - self.as_compression)
            * material.fy
            / (0.85 * material.fck * self.b)
        )
        yield_denominator = 1.0 - material.fy / (material.es * material.eps_cu)
        a_yield_limit = (
            material.beta1 * self.d_prime / yield_denominator
            if yield_denominator > 0
            else float("inf")
        )

        equilibrium = self._equilibrium_solution()
        c = float(equilibrium["root_c_mm"])
        a = material.beta1 * c
        eps_t, phi, strain_region = self._tension_strain_and_phi(
            c, use_textbook_rounding=use_textbook_rounding
        )
        eps_s_prime, fs_prime = self._steel_stress(c)
        compression_yielded = abs(fs_prime - material.fy) < 1.0e-6

        if compression_yielded:
            a_for_strength = a
            eps_s_for_strength = eps_s_prime
            fs_for_strength = fs_prime
        else:
            c_for_strength = round(c, 1) if use_textbook_rounding else c
            a_for_strength = material.beta1 * c_for_strength
            exact_eps_s_for_strength = (
                material.eps_cu
                * (c_for_strength - self.d_prime)
                / c_for_strength
            )
            eps_s_for_strength = (
                round(exact_eps_s_for_strength, 5)
                if use_textbook_rounding
                else exact_eps_s_for_strength
            )
            fs_for_strength = min(material.fy, material.es * eps_s_for_strength)

        cc = 0.85 * material.fck * a_for_strength * self.b
        cs = fs_for_strength * self.as_compression
        raw_mn = (
            cc * (self.d - a_for_strength / 2.0)
            + cs * (self.d - self.d_prime)
        ) * 1.0e-6
        raw_mn = max(0.0, raw_mn)

        violations: list[str] = []
        if rho_effective < rho_min:
            violations.append("유효철근비의 최소철근비 미달")
        if rho_effective > rho_max:
            violations.append("유효철근비의 최대철근비 초과")
        valid = not violations
        mn = raw_mn if valid else 0.0
        raw_phi_mn = phi * raw_mn
        phi_mn = raw_phi_mn if valid else 0.0

        values: dict[str, float | str | bool] = {
            "rho": rho,
            "rho_compression": rho_compression,
            "rho_effective": rho_effective,
            "rho_min": rho_min,
            "rho_max": rho_max,
            "rho_graph_min": rho_min + rho_compression,
            "rho_graph_max": rho_max + rho_compression,
            "a_assumed_yield_mm": a_assumed_yield,
            "a_yield_limit_mm": a_yield_limit,
            "a_mm": a,
            "c_mm": c,
            "d_t_mm": self.tension_steel_depth,
            "eps_t": eps_t,
            "phi": phi,
            "strain_region": strain_region,
            "eps_s_prime": eps_s_prime,
            "fs_prime_mpa": fs_prime,
            "a_for_strength_mm": a_for_strength,
            "eps_s_for_strength": eps_s_for_strength,
            "fs_for_strength_mpa": fs_for_strength,
            "cc_kn": cc * 1.0e-3,
            "cs_kn": cs * 1.0e-3,
            "compression_steel_yielded": compression_yielded,
        }
        values.update(equilibrium)
        steps_list = [
            *self._root_steps(equilibrium),
            f"ρ = A_s/(bd) = {rho:.6f} ({rho * 100:.3f}%)",
            f"ρ-ρ' = {rho_effective:.6f} ({rho_effective * 100:.3f}%)",
            "압축철근이 항복한다고 가정",
            "a = (A_s-A_s')f_y/(0.85f_ck b)",
            f"a = {a_assumed_yield:.2f} mm",
            (
                "항복 한계 = beta1 d'/(1-f_y/(E_s epsilon_cu)) "
                f"= {a_yield_limit:.2f} mm"
            ),
        ]

        if compression_yielded:
            steps_list.extend(
                [
                    (
                        f"항복 검토: a = {a_assumed_yield:.2f} mm >= "
                        f"{a_yield_limit:.2f} mm -> 압축철근 항복"
                    ),
                    f"c = a / beta1 = {c:.2f} mm",
                ]
            )
        else:
            quadratic_a = 0.85 * material.fck * self.b
            quadratic_b = (
                material.es * material.eps_cu * self.as_compression
                - self.as_tension * material.fy
            )
            quadratic_c = -(
                material.es
                * material.eps_cu
                * self.as_compression
                * material.beta1
                * self.d_prime
            )
            discriminant = quadratic_b**2 - 4.0 * quadratic_a * quadratic_c
            quadratic_root = (-quadratic_b + sqrt(discriminant)) / (2.0 * quadratic_a)
            values.update(
                {
                    "quadratic_a": quadratic_a,
                    "quadratic_b": quadratic_b,
                    "quadratic_c": quadratic_c,
                    "quadratic_root_mm": quadratic_root,
                }
            )
            steps_list.extend(
                [
                    (
                        f"항복 검토: a = {a_assumed_yield:.2f} mm < "
                        f"{a_yield_limit:.2f} mm -> 압축철근 비항복, a 재계산"
                    ),
                    (
                        "비항복 이차방정식(검산): (0.85f_ck b)a² "
                        "+ (E_s ε_cu A_s' - A_s f_y)a "
                        "- E_s ε_cu A_s' beta1 d' = 0"
                    ),
                    (
                        f"수치 대입: {quadratic_a:,.2f}a² "
                        f"{'+' if quadratic_b >= 0 else '-'} {abs(quadratic_b):,.2f}a "
                        f"{'+' if quadratic_c >= 0 else '-'} {abs(quadratic_c):,.2f} = 0"
                    ),
                    f"a = {a:.2f} mm",
                    f"c = a / beta1 = {c:.2f} mm",
                ]
            )

        steps_list.extend(
            [
                (
                    f"{'중간값 반올림' if use_textbook_rounding else '정밀 계산'}: "
                    f"ε'_s = {eps_s_for_strength:.6f}, "
                    f"f'_s = {fs_for_strength:.2f} MPa"
                    if not compression_yielded
                    else f"ε'_s = {eps_s_prime:.6f}, f'_s = {fs_prime:.2f} MPa"
                ),
                f"C_c = {cc * 1.0e-3:.2f} kN, C_s' = {cs * 1.0e-3:.2f} kN",
                f"M_n = C_c(d-a/2)+C_s'(d-d') = {raw_mn:.3f} kN·m",
            ]
        )
        steps_list.extend(
            self._strength_reduction_steps(
                c,
                eps_t,
                phi,
                strain_region,
                use_textbook_rounding=use_textbook_rounding,
            )
        )
        steps_list.append(f"phi*M_n = {phi:.3f}*M_n = {raw_phi_mn:.3f} kN·m")
        steps = tuple(steps_list)
        return AnalysisResult(
            "복근 직사각형보",
            mn,
            phi_mn,
            raw_mn,
            raw_phi_mn,
            valid,
            tuple(violations),
            values,
            steps,
        )


@dataclass(frozen=True, slots=True)
class TBeam(Beam):
    """플랜지와 복부를 가진 T형보."""

    bf: float
    bw: float
    hf: float
    h: float
    d: float
    as_tension: float
    material: Material = Material()
    d_t: float | None = None
    as_compression: float = 0.0
    d_prime: float = 60.0

    def __post_init__(self) -> None:
        self._validate_positive(
            (
                ("bf", self.bf),
                ("bw", self.bw),
                ("hf", self.hf),
                ("h", self.h),
                ("d", self.d),
                ("As", self.as_tension),
            )
        )
        if self.bw > self.bf:
            raise ValueError("복부 폭 bw는 플랜지 폭 bf보다 클 수 없습니다.")
        if not self.hf < self.d < self.h:
            raise ValueError("hf < d < h 조건을 만족해야 합니다.")
        if self.as_compression < 0 or not isfinite(self.as_compression):
            raise ValueError("압축철근량 As'는 유한한 0 이상의 값이어야 합니다.")
        if self.as_compression and not 0 < self.d_prime < self.d:
            raise ValueError("압축철근이 있으면 0 < d' < d여야 합니다.")
        self._validate_tension_depth()

    @property
    def reference_width(self) -> float:
        return self.bw

    def reinforcement_ratio(self) -> float:
        return self.as_tension / (self.bw * self.d)

    def with_tension_area(self, as_tension: float) -> "TBeam":
        return replace(self, as_tension=max(as_tension, 1.0e-9))

    def gross_section_properties(self) -> tuple[float, float, float]:
        """비균열 T단면의 도심 ybar, Ig, 인장측 거리 yt를 구한다."""
        flange_area = self.bf * self.hf
        web_height = self.h - self.hf
        web_area = self.bw * web_height
        flange_y = self.hf / 2.0
        web_y = self.hf + web_height / 2.0
        total_area = flange_area + web_area
        y_bar = (flange_area * flange_y + web_area * web_y) / total_area
        i_flange = self.bf * self.hf**3 / 12.0 + flange_area * (y_bar - flange_y) ** 2
        i_web = self.bw * web_height**3 / 12.0 + web_area * (web_y - y_bar) ** 2
        i_g = i_flange + i_web
        y_t = self.h - y_bar
        return y_bar, i_g, y_t

    def cracking_moment(self) -> float:
        _, i_g, y_t = self.gross_section_properties()
        rupture_modulus = 0.63 * self.material.lambda_ * sqrt(self.material.fck)
        return rupture_modulus * i_g / y_t * 1.0e-6

    def _equilibrium_solution(self, as_tension: float) -> dict[str, float | str | bool]:
        return self._root_equilibrium(
            bw=self.bw, bf=self.bf, hf=self.hf, as_tension=as_tension,
            as_compression=self.as_compression, d_prime=self.d_prime,
        )

    def _compression_stress(self, c: float) -> tuple[float, float]:
        if not self.as_compression:
            return 0.0, 0.0
        strain = self.material.eps_cu * (c - self.d_prime) / c
        stress = max(-self.material.fy, min(self.material.fy, self.material.es * strain))
        return strain, stress

    def _raw_strength(
        self, as_tension: float, *, equilibrium: dict[str, float | str | bool] | None = None,
    ) -> tuple[float, float, str, float]:
        material = self.material
        if as_tension <= 0:
            return 0.0, 0.0, "플랜지 내부", 0.0
        solution = equilibrium if equilibrium is not None else self._equilibrium_solution(as_tension)
        a = float(solution["root_a_mm"])
        _, fs_prime = self._compression_stress(float(solution["root_c_mm"]))
        cs = self.as_compression * fs_prime
        tension = as_tension * material.fy
        flange_capacity = 0.85 * material.fck * self.bf * self.hf
        if tension - cs <= flange_capacity:
            mn = ((tension - cs) * (self.d - a / 2.0)
                  + cs * (self.d - self.d_prime)) * 1.0e-6
            return max(0.0, mn), a, "플랜지 내부", 0.0

        as_flange = (
            0.85
            * material.fck
            * (self.bf - self.bw)
            * self.hf
            / material.fy
        )
        as_web = as_tension - as_flange - cs / material.fy
        mn_flange = as_flange * material.fy * (self.d - self.hf / 2.0)
        mn_web = as_web * material.fy * (self.d - a / 2.0)
        mn_compression = cs * (self.d - self.d_prime)
        return max(0.0, (mn_flange + mn_web + mn_compression) * 1.0e-6), a, "복부 내부", as_flange

    def maximum_tension_area(self) -> float:
        material = self.material
        c_max = (
            material.eps_cu
            * self.tension_steel_depth
            / (material.eps_cu + material.eps_t_min)
        )
        a_max = material.beta1 * c_max
        compression_area = self.bf * min(a_max, self.hf)
        if a_max > self.hf:
            compression_area += self.bw * (a_max - self.hf)
        _, fs_prime = self._compression_stress(c_max)
        return (0.85 * material.fck * compression_area
                + self.as_compression * fs_prime) / material.fy

    def minimum_tension_area(self, *, use_textbook_rounding: bool = True) -> float:
        """실제 T 총단면 Ig로 계산한 1.2Mcr 조건의 최소 철근량."""
        target = 1.2 * self.cracking_moment()
        low = 0.0
        high = self.maximum_tension_area()
        if self._design_strength(
            high, use_textbook_rounding=use_textbook_rounding
        ) < target:
            return float("inf")
        for _ in range(100):
            mid = (low + high) / 2.0
            if self._design_strength(
                mid, use_textbook_rounding=use_textbook_rounding
            ) < target:
                low = mid
            else:
                high = mid
        return (low + high) / 2.0

    def _design_strength(
        self, as_tension: float, *, use_textbook_rounding: bool = True
    ) -> float:
        """철근량별 순인장변형률을 반영한 제한 전 설계휨강도."""
        raw_mn, a, _, _ = self._raw_strength(as_tension)
        if raw_mn <= 0 or a <= 0:
            return 0.0
        c = self._strain_neutral_axis(
            a, use_textbook_rounding=use_textbook_rounding
        )
        _, phi, _ = self._tension_strain_and_phi(
            c, use_textbook_rounding=use_textbook_rounding
        )
        return phi * raw_mn

    def _strain_neutral_axis(
        self, a: float, *, use_textbook_rounding: bool = True
    ) -> float:
        """리포트는 중간값 반올림, 그래프는 원시 a로 중립축 깊이를 구한다."""
        a_for_strain = round(a) if use_textbook_rounding else a
        return a_for_strain / self.material.beta1

    def analyze(self, *, use_textbook_rounding: bool = True) -> AnalysisResult:
        material = self.material
        rho = self.reinforcement_ratio()
        as_min = self.minimum_tension_area(
            use_textbook_rounding=use_textbook_rounding
        )
        as_max = self.maximum_tension_area()
        rho_min = as_min / (self.bw * self.d)
        rho_max = as_max / (self.bw * self.d)
        equilibrium = self._equilibrium_solution(self.as_tension)
        raw_mn, a, neutral_axis_location, as_flange = self._raw_strength(
            self.as_tension, equilibrium=equilibrium,
        )
        a_for_strain = round(a) if use_textbook_rounding else a
        c = self._strain_neutral_axis(
            a, use_textbook_rounding=use_textbook_rounding
        )
        eps_t, phi, strain_region = self._tension_strain_and_phi(
            c, use_textbook_rounding=use_textbook_rounding
        )
        y_bar, i_g, y_t = self.gross_section_properties()
        m_cr = self.cracking_moment()

        violations: list[str] = []
        if self.as_tension < as_min:
            violations.append("최소철근량 미달 (phiMn < 1.2Mcr)")
        if self.as_tension > as_max:
            violations.append("최대철근량 초과")
        valid = not violations
        mn = raw_mn if valid else 0.0
        raw_phi_mn = phi * raw_mn
        phi_mn = raw_phi_mn if valid else 0.0

        values: dict[str, float | str | bool] = {
            "rho": rho,
            "rho_min": rho_min,
            "rho_max": rho_max,
            "as_min_mm2": as_min,
            "as_max_mm2": as_max,
            "a_mm": a,
            "c_mm": c,
            "d_t_mm": self.tension_steel_depth,
            "eps_t": eps_t,
            "phi": phi,
            "strain_region": strain_region,
            "neutral_axis_location": neutral_axis_location,
            "as_flange_mm2": as_flange,
            "centroid_from_top_mm": y_bar,
            "ig_mm4": i_g,
            "yt_mm": y_t,
            "mcr_knm": m_cr,
            "minimum_required_design_strength_knm": 1.2 * m_cr,
        }
        values.update(equilibrium)
        if self.as_compression:
            eps_prime, fs_prime = self._compression_stress(float(equilibrium["root_c_mm"]))
            values.update({
                "eps_s_prime": eps_prime, "fs_prime_mpa": fs_prime,
                "cs_kn": self.as_compression * fs_prime * 1.0e-3,
                "compression_steel_yielded": abs(fs_prime - material.fy) < 1.0e-6,
            })
        a_for_strain_text = (
            f"{a_for_strain:.0f}"
            if use_textbook_rounding
            else f"{a_for_strain:.3f}"
        )
        steps = [
            *self._root_steps(equilibrium),
            f"T 총단면 도심 ybar = {y_bar:.3f} mm",
            f"Ig = {i_g:,.3f} mm^4, yt = {y_t:.3f} mm",
            f"Mcr = 0.63*sqrt(fck)*Ig/yt = {m_cr:.3f} kN·m",
            f"최소철근 조건: phi*Mn >= 1.2Mcr = {1.2 * m_cr:.3f} kN·m",
            f"As,min = {as_min:.3f} mm², As,max = {as_max:.3f} mm²",
            f"중립축 판정 = {neutral_axis_location}, a = {a:.3f} mm",
            f"변형률 검토용 a = {a_for_strain_text} mm",
            f"c = a/beta1 = {a_for_strain_text}/{material.beta1:g} = {c:.3f} mm",
            f"Mn = {raw_mn:.3f} kN·m",
        ]
        if self.as_compression:
            steps.append(
                f"압축철근: ε'_s = {eps_prime:.6f}, f'_s = {fs_prime:.2f} MPa, "
                f"C_s' = {self.as_compression * fs_prime * 1.0e-3:.2f} kN"
            )
        steps.extend(
            self._strength_reduction_steps(
                c,
                eps_t,
                phi,
                strain_region,
                use_textbook_rounding=use_textbook_rounding,
            )
        )
        steps.append(f"phi*Mn = {phi:.3f}*Mn = {raw_phi_mn:.3f} kN·m")
        return AnalysisResult(
            "복근 T형보" if self.as_compression else "T형보",
            mn,
            phi_mn,
            raw_mn,
            raw_phi_mn,
            valid,
            tuple(violations),
            values,
            tuple(steps),
        )

