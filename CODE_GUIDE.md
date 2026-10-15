# RC Beam Analyzer 코드 설명서

이 문서는 프로젝트의 각 Python 스크립트가 맡는 역할과 클래스·주요 함수의 동작을 설명한다. 계산 코드는 입력, 구조해석, 결과 표현을 분리하여 GUI 외의 환경에서도 같은 해석 클래스를 재사용할 수 있도록 구성되어 있다.

## 전체 실행 흐름

1. `main.py`가 실행 옵션을 판독한다.
2. 옵션이 없으면 Tkinter GUI를 열고, `--examples`가 있으면 교재 예제를 터미널에서 실행한다.
3. GUI 또는 예제 모듈이 `Material`과 보 객체를 생성한다.
4. 각 보 객체의 `analyze()`가 재료·단면·철근 조건으로 강도를 계산한다.
5. 계산 결과는 공통 `AnalysisResult` 객체로 반환된다.
6. `formatting.py`는 결과를 터미널 리포트로, `plotting.py`는 단면도와 강도곡선으로 변환한다.

해석 모델의 관계는 `BEAM_ANALYSIS_UML.mmd`, GUI와 출력 계층을 포함한 관계는 `APPLICATION_UML.mmd`에서 확인할 수 있다.

## `main.py`

프로그램의 단일 진입점이다. GUI와 CLI가 서로 다른 계산식을 가지지 않도록 두 실행 방식 모두 `beam_analysis` 패키지를 호출한다.

### `_configure_console()`

Windows 터미널에서 한글, 그리스 문자, 상자 문자가 최대한 안정적으로 출력되도록 표준 출력과 표준 오류의 인코딩을 UTF-8로 설정한다.

### `build_parser()`

다음 명령행 옵션을 정의한다.

- `--examples`: GUI를 열지 않고 예제 4-2, 4-3, 4-5를 계산한다.
- `--save-plots DIR`: 예제 결과의 Matplotlib 그래프를 지정한 디렉터리에 PNG로 저장한다.

### `run_examples()`

`TEXTBOOK_EXAMPLES`의 팩토리 함수를 순회한다. 각 함수가 반환한 보 객체를 해석하고, `format_result()`로 계산 과정을 출력한다. 그래프 저장 경로가 있으면 `create_analysis_figure()`가 생성한 Figure를 PNG로 저장한다.

### `main()`

CLI 옵션이 있으면 예제 모드를 실행하고, 옵션이 없으면 `beam_analysis.gui.launch()`를 지연 import하여 GUI를 연다. Matplotlib 또는 Tcl/Tk가 없을 때는 설치·확인 방법을 오류 메시지로 안내한다.

## `beam_analysis/__init__.py`

외부 코드에서 긴 내부 경로를 알 필요 없이 핵심 모델을 가져올 수 있도록 공개 인터페이스를 정리한다.

```python
from beam_analysis import Material, SinglyReinforcedBeam, DoublyReinforcedBeam, TBeam
```

`__all__`에는 재료, 결과 객체, 세 보 클래스만 노출한다. GUI나 Matplotlib을 import하지 않으므로 계산 코어만 사용하는 CLI는 가볍게 시작할 수 있다.

## `beam_analysis/models.py`

프로젝트의 핵심 구조계산 모듈이다. 길이는 mm, 면적은 mm², 응력은 MPa, 모멘트는 kN·m를 사용한다.

### `Material`

일반 콘크리트와 철근의 공통 재료 정수를 보관하는 불변 데이터 클래스다.

- `fck`: 콘크리트 압축강도. 과제 범위인 `0 < fck ≤ 40 MPa`만 허용한다.
- `fy`: 철근 항복강도
- `es`: 철근 탄성계수, 기본값 `200,000 MPa`
- `phi`: 인장지배 단면의 강도감소계수 상한값 `0.85`
- `phi_min`: 압축지배 단면의 강도감소계수 `0.65`
- `eps_cu`: 콘크리트 극한압축변형률, `0.0033`
- `beta1`: 등가응력블록 계수, `0.8`
- `lambda_`: 일반 콘크리트 계수, `1.0`
- `eps_y`: `fy / Es`로 계산한 철근 항복변형률
- `eps_t_min`: `0.004`와 `2εy` 중 큰 값
- `strength_reduction_factor()`: `εt`와 `εy`, 인장지배 한계 `0.005`를 비교하여 `0.65~0.85`의 실제 `φ` 계산. 변화구간의 `φ`는 교재 풀이 표기에 맞춰 소수 셋째 자리까지 계산에 적용한다.

`__post_init__()`는 과제에서 허용하지 않은 콘크리트 강도나 음수 재료값이 계산으로 들어오는 것을 차단한다.

### `AnalysisResult`

세 보 형식의 서로 다른 계산 결과를 하나의 출력 형식으로 전달하는 데이터 클래스다.

- `nominal_strength`, `design_strength`: 철근 제한을 적용한 최종 강도
- `raw_nominal_strength`, `raw_design_strength`: 제한 판정 전 계산 강도
- `valid`: 최소·최대철근 조건의 적합 여부
- `violations`: 위반 사유 목록
- `values`: 중립축, 응력블록 깊이, 철근비 등 수치 데이터
- `steps`: 터미널에 표시할 계산 순서

명세에 따라 철근 제한을 벗어나면 최종 `Mn`과 `φMn`은 0이 되지만, 원인을 검토할 수 있도록 제한 전 강도는 별도로 보존한다.

### `Beam`

세 보 클래스의 추상 기반 클래스다. 모든 보가 같은 방식으로 GUI와 그래프에 연결되도록 다음 인터페이스를 강제한다.

- `analyze()`: `AnalysisResult` 반환
- `with_tension_area()`: 인장철근량만 바꾼 새 객체 반환
- `reinforcement_ratio()`: 현재 철근비 반환
- `reference_width`: 철근비 계산의 기준 폭
- `strength_curve()`: 철근비 0~3% 구간에서 보 객체를 반복 생성하여 `Mn`, `φMn` 배열 계산
- `tension_steel_depth`: `d_t` 직접 입력값을 우선 사용하고, 미입력 시 `h-60 mm` 반환

`_rectangular_rho_min()`은 교재 식 (4.14)의 최소철근비를, `_rectangular_rho_max()`는 최외단 인장철근의 최소 허용변형률로부터 최대철근비를 계산한다.

### `SinglyReinforcedBeam`

인장철근만 배근한 직사각형보를 나타낸다.

계산 순서는 다음과 같다.

1. `ρ = As/(bd)`로 인장철근비를 계산한다.
2. 힘의 평형으로 등가응력블록 깊이 `a = As·fy/(0.85·fck·b)`를 계산한다.
3. `c = a/β1`으로 중립축을 구한다.
4. `Mn = As·fy·(d-a/2)`로 공칭휨강도를 계산한다.
5. `εt = εcu(d_t-c)/c`와 `0.005`를 비교하여 `φ`를 결정한다. `d_t`가 없으면 `h-60 mm`를 사용한다.
6. `ρmin ≤ ρ ≤ ρmax`인지 확인하고, 위반하면 최종 강도를 0으로 처리한다.

### `DoublyReinforcedBeam`

인장철근과 압축철근을 모두 가진 직사각형보를 나타낸다.

- `effective_reinforcement_ratio()`: 최대·최소철근 검토에 사용하는 `(As-As')/(bd)` 계산
- `_steel_stress(c)`: 변형률 적합조건으로 압축철근의 변형률과 응력을 구하고 응력을 `-fy`와 `+fy` 사이로 제한
- `_neutral_axis()`: 콘크리트 압축력, 압축철근력, 인장철근력의 평형점이 되는 `c`를 이분법으로 탐색
- `analyze()`: 압축철근의 항복 여부, 콘크리트 압축력 `Cc`, 철근 압축력 `Cs'`, 공칭휨강도를 계산

공칭휨강도는 다음 두 저항모멘트의 합으로 계산한다.

```text
Mn = Cc(d-a/2) + Cs'(d-d')
```

압축철근을 2-D22 사용한 예제 4-2에서는 압축철근이 항복하고, 5-D22인 예제 4-3에서는 비항복 상태가 자동으로 선택된다.

### `TBeam`

플랜지 폭 `bf`, 복부 폭 `bw`, 플랜지 두께 `hf`를 가진 T형보를 나타낸다.

- `gross_section_properties()`: 플랜지와 복부를 두 직사각형으로 나누어 전체 도심 `ybar`, 평행축정리를 적용한 `Ig`, 인장연단 거리 `yt`를 계산
- `cracking_moment()`: 일반 콘크리트 파괴계수 `0.63√fck`와 `Ig/yt`로 `Mcr` 계산
- `_raw_strength()`: 등가응력블록이 플랜지 안에 있는지 복부까지 내려가는지 판정하여 공칭휨강도 계산
- `_strain_neutral_axis()`: 교재 예제처럼 응력블록 깊이 `a`를 mm 단위로 정리하여 변형률 검토용 `c=a/β1` 계산
- `maximum_tension_area()`: 최소 허용 인장변형률에서 가능한 최대 압축응력블록과 `As,max` 계산
- `minimum_tension_area()`: 철근량마다 `εt`로 `φ`를 계산하면서 `φMn ≥ 1.2Mcr`가 처음 만족되는 `As,min`을 이분법으로 탐색

T형보의 최소철근 검토는 직사각형보의 단순 철근비 식을 재사용하지 않고, 명세대로 T 총단면의 단면2차모멘트를 별도로 계산한다.

## `beam_analysis/formatting.py`

터미널과 GUI 하단의 계산 리포트를 생성한다.

- `_display_width()`: 한글처럼 터미널에서 두 칸을 차지하는 문자의 폭을 계산
- `_pad()`: 표시 폭을 기준으로 문자열 정렬
- `_wrap_display()`: 긴 계산식을 상자 경계 안에서 줄바꿈
- `_rows()`: 라벨과 값을 고정폭 행으로 변환
- `format_result()`: 판정, 강도, 철근비, 계산 단계, 적용 기준을 상자형 리포트로 조립
- `format_material()`: 재료 상수를 한 줄 요약으로 변환

문자열 길이가 아니라 실제 표시 폭을 사용하므로 한글과 영문이 섞여도 테두리가 가능한 한 일정하게 정렬된다.

## `beam_analysis/plotting.py`

Matplotlib Figure 안에 단면도와 철근비–휨강도 그래프를 함께 구성한다.

### `configure_font()`

맑은 고딕, AppleGothic, 나눔고딕, Noto Sans CJK KR 순서로 한글 글꼴을 찾는다. 한글 글꼴이 없으면 축 제목을 영문으로 바꾸어 깨진 글자 출력을 방지한다.

### `draw_section()`

객체 형식을 검사하여 직사각형 또는 T형 콘크리트 패치를 그리고, 철근량에 따라 철근 원을 배치한다. 복근보는 상부 압축철근과 하부 인장철근을 모두 표현한다.

### `draw_strength_curve()`

`Beam.strength_curve()`에서 받은 철근비 0~3%의 `Mn`, `φMn`을 그린다. 최소·최대철근 범위 밖은 붉은 배경으로 표시하고, 현재 입력 단면의 위치를 점과 주석으로 강조한다.

### `create_analysis_figure()`

단면도 축과 강도곡선 축을 하나의 Figure로 조립한다. GUI는 이 Figure를 Tkinter에 삽입하고, CLI는 동일한 Figure를 PNG로 저장한다.

## `beam_analysis/gui.py`

Tkinter 데스크톱 애플리케이션을 구성한다.

### `FIELD_SETS`

보 형식별 입력 필드의 내부 이름, 화면 라벨, 기본값을 정의한다. 보 형식을 바꾸면 이 설정을 읽어 입력창을 다시 구성한다.

### `BeamAnalyzerApp`

GUI의 상태와 이벤트를 관리하는 유일한 화면 클래스다.

- `_configure_style()`: 색상, 글꼴, 카드형 프레임 스타일 설정
- `_build_layout()`: 입력 패널, 그래프 패널, 계산 리포트 패널 배치
- `_build_input_panel()`: 예제 선택, 보 형식, 단면, 재료 입력 위젯 생성
- `_rebuild_section_fields()`: 선택한 보 형식에 맞추어 입력 필드를 교체
- `load_example()`: 예제 팩토리로 객체를 만든 뒤 그 값을 입력창에 채움
- `_build_beam()`: 입력 문자열을 숫자로 검증하고 적절한 보 클래스 생성
- `run_analysis()`: 해석 실행 후 터미널과 GUI 리포트, 상태 문구, Figure를 한 번에 갱신
- `_show_figure()`: 기존 Canvas와 Toolbar를 제거하고 새 Matplotlib Figure 삽입

### `launch()`

Tk 루트 창과 `BeamAnalyzerApp`을 만들고 이벤트 루프를 시작한다.

## `examples/__init__.py`

`examples` 디렉터리를 Python 패키지로 인식시키는 파일이다. 실행 코드는 포함하지 않는다.

## `examples/textbook_examples.py`

교재 예제를 재현하는 팩토리 함수를 정의한다.

- `MATERIAL`: 세 예제가 공유하는 `fck=21 MPa`, `fy=400 MPa` 재료 객체
- `D22_AREA`, `D25_AREA`: 예제에서 사용하는 철근 한 가닥의 단면적
- `example_4_2()`: 8-D22 인장철근과 2-D22 압축철근을 가진 복근보
- `example_4_3()`: 8-D22 인장철근과 5-D22 압축철근을 가진 복근보
- `example_4_5()`: 8-D25 인장철근을 가진 T형보
- `TEXTBOOK_EXAMPLES`: GUI 표시 이름과 팩토리 함수를 연결하는 사전

객체를 미리 생성하지 않고 함수로 생성하므로 GUI와 테스트가 매번 독립적인 불변 보 객체를 받는다.

## `tests/test_models.py`

표준 라이브러리 `unittest`로 작성된 회귀 테스트다.

### `MaterialRuleTests`

과제 상수 `εcu=0.0033`, `β1=0.8`, `λ=1.0`이 유지되는지 확인하고, `fck > 40 MPa` 입력이 거부되는지 검사한다.

### `TextbookExampleTests`

예제 4-2, 4-3, 4-5의 공칭·설계휨강도를 발췌본의 반올림 결과와 비교한다. 복근보의 압축철근 항복 여부와 T형보 중립축 위치도 함께 검사한다.

### `LimitAndSectionTests`

- 최소철근비 미달 시 강도가 0인지 검사
- 최대철근비 초과 시 강도가 0인지 검사
- T형보의 도심, `Ig`, `yt`, `Mcr` 검사
- GUI 없이 Matplotlib Figure를 PNG 바이트로 렌더링할 수 있는지 검사

## 유지보수 시 확인 순서

계산식을 변경했다면 다음 순서로 검증한다.

```powershell
python -m unittest discover -s tests -v
python main.py --examples
python main.py --examples --save-plots outputs
python main.py
```

새 보 형식을 추가하려면 `Beam`을 상속한 모델을 먼저 작성하고, 그다음 `FIELD_SETS`, `_build_beam()`, `draw_section()`을 연결한다. 계산 코어를 GUI 이벤트 안에 직접 작성하지 않는 것이 현재 구조의 핵심 원칙이다.

