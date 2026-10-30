"""Verify the v1.3b archive and execute its bundled patch applier."""
import json
from pathlib import Path
from verify_v13a_package import main

if __name__ == '__main__':
    profile = json.loads((Path(__file__).resolve().parents[1]/'source/v13b/release_profile.json').read_text('utf8'))
    main('1.3b', profile)
