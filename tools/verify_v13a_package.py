"""Exercise the packaged applier and inspect the complete v1.3a public asset set."""
import argparse,hashlib,io,json,re,subprocess,sys,zipfile
from pathlib import Path
from package_v13a import SOURCES,JP,RC,BPS
sha=lambda b:hashlib.sha256(b).hexdigest()

def verify_metadata(inner, external, version, target_sha, patch_sha, expected_members=None):
    """Bind every shared public field, then check immutable release identities."""
    extras = {'zip_file', 'zip_sha256', 'zip_bytes', 'members', 'public_assets'}
    if (extras & inner.keys() or external.keys() != inner.keys() | extras
            or any(external[key] != value for key, value in inner.items())):
        raise ValueError('ZIP/external metadata binding')
    patch = f'ND3_B3TJ_K_v{version}_FROM_J.bps'
    expected = dict(version=version, source_sha256=JP, source_size=0x1000000,
                    target_sha256=target_sha, target_size=0x1000000,
                    patch_sha256=patch_sha, patch_file=patch)
    if any(inner.get(key) != value for key, value in expected.items()):
        raise ValueError('Release profile metadata binding')
    assets = [patch, f'ND3_Korean_v{version}.zip',
              f'v{version}-release-manifest.json', f'v{version}-SHA256SUMS.txt']
    if external['zip_file'] != assets[1] or external['public_assets'] != assets:
        raise ValueError('Public asset name binding')
    if expected_members is not None and (
            not isinstance(external['members'], dict) or set(external['members']) != expected_members):
        raise ValueError('External member inventory differs from ZIP allowlist')


def verify_checksums(package, version):
    """Require one valid digest for each of the three checksummed assets."""
    expected = {f'ND3_B3TJ_K_v{version}_FROM_J.bps', f'ND3_Korean_v{version}.zip',
                f'v{version}-release-manifest.json'}
    seen = set()
    for line in (package/f'v{version}-SHA256SUMS.txt').read_text('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if match is None:
            raise ValueError('Public checksum syntax')
        digest, name = match.groups()
        if name not in expected or name in seen or sha((package/name).read_bytes()) != digest:
            raise ValueError('Public checksum identity or duplicate')
        seen.add(name)
    if seen != expected:
        raise ValueError('Incomplete public checksum set')


def main(version='1.3a', profile=None, sources=None):
    target_sha, patch_sha = (profile['target_sha256'], profile['patch_sha256']) if profile else (RC, BPS)
    package_sources = sources or SOURCES
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--j',type=Path,required=True);p.add_argument('--wrong-base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('Fresh verification directory required')
    m=json.loads((a.package/f'v{version}-release-manifest.json').read_text('utf-8'));archive=a.package/f'ND3_Korean_v{version}.zip'
    if sha(archive.read_bytes())!=m['zip_sha256'] or archive.stat().st_size!=m['zip_bytes'] or sha(a.j.read_bytes())!=JP or sha(a.wrong_base.read_bytes())==JP:raise ValueError('Package or test input identity')
    verify_checksums(a.package, version)
    expected=set(package_sources)|{f'ND3_B3TJ_K_v{version}_FROM_J.bps','manifest.json'}
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if set(names)!=expected or len(names)!=len(expected):raise ValueError('Unexpected/duplicate ZIP member')
        for name in names:
            if '/' in name or '\\' in name or ':' in name or name in ['.','..']:raise ValueError('Package path traversal')
            data=z.read(name);row=m['members'][name]
            if len(data)!=row['bytes'] or sha(data)!=row['sha256'] or zipfile.is_zipfile(io.BytesIO(data)):raise ValueError('Payload identity or nested archive')
            if name=='logo.png':
                if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Logo format')
            elif name.endswith('.bps'):
                if sha(data)!=patch_sha or data!=(a.package/name).read_bytes():raise ValueError('Standalone and ZIP BPS differ')
            elif re.search(rb'C:[/\\]Users[/\\]|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',data):raise ValueError('Private text')
        a.out.mkdir(parents=True);z.extractall(a.out)
    inner=json.loads((a.out/'manifest.json').read_text('utf-8'))
    verify_metadata(inner, m, version, target_sha, patch_sha, expected)
    def apply(src,dst):return subprocess.run([sys.executable,'-X','utf8',str(a.out/'apply_development.py'),str(src.resolve()),'--output',str(dst.resolve())],capture_output=True)
    output=a.out/'applied.gba';result=apply(a.j,output)
    if result.returncode or output.stat().st_size!=0x1000000 or sha(output.read_bytes())!=target_sha:raise ValueError('Actual included applier result')
    before=sha(output.read_bytes())
    if apply(a.j,output).returncode==0 or sha(output.read_bytes())!=before:raise ValueError('Output overwrite protection')
    rejected=a.out/'wrong-base.gba'
    if apply(a.wrong_base,rejected).returncode==0 or rejected.exists():raise ValueError('Wrong Japanese base protection')
    patch=a.out/f'ND3_B3TJ_K_v{version}_FROM_J.bps';data=bytearray(patch.read_bytes());data[0]^=1;patch.write_bytes(data);rejected=a.out/'corrupted-patch.gba'
    if apply(a.j,rejected).returncode==0 or rejected.exists():raise ValueError('Corrupted patch protection')
    report=dict(status='PUBLIC_ASSET_CONTENT_AND_ACTUAL_APPLIER_PASS_RELEASE_GATES_SEPARATE',source_commit=m['source_commit'],candidate_sha256=target_sha,zip_sha256=m['zip_sha256'],patch_sha256=patch_sha,package_status=m['status'],member_count=len(expected),exact_allowlist=True,standalone_zip_patch_equal=True,actual_bundled_applier_exact_16MiB=True,wrong_base_rejected_without_output=True,existing_output_preserved=True,corrupt_patch_rejected_without_output=True,nested_archives=0,ROM_BIOS_SAV_font_binary_in_public_assets=False,limits=['The extracted verifier folder contains a local applied ROM and is private.','Package validation does not satisfy hardware or final auditor gates.'])
    (a.out/'PACKAGE_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n','utf-8');print(json.dumps(report))
if __name__=='__main__':main()
