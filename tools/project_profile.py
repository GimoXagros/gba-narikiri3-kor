"""User-selected release identity, independent of development build numbers."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def project():
    value=json.loads((ROOT/'project.json').read_text(encoding='utf-8'))
    if value['schema']!=1 or value['version'] not in ('1.1a','1.2'):raise ValueError('Unsupported project/version selection')
    for field in ['rom_file','patch_file']:
        if Path(value[field]).name!=value[field] or '/' in value[field] or '\\' in value[field]:raise ValueError('Invalid output filename')
    return value

def rom_path(directory,manifest):
    return directory/manifest.get('rom_file','nd3-dynamic-small-EXPERIMENT.gba')
