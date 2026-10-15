# RC Beam Analyzer

『철근콘크리트 구조설계』 8판을 기준으로 단근 직사각형보, 복근 직사각형보, T형보의 공칭휨강도와 설계휨강도를 계산하는 데스크톱 애플리케이션입니다.

Tkinter GUI에 Matplotlib 단면도와 철근비–휨강도 그래프를 결합했으며, 같은 계산 결과를 터미널에서도 정렬된 리포트로 확인할 수 있습니다.

## 주요 기능

- `SinglyReinforcedBeam`, `DoublyReinforcedBeam`, `TBeam` 독립 해석 클래스
- 복근보 압축철근의 항복·비항복 상태 자동 판정
- T형보 중립축의 플랜지·복부 위치 자동 판정
- 순인장변형률에 따른 압축지배·변화구간·인장지배 판정 및 `φ` 계산
- `dt`가 직접 주어지지 않으면 최외단 인장철근 깊이를 `h-60 mm`로 계산
- T형 총단면의 도심, 단면2차모멘트 `Ig`, 균열모멘트 `Mcr` 별도 계산
- 최소·최대철근 한계 위반 시 명세에 따라 `Mn = φMn = 0` 처리
- 인장철근비 `As/(bd) = 0~3%`에 대한 공칭·설계휨강도 그래프
- 교재 예제 4-2, 4-3, 4-5 입력 프리셋
- GUI 없이 실행 가능한 예제 리포트 및 그래프 저장 모드

## 계산 기준

| 항목 | 적용값 |
|---|---:|
| 콘크리트 | 일반 콘크리트 (`λ = 1.0`) |
| 적용 범위 | `0 < fck ≤ 40 MPa` |
| 콘크리트 극한압축변형률 | `εcu = 0.0033` |
| 등가응력블록 계수 | `β1 = 0.8` |
| 철근 탄성계수 | `Es = 200,000 MPa` |
| 휨 강도감소계수 | 순인장변형률에 따라 `0.65 ≤ φ ≤ 0.85` |
| 최외단 인장철근 깊이 | 미입력 시 `dt = h-60 mm` |

이 프로그램은 수업 과제 및 학습용입니다. 실제 구조물의 설계·안전성 검토에는 사용할 수 없습니다.

## 실행 환경

- Python 3.10 이상
- Windows 10/11 권장
- Tkinter: Python 표준 라이브러리이므로 `requirements.txt`에 포함되지 않음
- 외부 패키지: Matplotlib

## 설치 및 GUI 실행

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Python 공식 Windows 설치판에는 일반적으로 Tkinter가 포함됩니다. 최소 설치판에서 GUI 모듈 오류가 발생한다면 Python 설치 관리자의 `tcl/tk and IDLE` 구성요소를 추가합니다.

## 터미널 리포트

GUI를 열지 않고 세 교재 예제를 일괄 계산합니다.

```powershell
python main.py --examples
```

계산 결과와 그래프 PNG를 함께 생성하려면 다음과 같이 실행합니다.

```powershell
python main.py --examples --save-plots outputs
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

테스트는 계산 상수, 교재 예제 결과, 철근비 제한, T형보 단면2차모멘트, GUI 없이 Matplotlib Figure가 렌더링되는지를 확인합니다.

## 프로젝트 구조

```text
.
├─ main.py                         # GUI/CLI 진입점
├─ beam_analysis/
│  ├─ models.py                    # 보 클래스와 구조 계산
│  ├─ formatting.py                # 터미널·GUI 리포트
│  ├─ plotting.py                  # 단면도와 강도곡선
│  └─ gui.py                       # Tkinter 애플리케이션
├─ examples/
│  └─ textbook_examples.py         # 예제 4-2, 4-3, 4-5
├─ tests/
│  └─ test_models.py               # 자동 회귀 테스트
├─ requirements.txt
└─ .gitignore
```
