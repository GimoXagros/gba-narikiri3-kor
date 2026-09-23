# v1.2 빌드 및 패키지 재현

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
