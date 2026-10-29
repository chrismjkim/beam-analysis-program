"""예제 4-2, 4-3, 4-5와 추가 T형보 입력값."""

from __future__ import annotations

from beam_analysis import DoublyReinforcedBeam, Material, TBeam


MATERIAL = Material(fck=21.0, fy=400.0)
D22_AREA = 387.1
D25_AREA = 506.7


def example_4_2() -> DoublyReinforcedBeam:
    return DoublyReinforcedBeam(
        b=300.0,
        h=600.0,
        d=515.0,
        d_prime=60.0,
        as_tension=8 * D22_AREA,
        as_compression=2 * D22_AREA,
        material=MATERIAL,
    )


def example_4_3() -> DoublyReinforcedBeam:
    return DoublyReinforcedBeam(
        b=300.0,
        h=600.0,
        d=515.0,
        d_prime=60.0,
        as_tension=8 * D22_AREA,
        as_compression=5 * D22_AREA,
        material=MATERIAL,
    )


def example_4_5() -> TBeam:
    return TBeam(
        bf=600.0,
        bw=300.0,
        hf=120.0,
        h=600.0,
        d=510.0,
        as_tension=8 * D25_AREA,
        material=MATERIAL,
    )


TEXTBOOK_EXAMPLES = {
    "예제 4-2 (복근보, 압축철근 2-D22)": example_4_2,
    "예제 4-3 (복근보, 압축철근 5-D22)": example_4_3,
    "예제 4-5 (T형보)": example_4_5,
}


def additional_t_without_compression() -> TBeam:
    return TBeam(
        bf=800.0, bw=400.0, hf=150.0, h=600.0, d=515.0, d_t=540.0,
        as_tension=8 * D25_AREA, material=Material(fck=27.0, fy=400.0),
    )


def additional_t_with_compression() -> TBeam:
    return TBeam(
        bf=800.0, bw=400.0, hf=150.0, h=600.0, d=515.0, d_t=540.0,
        as_tension=8 * D25_AREA, as_compression=4 * D25_AREA, d_prime=60.0,
        material=Material(fck=27.0, fy=400.0),
    )


DOUBLY_T_EXAMPLE = "복근 T형보 (압축철근 4-D25, h=600 mm 가정)"

ADDITIONAL_EXAMPLES = {
    "추가 T형보 (압축철근 없음, h=600 mm 가정)": additional_t_without_compression,
    DOUBLY_T_EXAMPLE: additional_t_with_compression,
}
ALL_EXAMPLES = {**TEXTBOOK_EXAMPLES, **ADDITIONAL_EXAMPLES}

