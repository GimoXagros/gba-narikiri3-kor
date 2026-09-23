"""Build the public v1.2 allowlist after exact-ROM build and PC evidence gates."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from bps import apply_bps, create_bps
from build_visibility_poc import J
from package_prerelease import second_pc
from project_profile import project, rom_path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ('j', 'build', 'runtime', 'second-runtime', 'out', 'commit'):
        p.add_argument('--' + name, required=True, type=Path if name != 'commit' else str)
    a = p.parse_args()
    identity = project()
    if identity['version'] != '1.2' or identity['stage'] != 'public-release':
        raise ValueError('This package requires the v1.2 public release identity')
    if len(a.commit) != 40 or any(c not in '0123456789abcdef' for c in a.commit.lower()):
        raise ValueError('Commit must be an exact 40-character Git SHA')
    stage = a.out.parent / (a.out.name + '-validated-local')
    subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tools/package_development.py'),
                    '--j', str(a.j), '--build', str(a.build), '--runtime', str(a.runtime),
                    '--out', str(stage)], cwd=ROOT, check=True)
    built = json.loads((a.build / 'manifest.json').read_text(encoding='utf-8'))
    first = json.loads((a.runtime / 'runtime.json').read_text(encoding='utf-8'))
    second = second_pc(a.second_runtime, built['target_sha256'], first['core_sha256'])
    audit = json.loads((a.build / 'dialogue-audit-verification.json').read_text(encoding='utf-8'))
    reproduction = json.loads((a.build / 'reproduction.json').read_text(encoding='utf-8'))
    ledger = ROOT / 'qa/dialogue-review-book-20260920.json'
    if audit['status'] != 'PASS' or audit['rom_sha256'] != built['target_sha256'] or audit['ledger_sha256'] != sha(ledger):
        raise ValueError('Final dialogue audit and adopted ledger do not match the build')
    source = a.j.read_bytes()
    target = rom_path(a.build, built).read_bytes()
    if hashlib.sha256(source).hexdigest() != J or hashlib.sha256(target).hexdigest() != built['target_sha256']:
        raise ValueError('Source/target identity mismatch')
    patch = create_bps(source, target, b'ND3 B3TJ cumulative Korean patch v1.2')
    if apply_bps(source, patch) != target:
        raise ValueError('BPS application differs from verified build')
    a.out.mkdir(parents=True, exist_ok=False)
    patch_path = a.out / identity['patch_file']
    patch_path.write_bytes(patch)
    build_checks = {path.name: json.loads(path.read_text(encoding='utf-8'))['status']
                    for path in sorted(a.build.glob('*-verification.json'))}
    allowed_statuses = {'PASS', 'PROTECTED_NON_TEXT_IDENTICAL',
                        'SCOPED_GRAPHICS_EDGE_CLASSIFICATION_PASS',
                        'SCOPED_INACTIVE_PATH_CLASSIFICATION_PASS'}
    if not build_checks or any(status not in allowed_statuses for status in build_checks.values()):
        raise ValueError('A build verification is missing or failed')
    manifest = {
        'status': 'V1.2_SCOPED_RELEASE_VERIFIED', 'version': '1.2',
        'commit': a.commit.lower(), 'source_size': len(source), 'source_sha256': J,
        'target_size': len(target), 'target_sha256': hashlib.sha256(target).hexdigest(),
        'patch_file': patch_path.name, 'patch_sha256': sha(patch_path),
        'bps_roundtrip': True, 'rom_included': False,
        'legacy_ips_sha256': sha(ROOT / 'ToWN3(K) 1.1.ips'),
        'dialogue_ledger_sha256': sha(ledger),
        'dialogue_audit': {key: audit[key] for key in ('reviewed_typed_records',
                            'correction_groups', 'corrected_records')},
        'reproduction': reproduction,
        'runtime': {'mgba_core_sha256': first['core_sha256'],
                    'second_core_sha256': second['runtime']['core_sha256'],
                    'first_save_reload': True, 'visual_observation': 'EXPECTED_SCREENS_OBSERVED'},
        'build_verification': build_checks,
        'limits': built['limits'],
    }
    (a.out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for src, dst in (
        ('tools/apply_development.py', 'apply_development.py'),
        ('tools/bps.py', 'bps.py'),
        ('fonts/LICENSE.dalmoori', 'LICENSE.dalmoori'),
        ('docs/LICENSE.nd2-tools', 'LICENSE.nd2-tools'),
        ('CREDITS.md', 'CREDITS.md'),
        ('docs/RELEASE_README_V1_2.md', '먼저_읽어주세요.md'),
        ('docs/RELEASE_NOTES_V1_2.md', '릴리스_노트.md'),
    ):
        shutil.copyfile(ROOT / src, a.out / dst)
    archive = a.out.parent / 'ND3_Korean_v1.2.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(a.out.iterdir()):
            if path.suffix.lower() not in ('.md', '.json', '.py', '.bps', '.dalmoori', '.nd2-tools'):
                raise ValueError('Unexpected public member type')
            z.write(path, path.name)
    sums = a.out.parent / 'v1.2-SHA256SUMS.txt'
    sums.write_text(f'{sha(patch_path)}  {patch_path.name}\n{sha(archive)}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'status': 'PASS', 'rom_sha256': manifest['target_sha256'],
                      'patch_sha256': sha(patch_path), 'zip_sha256': sha(archive),
                      'second_pc_core_sha256': second['runtime']['core_sha256']}))


if __name__ == '__main__':
    main()
