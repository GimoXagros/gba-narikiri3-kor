# 빌드 및 패키지 재현

## 도구 의존성 검사

개발 의존성은 Python 3.12 이상을 요구합니다(NumPy의 최소 버전 조건).
Python 3.12와 3.14에서 `python -m unittest discover -s tests -v`로 합성 입력의
쓰기 범위·원본 보호, 타일 왕복 변환, RLE 왕복 및 선택적 fontTools API를 검사합니다.
fontTools는 현재 빌드 코드에서 직접 사용하지 않습니다. 이 검사는 ROM 재빌드,
패치 재적용, 자연 진행·저장 또는 실기 검증을 대신하지 않습니다.

## v1.3b 소스 빌드

같은 일본판·IPS와 ARM 도구로 v1.3a까지의 기준선을 재생성한 다음 `source/v13b/`를 적용합니다. 완성 한국어 ROM은 입력으로 사용하지 않습니다.

```powershell
python -X utf8 tools/build_v13b.py --j '일본판.gba' --ips 'ToWN3(K) 1.1.ips' --toolchain 'C:\도구\gcc-arm-none-eabi\bin' --out output/v1.3b-build
```

결과 ROM은 16,777,216바이트로 제한합니다. 최종 단계에서 확인된 문자열의 시작·종료 위치, 문자열 포인터, 이름 입력·키보드와 구분 표를 다시 검사합니다. 공유 이름은 확인한 표시 경로에서만 임시 변환하며 원래 저장 문자는 바꾸지 않습니다. 압축 자료 뒤 공간을 사용한 코드는 기존 자료의 압축 해제 결과와 실제 소비 경계를 별도로 확인합니다.

`tools/package_v13b.py`와 `tools/verify_v13b_package.py`는 아래 패키지 절차와 같은 인자를 받습니다. 소스 커밋·후보·BPS·필수 검증 결과를 고정한 후 패키지를 생성하고, 동봉 적용기로 재적용합니다. 체크섬 목록의 누락·중복과 내부·외부 명세 불일치를 거부합니다. 실행 검증은 최종 ROM·코어·입력 기록의 해시가 일치하는 `--trace-set v13b`를 사용합니다.

## v1.3a 소스 빌드

같은 준비 입력과 도구로 다음을 실행합니다. 기존 한국어 ROM이나 과거 출력 폴더를 입력으로 사용하지 않습니다.

```powershell
python -X utf8 tools/build_v13a.py --j '일본판.gba' --ips 'ToWN3(K) 1.1.ips' --toolchain 'C:\도구\gcc-arm-none-eabi\bin' --out output/v1.3a-build
```

빌더는 v1.3 기준선을 소스에서 재생성하고 `source/v13a/`의 명시적인 변경을 적용합니다. 결과는 `ND3_B3TJ_K_v1.3a.gba`와 `_FROM_J.bps`, 소스·도구·입력 해시를 포함한 `BUILD_MANIFEST.json`입니다. 최종 ROM은 16MiB를 강제합니다. 하위 기준선 빌더의 32MiB 역사 비교본은 중간 검사 자료이며 배포하지 않습니다.

대화의 고정 줄바꿈 중 승인된 위치만 표시용 제어로 바꿉니다. 기존 공백 코드의 길이를 유지하고 문자열을 이동하지 않습니다. 소형 목록은 확인된 아이템 이름 호출부만 처리하며, 화면이 참조하는 타일과 현재 이름의 타일을 보호합니다. 새 소비 경로를 추가할 때는 현재 범위의 검증을 그대로 일반화하지 마세요.

검증된 두 코어에서는 새 입력 기록을 명시해서 실행합니다. 알려진 ROM·코어·입력 해시가 아니면 실패하며 기존 검증의 기본 입력은 바꾸지 않습니다.

```powershell
python -X utf8 tools/verify_runtime_smoke.py --rom 'output/v1.3a-build/ND3_B3TJ_K_v1.3a.gba' --core 'mgba_libretro.dll' --out output/v1.3a-runtime --trace-set v13a
```

패키지는 `tools/package_v13a.py`, 실제 동봉 적용기는 `tools/verify_v13a_package.py`로 검증합니다. 인자는 아래 v1.3 절차와 동일하되 도구·폴더 버전을 바꿉니다. 정확한 커밋·후보에 묶인 SOURCE_QA, STATIC_BINARY_QA, RC_BUILD, RC_READBACK_QA, RUNTIME_SMOKE 및 독립 감사가 필요합니다. 실기 항목은 이번 사용자 지시에 따라 `DEFERRED_BY_USER`이며 에이전트 실행은 `NOT_RUN`으로 명시해야 합니다. 배포 승인과 실기 통과를 같은 판정으로 기록하지 않습니다.

## v1.3 소스 빌드

v1.3 결과는 정확히 16,777,216 bytes입니다. 개발 빌더는 별도로 준비한 일본판 B3TJ와 1.1 IPS에서 누적 번역, 승인 그림, 기존 16MiB 배치, 메뉴 최적화와 후보 교정을 순서대로 생성합니다. 과거 `output/` 폴더나 완성 한국어 ROM은 입력이 아닙니다. 아래 준비 입력과 Python 의존성, ARM 도구를 사용합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/build_release.py --j '일본판.gba' --ips 'ToWN3(K) 1.1.ips' --toolchain 'C:\도구\gcc-arm-none-eabi\bin' --out output/v1.3-build
```

매번 새 출력 폴더를 지정합니다. 결과는 `ND3_B3TJ_K_v1.3_RC16.gba`, 일본판에서 바로 적용하는 누적 BPS, 비공개 32MiB 비교본 `ND3_B3TJ_K_v1.3_FIX32.gba`와 빌드·쓰기 지도입니다. 32MiB 비교본은 배포 대상이 아닙니다. 중간 기준선만 생성하려면 `--baseline-only`를 사용합니다. `--diagnostic-field-list`는 지도 이름 등 최종 교정이 없는 과거 V4 중간 검사 모드입니다.

`BUILD_MANIFEST.json`은 입력·도구·소스 및 단계별 해시를 기록하고, `EXPECTED_WRITES.json`은 OPT16 이후의 정확한 쓰기 범위와 원소유 스트림을 연결합니다. 새 그림이 원래 압축 길이를 넘으면 실제 소비가 끝난 스트림만 재배치·재압축합니다. 객체 사이 패딩이나 단순한 빈 바이트는 소유 공간으로 간주하지 않습니다.

빌드와 누적 BPS 재적용 성공은 실기·자연 진행·저장 및 최종 독립 감사의 통과를 뜻하지 않습니다. [현재 상태](V13_RC_STATUS.md)를 확인하세요. 최종 사용자는 일본판에 공개 BPS를 한 번 적용하며 구판 IPS를 먼저 적용하지 않습니다.

## v1.3 패키지 검사

현재 커밋과 깨끗한 빌드 결과를 고정한 뒤 검수용 공개 자산을 별도 새 폴더에 만듭니다. `--commit`에는 실제 빌드 소스의40자리 커밋을 지정합니다. 아직 필수 게이트가 남았다면 `--review-only`를 사용하며 결과 manifest는 미발행 상태를 명시합니다.

```powershell
python -X utf8 tools/package_v13.py --j '일본판.gba' --build output/v1.3-build --commit '<40-character-source-commit>' --out output/v1.3-package-review --review-only
python -X utf8 tools/verify_v13_package.py --package output/v1.3-package-review --j '일본판.gba' --wrong-base '기존한국어판.gba' --out output/v1.3-package-verification
```

ZIP의 명시된 파일 목록과 중첩 압축 여부, 단독/동봉 BPS 동일성, 실제 동봉 적용기의16MiB 생성, 잘못된 원본·손상 패치 거부와 기존 결과 보호를 검사합니다. 이 검증 출력에는 로컬 적용 ROM이 생기므로 검수 폴더를 공개하지 않습니다. 정식 패키징 모드에는 후보·소스 커밋에 묶인 모든 필수 게이트와 최종 감사 GO가 필요합니다. `--gates`로 로컬 근거 파일을 지정하며 공개 manifest에는 허용된 공개 요약만 들어갑니다. 사용자 종합 회신과 기기·로더·개별 결과 UNKNOWN, 에이전트 실기 NOT_RUN은 gate_details에 구분합니다. 실제 원격 발행·다운로드 재검증은 별도 단계입니다.

## v1.2 기록

이 절차는 v1.2 공개 패키지를 재현·검사하기 위한 개발자 안내입니다. 최종 사용자는 일본판 ROM에 BPS를 바로 적용하며, 1.1 IPS를 선행 적용하지 않습니다.

## 준비 입력

- Windows, 검증된 Python 환경과 `requirements-dev.txt` 의존성
- 같은 도구 폴더의 `arm-none-eabi-as.exe`, `ld.exe`, `objcopy.exe`, `objdump.exe`, `nm.exe`
- 별도로 준비한 일본판 B3TJ ROM. 크기 16,777,216 bytes, SHA-256 `d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394`
- 기존 한국어 1.1 패치 입력 `ToWN3(K) 1.1.ips`. 크기 504,608 bytes, SHA-256 `207e69c0617997ff410ee769030e9ea4e1dcc7f6500dde93e7154cd9a859179a`

개발 빌드는 일본판과 IPS로 확인한 기준 ROM을 복원한 뒤 v1.2 변경을 생성합니다. 기존 한국어 ROM을 빌드 입력으로 사용하지 마세요. 공개 패치는 일본판에 직접 적용하는 누적 BPS입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 빌드

프로젝트 폴더에서 입력 경로와 toolchain 폴더를 실제 위치로 바꾸고 매 빌드마다 새 출력 폴더를 지정합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/build_development.py --j '일본판.gba' --ips 'ToWN3(K) 1.1.ips' --toolchain 'C:\도구\gcc-arm-none-eabi\bin' --out output/v1.2-build --dialogue-review qa/dialogue-review-book-20260920.json --monster-descriptions --deduplicate-dialogue --dialogue-pool review
```

빌드는 현재 번역·프로필·코드 소스를 반영하며 일본판 및 1.1 IPS 해시를 검사합니다. 대사 검토 자료는 명시적으로 선택한 review pool로 빌드합니다. 기존 결과를 덮어쓰지 않도록 새로운 출력 경로를 사용하세요. `--help`로 현재 인자를 확인할 수 있습니다.

## 런타임 확인

mGBA와 VBA-Next의 libretro core 경로를 실제 환경에 맞게 지정합니다. 첫 실행과 새 프로세스 재실행 결과를 별도 폴더에 남깁니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/verify_runtime_smoke.py --rom output/v1.2-build/ND3_B3TJ_K_v1.2.gba --core 'C:\도구\mgba_libretro.dll' --out output/runtime-mgba
.\.venv\Scripts\python.exe -X utf8 tools/verify_runtime_smoke.py --rom output/v1.2-build/ND3_B3TJ_K_v1.2.gba --core 'C:\도구\vba_next_libretro.dll' --out output/runtime-vba
```

자동 입력 결과와 캡처 직접 확인은 구분합니다. 완료한 회귀 검증에서는 mGBA와 VBA-Next에서 신규 첫 저장, 별도 실행 재로드, 메뉴 및 아이템 설명을 확인하고 코어별 4개 캡처를 직접 검사했습니다. 두 코어의 첫 전투 조작 경로와 mGBA 타이틀/스탭롤 캡처도 확인했습니다. 사용자 OLD 2DS/DSPico/GBARunner3 저장 이어하기 보고는 개발자가 재현한 검사로 계산하지 않습니다.

## 공개 패키징 및 ZIP 검사

빌드와 양쪽 코어 런타임 결과를 준비하고, 승인된 소스 커밋의 전체 SHA-1을 `--commit`에 지정합니다. `package_release.py --help`를 확인했으며 현재 필수 인자는 아래 명령과 같습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/package_release.py --j '일본판.gba' --build output/v1.2-build --runtime output/runtime-mgba --second-runtime output/runtime-vba --out output/v1.2-release --commit '<40-character-commit-sha>'
.\.venv\Scripts\python.exe -X utf8 tools/verify_package.py --archive output/ND3_Korean_v1.2.zip --j '일본판.gba' --wrong-base '기존한국어판.gba' --out output/v1.2-package-check
```

패키저는 ROM 해시·빌드 manifest·대사 검토 데이터·런타임 근거를 서로 연결하고 공개 BPS를 만들며 실제 적용 결과를 확인합니다. ROM은 공개 ZIP에 넣지 않습니다. ZIP 검증기는 압축을 풀어 동봉 적용기로 패치를 실제 적용하고, 잘못된 기반 ROM 거부와 기존 출력 보호, 내부 파일 목록을 확인합니다. BPS와 ZIP 체크섬은 `v1.2-SHA256SUMS.txt`에 기록합니다. 릴리스 전 체크아웃에서도 같은 입력과 도구로 재현한 결과 해시를 대조하세요.
