"""RC Beam Analyzer 실행 진입점."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from beam_analysis.formatting import format_result
from examples.textbook_examples import TEXTBOOK_EXAMPLES


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, OSError):
                pass

def run_examples(save_directory: Path | None = None) -> int:
    if save_directory is not None:
        save_directory.mkdir(parents=True, exist_ok=True)
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        from beam_analysis.plotting import create_analysis_figure

    for index, (name, factory) in enumerate(TEXTBOOK_EXAMPLES.items(), start=1):
        beam = factory()
        result = beam.analyze()
        if index > 1:
            print()
        print(format_result(beam, result, name))
        if save_directory is not None:
            figure = create_analysis_figure(beam, result)
            FigureCanvasAgg(figure)
            example_number = name.split()[1].replace("-", "_")
            target = save_directory / f"example_{example_number}.png"
            figure.savefig(target, dpi=180, bbox_inches="tight")
            print(f"그래프 저장: {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="단근보·복근보·T형보 휨강도 해석 데스크톱 애플리케이션"
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="GUI 대신 교재 예제 4-2, 4-3, 4-5 결과를 터미널에 출력",
    )
    parser.add_argument(
        "--save-plots",
        type=Path,
        metavar="DIR",
        help="--examples와 함께 사용하여 그래프 PNG를 지정 폴더에 저장",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    args = build_parser().parse_args(argv)
    if args.examples or args.save_plots is not None:
        try:
            return run_examples(args.save_plots)
        except ImportError as error:
            print("그래프 생성에 필요한 Matplotlib을 불러오지 못했습니다.", file=sys.stderr)
            print("python -m pip install -r requirements.txt", file=sys.stderr)
            print(f"상세 오류: {error}", file=sys.stderr)
            return 1

    try:
        from beam_analysis.gui import launch

        launch()
    except ImportError as error:
        print("GUI 실행에 필요한 모듈을 불러오지 못했습니다.", file=sys.stderr)
        print("python -m pip install -r requirements.txt", file=sys.stderr)
        print(f"상세 오류: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        # 디스플레이가 없는 환경에서도 CLI 사용법을 즉시 안내한다.
        if error.__class__.__name__ == "TclError":
            print("Tkinter GUI를 열 수 없습니다.", file=sys.stderr)
            print(
                "Python 설치 관리자의 'tcl/tk and IDLE' 구성요소와 디스플레이 환경을 확인하세요.",
                file=sys.stderr,
            )
            print("GUI 없이 확인: python main.py --examples", file=sys.stderr)
            return 1
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

