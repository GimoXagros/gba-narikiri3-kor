"""Package only the hash-bound v1.3b candidate with its completed release gates."""
import json
from pathlib import Path
from package_v13a import main, SOURCES

if __name__ == '__main__':
    profile = json.loads((Path(__file__).resolve().parents[1]/'source/v13b/release_profile.json').read_text('utf8'))
    main('1.3b', profile, SOURCES | {
        '먼저_읽어주세요.md': 'docs/RELEASE_README_V1_3B.md',
        '검증_요약.md': 'docs/FINAL_VALIDATION_V1_3B.md'})
