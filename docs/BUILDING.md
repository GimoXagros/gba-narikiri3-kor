# 누적 개발판 재현

이 절차는 번역 초안과 조사 중인 표시 기능을 포함한 개발판을 만든다. 모든 검사를 통과해도 전체 게임 번역·검수·실기 호환 완료를 뜻하지 않는다.

## 준비

Windows와 Python 3.14에서 확인했다. 다른 Python 버전·운영체제에서의 도구 실행은 별도 확인이 필요하다. ARM binutils의 `arm-none-eabi-as.exe`, `ld.exe`, `objcopy.exe`, `objdump.exe`, `nm.exe`가 같은 폴더에 있어야 한다.

프로젝트 폴더에서 다음 명령으로 가상 환경과 검사 패키지를 준비한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

게임 파일은 사용자가 별도로 준비한다. 두 입력 모두 빌드 시작 시 정확한 SHA-256을 검사한다.

| 입력 | 크기 | SHA-256 |
|---|---:|---|
| B3TJ 일본판 | 16777216 | d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394 |
| 기존 한국어 1.1 IPS | 504608 | 207e69c0617997ff410ee769030e9ea4e1dcc7f6500dde93e7154cd9a859179a |

기존 한국어 ROM은 빌드 입력으로 사용하지 않는다. 일본판과 IPS로 재구성한 결과가 기존 한국어 1.1 해시와 일치해야 다음 단계로 진행한다.

## 만들기와 CPU 검사

경로는 실제 입력 위치로 바꾸고, 출력 폴더는 매번 새 이름을 지정한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/build_development.py --j '일본판.gba' --ips 'ToWN3(K) 1.1.ips' --toolchain 'C:\도구\gcc-arm-none-eabi\bin' --out output/reproduce-01
```

이 명령은 현재 선택한 번역 JSON, 달무리 2350자, 소형 글꼴·이름 입력·의상 정렬·정보창의 Thumb 소스와 UI/그래픽 참조 규칙을 하나의 32 MiB 결과에 반영한다. 원본 영역의 선언되지 않은 변경, 원래 글꼴 변경, 참조 원본 불일치, 글자·배치·포맷 조건 위반은 실패한다. 추출 후보 검색이나 초안 생성 절차는 빌드 중에 실행하지 않는다.

실제 결과의 소형 출력·이름 입력·저장 소비자, 910개 이름, UI 72개와 팀 표 54개, 대사·요리·소개·설명·그래픽 등 채택한 영역별 검사를 수행한다. 검사별 JSON은 결과 ROM 해시에 연결된다. `reproduction.json`에는 도구·소스·번역·라이브러리 버전과 해시를 기록한다. 비교용 한국어 ROM도 출력 폴더 안에 생성되며 공개 산출물에는 넣지 않는다. 원래 글자 비트와 독립 비교하는 아이템 설명 검사 결과도 꾸러미의 필수 조건이다.

## 정상 입력과 저장 재실행 확인

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/verify_runtime_smoke.py --rom output/reproduce-01/ND3_B3TJ_K_v1.1a.gba --core 'C:\도구\mgba_libretro.dll' --out output/runtime-reproduce-01
```

`qa/traces`의 입력 기록으로 새 게임부터 첫 저장까지 진행하고, 별도 프로세스에서 그 EEPROM 저장을 불러온다. 이어서 메뉴와 초기 아이템 목록·설명을 촬영한다. RAM 조작은 사용하지 않는다. 게임 합계 검사값, 시간 이외 전체 8192 bytes의 상태 및 관찰한 ±3프레임 시간 범위를 검사한다. 실제 시간차는 보고서에 남기며, 범위나 상태가 달라지면 임의 해시 갱신 없이 원인을 조사한다. 근거는 docs/PC_VERIFICATION.md에 기록했다.

결과의 `VISUAL_INSPECTION_PENDING`은 캡처를 직접 확인해야 한다는 뜻이다. 입력 재생 성공만으로 화면 도달이나 번역 표시 성공을 확정하지 않는다. 재생 도구는 전투·분기·엔딩·전체 사용자 저장·실기 검증을 수행하지 않는다.

## 개발 검토 꾸러미

CPU 검사, 정확한 ROM에 연결된 실행 기록과 화면 관찰 기록을 준비한 뒤 생성한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/package_development.py --j '일본판.gba' --build output/reproduce-01 --runtime output/runtime-reproduce-01 --out output/개발검토판_새이름
```

꾸러미에는 BPS, 적용기, 안내와 검증 기록·라이선스만 들어간다. BPS를 일본판에 적용한 결과가 빌드와 같은지 검사한다. 최종적으로 ZIP을 별도 폴더에 풀어 동봉 적용기로 같은 결과를 만드는 것까지 확인한다. GitHub 공개·최종 릴리즈는 이 절차에 포함되지 않는다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/verify_package.py --archive output/개발검토판_새이름.zip --j '일본판.gba' --wrong-base '기존한국어판.gba' --out output/package-check-새이름
```

이 검사는 실제 동봉 적용기, 잘못된 원본 거부, 기존 출력 보호, ROM·저장 미포함을 확인한다. 저장소의 `.gitattributes`는 줄바꿈 자동 변환을 끄므로 체크아웃 과정에서 입력·증거 파일의 해시가 달라지지 않는다.
