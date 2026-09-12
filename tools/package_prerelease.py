"""Publishable experimental prerelease: validated patch, review and evidence only.

The underlying build remains an experiment. A GitHub prerelease is not a
release-candidate or 100%-completion claim. Reuse the development packager's
source, BPS, CPU and first-PC verification gates before preparing this archive.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitized(value):
    if isinstance(value, dict):
        return {k: sanitized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitized(v) for v in value]
    if isinstance(value, str) and re.match(r'^[A-Za-z]:[/\\]', value):
        return value.replace('\\', '/').rsplit('/', 1)[-1]
    return value


def second_pc(path, target_hash, first_core):
    r = json.loads((path/'runtime.json').read_text(encoding='utf-8'))
    v = json.loads((path/'visual-observation.json').read_text(encoding='utf-8'))
    if r['rom_sha256'] != target_hash or v['rom_sha256'] != target_hash:
        raise ValueError('Second PC evidence is for a different ROM')
    if r['core_sha256'] == first_core or r['core_sha256'] != v['core_sha256']:
        raise ValueError('Second PC must use a separately identified core')
    if r['status'] != 'REPLAY_AND_SAVE_CHECKS_PASS_VISUAL_INSPECTION_PENDING' or v['status'] != 'EXPECTED_SCREENS_OBSERVED':
        raise ValueError('Second PC replay/visual checks incomplete')
    if r['ram_interventions'] or not r['separate_process_reload']:
        raise ValueError('Second PC used state intervention or lacks a clean reload')
    captures = [c for phase in r['phases'].values() for c in phase['captures']]
    if {c['sha256'] for c in captures} != {c['sha256'] for c in v['captures']}:
        raise ValueError('Unreviewed second-PC captures')
    for c in captures:
        if sha(Path(c['path'])) != c['sha256']:
            raise ValueError('Second-PC capture changed')
    save = r['phases']['first-save']['save']
    if save['fixture_modified'] or save['size'] != 8192 or sha(Path(save['path'])) != save['sha256'] or r['phases']['reload']['input_save_sha256'] != save['sha256']:
        raise ValueError('Second-PC save chain differs')
    return {'runtime': r, 'visual_observation': v}


def main():
    p = argparse.ArgumentParser()
    for name in ('j', 'build', 'runtime', 'second-runtime', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    stage = a.out.parent/(a.out.name+'-validated-local')
    subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'tools/package_development.py'),
                    '--j', str(a.j), '--build', str(a.build), '--runtime', str(a.runtime),
                    '--out', str(stage)], check=True, cwd=ROOT)
    manifest = json.loads((stage/'manifest.json').read_text(encoding='utf-8'))
    review = json.loads((a.build/'dialogue-audit-verification.json').read_text(encoding='utf-8'))
    if review['status'] != 'PASS' or review['rom_sha256'] != manifest['target_sha256'] or review['ledger_sha256'] != sha(ROOT/'qa/dialogue-review-v1.1a.json'):
        raise ValueError('Semantic review ledger is not bound to this artifact')
    first = json.loads((a.runtime/'runtime.json').read_text(encoding='utf-8'))
    other = second_pc(a.second_runtime, manifest['target_sha256'], first['core_sha256'])
    a.out.mkdir(parents=True, exist_ok=False)
    for path in stage.iterdir():
        if path.is_file():
            shutil.copyfile(path, a.out/path.name)
    manifest.update(status='EXPERIMENTAL_PRERELEASE_NOT_100_PERCENT', version='1.1a',
                    underlying_build_status='EXPERIMENT_NOT_RELEASE',
                    semantic_review=review, github_prerelease=True,
                    claim='Full known dialogue comparison and scoped PC verification. No full-game or all-platform error-free claim.')
    (a.out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for source, dest in [('docs/PRERELEASE_README.md', '먼저_읽어주세요.md'),
                         ('docs/DIALOGUE_REVIEW_V1_1A.md', '대사_수정_리포트.md'),
                         ('qa/dialogue-review-v1.1a.json', 'dialogue-review-v1.1a.json')]:
        shutil.copyfile(ROOT/source, a.out/dest)
    shutil.copyfile(a.build/'dialogue-audit-verification.json', a.out/'dialogue-audit-verification.json')
    (a.out/'second-pc-verification.json').write_text(json.dumps(other, ensure_ascii=False, indent=2), encoding='utf-8')
    for path in a.out.glob('*.json'):
        path.write_text(json.dumps(sanitized(json.loads(path.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    archive = a.out.parent/(a.out.name+'.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(a.out.iterdir()):
            if path.suffix.lower() not in ('.md', '.json', '.py', '.bps', '.dalmoori', '.nd2-tools'):
                raise ValueError('Unexpected publishable file type')
            z.write(path, path.name)
    print(json.dumps({'archive': str(archive), 'sha256': sha(archive), 'rom_included': False, 'target_sha256': manifest['target_sha256']}))


if __name__ == '__main__':
    main()
