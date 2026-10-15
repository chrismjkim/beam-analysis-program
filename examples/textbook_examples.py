"""『철근콘크리트 구조설계』 8판 예제 4-2, 4-3, 4-5."""

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
    # 사용자가 제공한 발췌 이미지 기준: 압축철근 5-D22
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

