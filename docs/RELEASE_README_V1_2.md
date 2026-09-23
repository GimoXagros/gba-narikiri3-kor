# 나리키리 던전 3 한국어 패치 v1.2 적용

이 ZIP에는 일본판 B3TJ 원본에 바로 적용하는 누적 BPS 패치와 검증된 적용기가 들어 있습니다. 원본 ROM과 기존 저장은 먼저 별도 복사본으로 백업하세요. 기존 한국어판이나 이미 패치된 ROM에는 적용하지 마세요.

지원하는 일본판 원본은 16,777,216 bytes, SHA-256 `d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394`입니다. Python 3가 설치된 폴더에서 ZIP을 모두 풀고 다음처럼 실행합니다.

```powershell
python -X utf8 apply_development.py '일본판.gba' --output 'ND3_B3TJ_K_v1.2.gba'
```

적용기는 원본, BPS, 결과 ROM의 해시를 확인하고 기존 결과 파일을 덮어쓰지 않습니다. 출력 ROM의 SHA-256은 동봉 `manifest.json`의 `target_sha256`과 일치해야 합니다. 게임 ROM, BIOS, 저장 파일은 ZIP에 포함되지 않습니다.

기존 저장을 이어 스탭롤까지 진행한 OLD 2DS/DSPico/GBARunner3 사례는 사용자의 보고입니다. 다른 저장 상태나 기기의 완전한 호환성 보증은 아닙니다. 변경 사항과 검사 범위는 `릴리스_노트.md`, 제작자와 출처는 `CREDITS.md`를 확인하세요.
