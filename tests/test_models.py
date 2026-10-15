"""교재 예제와 철근비 제한을 검증하는 회귀 테스트."""

from __future__ import annotations

import io
import unittest
from dataclasses import replace

from matplotlib.backends.backend_agg import FigureCanvasAgg

from beam_analysis import Material, SinglyReinforcedBeam
from beam_analysis.plotting import create_analysis_figure
from examples.textbook_examples import example_4_2, example_4_3, example_4_5


class MaterialRuleTests(unittest.TestCase):
    def test_assignment_constants(self) -> None:
        material = Material(fck=21, fy=400)
        self.assertEqual(material.eps_cu, 0.0033)
        self.assertEqual(material.beta1, 0.8)
        self.assertEqual(material.lambda_, 1.0)
        self.assertEqual(material.phi_min, 0.65)
        self.assertEqual(material.phi, 0.85)

    def test_strength_reduction_factor_regions(self) -> None:
        material = Material(fck=21, fy=400)
        self.assertEqual(material.strength_reduction_factor(0.002), (0.65, "압축지배단면"))
        phi_transition, region = material.strength_reduction_factor(0.0035)
        self.assertAlmostEqual(phi_transition, 0.75, places=12)
        self.assertEqual(region, "변화구간단면")
        self.assertEqual(
            material.strength_reduction_factor(0.004917),
            (0.85, "인장지배단면"),
        )
        phi_near_limit, region = material.strength_reduction_factor(
            0.004917, use_textbook_rounding=False
        )
        expected_phi = 0.65 + 0.20 * (0.004917 - 0.002) / (0.005 - 0.002)
        self.assertAlmostEqual(phi_near_limit, expected_phi, places=12)
        self.assertEqual(region, "변화구간단면")
        self.assertEqual(material.strength_reduction_factor(0.005), (0.85, "인장지배단면"))

    def test_strength_reduction_factor_is_continuous_at_tension_limit(self) -> None:
        material = Material(fck=21, fy=400)
        phi_below, _ = material.strength_reduction_factor(
            0.005 - 1.0e-9, use_textbook_rounding=False
        )
        phi_at_limit, _ = material.strength_reduction_factor(
            0.005, use_textbook_rounding=False
        )
        self.assertAlmostEqual(phi_below, phi_at_limit, places=6)

    def test_fck_above_40_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "fck <= 40"):
            Material(fck=41, fy=400)


class TextbookExampleTests(unittest.TestCase):
    def test_example_4_2(self) -> None:
        result = example_4_2().analyze()
        self.assertTrue(result.valid)
        self.assertTrue(result.values["compression_steel_yielded"])
        self.assertAlmostEqual(result.nominal_strength, 538.8, delta=0.1)
        self.assertAlmostEqual(result.design_strength, 458.0, delta=0.1)
        self.assertAlmostEqual(result.values["d_t_mm"], 540.0, delta=0.001)
        self.assertAlmostEqual(result.values["eps_t"], 0.004917, delta=0.000001)
        self.assertEqual(result.values["phi"], 0.85)
        self.assertEqual(result.values["strain_region"], "인장지배단면")
        self.assertAlmostEqual(result.values["a_assumed_yield_mm"], 173.49, delta=0.01)
        self.assertIn("a = 173.49 mm", result.steps)
        self.assertIn("c = a / beta1 = 216.86 mm", result.steps)
        graph_result = example_4_2().analyze(use_textbook_rounding=False)
        self.assertAlmostEqual(graph_result.design_strength, 454.98001832156854, places=9)
        self.assertAlmostEqual(graph_result.values["phi"], 0.8444786015672092, places=12)

    def test_example_4_3(self) -> None:
        result = example_4_3().analyze()
        self.assertTrue(result.valid)
        self.assertFalse(result.values["compression_steel_yielded"])
        self.assertAlmostEqual(result.nominal_strength, 568.4, delta=0.3)
        self.assertAlmostEqual(result.design_strength, 483.1, delta=0.1)
        self.assertGreaterEqual(result.values["eps_t"], 0.005)
        self.assertEqual(result.values["phi"], 0.85)
        self.assertEqual(result.values["strain_region"], "인장지배단면")
        self.assertAlmostEqual(result.values["a_assumed_yield_mm"], 86.75, delta=0.01)
        self.assertAlmostEqual(result.values["quadratic_root_mm"], 103.45, delta=0.01)
        self.assertAlmostEqual(
            result.values["quadratic_root_mm"], result.values["a_mm"], places=9
        )
        self.assertTrue(any("비항복 이차방정식" in step for step in result.steps))
        self.assertIn("a = 103.45 mm", result.steps)
        self.assertIn("c = a / beta1 = 129.32 mm", result.steps)
        graph_result = example_4_3().analyze(use_textbook_rounding=False)
        self.assertAlmostEqual(graph_result.design_strength, 482.9708930101057, places=9)

    def test_example_4_5(self) -> None:
        result = example_4_5().analyze()
        self.assertTrue(result.valid)
        self.assertEqual(result.values["neutral_axis_location"], "복부 내부")
        self.assertAlmostEqual(result.nominal_strength, 698.9, delta=0.1)
        self.assertAlmostEqual(result.design_strength, 570.3, delta=0.1)
        self.assertAlmostEqual(result.values["d_t_mm"], 540.0, delta=0.001)
        self.assertAlmostEqual(result.values["c_mm"], 228.75, delta=0.001)
        self.assertAlmostEqual(result.values["eps_t"], 0.004490, delta=0.000001)
        self.assertEqual(result.values["phi"], 0.816)
        self.assertEqual(result.values["strain_region"], "변화구간단면")
        self.assertTrue(any("epsilon_t 비교" in step for step in result.steps))
        self.assertTrue(any(step.startswith("phi = 0.65") and step.endswith("= 0.816") for step in result.steps))
        graph_result = example_4_5().analyze(use_textbook_rounding=False)
        self.assertAlmostEqual(graph_result.design_strength, 570.7413822112503, places=9)
        self.assertAlmostEqual(graph_result.values["c_mm"], 228.48739495798327, places=9)
        self.assertAlmostEqual(graph_result.values["phi"], 0.8166078215030034, places=12)

    def test_explicit_dt_overrides_h_minus_60_default(self) -> None:
        beam = example_4_5()
        self.assertEqual(beam.tension_steel_depth, 540.0)
        self.assertEqual(replace(beam, d_t=550.0).tension_steel_depth, 550.0)


class LimitAndSectionTests(unittest.TestCase):
    def test_strength_is_zero_below_minimum_ratio(self) -> None:
        beam = SinglyReinforcedBeam(b=300, h=600, d=520, as_tension=1.0)
        result = beam.analyze()
        self.assertFalse(result.valid)
        self.assertEqual(result.nominal_strength, 0.0)
        self.assertEqual(result.design_strength, 0.0)
        self.assertIn("최소철근비 미달", result.violations)

    def test_strength_is_zero_above_maximum_ratio(self) -> None:
        beam = SinglyReinforcedBeam(b=300, h=600, d=520, as_tension=0.03 * 300 * 520)
        result = beam.analyze()
        self.assertFalse(result.valid)
        self.assertEqual(result.nominal_strength, 0.0)
        self.assertEqual(result.design_strength, 0.0)
        self.assertIn("최대철근비 초과", result.violations)

    def test_t_beam_gross_section_properties(self) -> None:
        beam = example_4_5()
        y_bar, i_g, y_t = beam.gross_section_properties()
        self.assertAlmostEqual(y_bar, 260.0, places=6)
        self.assertAlmostEqual(i_g, 7_171_200_000.0, places=1)
        self.assertAlmostEqual(y_t, 340.0, places=6)
        self.assertGreater(beam.cracking_moment(), 0.0)

    def test_figure_can_render_without_gui(self) -> None:
        beam = example_4_2()
        figure = create_analysis_figure(beam)
        FigureCanvasAgg(figure)
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png")
        self.assertGreater(buffer.tell(), 10_000)

    def test_strength_plot_marks_limits_and_current_condition_in_red(self) -> None:
        beam = example_4_2()
        figure = create_analysis_figure(beam)
        strength_axis = figure.axes[1]
        labels = [text.get_text() for text in strength_axis.texts]
        current_label = next(label for label in labels if "φMn=" in label)

        self.assertTrue(any(label.startswith("최소 ρ") or label.startswith("Min ρ") for label in labels))
        self.assertTrue(any(label.startswith("최대 ρ") or label.startswith("Max ρ") for label in labels))
        self.assertIn(f"ρ={beam.reinforcement_ratio() * 100.0:.3f}%", current_label)
        self.assertIn("φMn=458.0", current_label)
        self.assertNotIn("φMn=455.0", current_label)
        current_text = next(text for text in strength_axis.texts if text.get_text() == current_label)
        self.assertEqual(current_text.get_color(), "#d1495b")
        self.assertEqual(strength_axis.collections[-1].get_facecolor()[0][:3].tolist(), [0.8196078431372549, 0.28627450980392155, 0.3568627450980392])

    def test_strength_curve_has_no_internal_rounding_jump(self) -> None:
        beam = example_4_2()
        _, _, design = beam.strength_curve(points=1501)
        adjacent_valid_changes = [
            abs(current - previous)
            for previous, current in zip(design, design[1:])
            if previous > 0.0 and current > 0.0
        ]
        self.assertLess(max(adjacent_valid_changes), 1.0)


if __name__ == "__main__":
    unittest.main()

