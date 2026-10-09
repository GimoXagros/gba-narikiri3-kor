"""Exercise the packaged applier and inspect the complete v1.3 public asset set."""
import argparse,hashlib,io,json,re,subprocess,sys,zipfile
from pathlib import Path
from package_v13 import SOURCES,JP,RC,BPS
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--j',type=Path,required=True);p.add_argument('--wrong-base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('Fresh verification directory required')
    m=json.loads((a.package/'v1.3-release-manifest.json').read_text('utf-8'));archive=a.package/'ND3_Korean_v1.3.zip'
    if sha(archive.read_bytes())!=m['zip_sha256'] or sha(a.j.read_bytes())!=JP or sha(a.wrong_base.read_bytes())==JP:raise ValueError('Package or test input identity')
    expected=set(SOURCES)|{'ND3_B3TJ_K_v1.3_FROM_J.bps','manifest.json'}
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
                if sha(data)!=BPS or data!=(a.package/name).read_bytes():raise ValueError('Standalone and ZIP BPS differ')
            elif re.search(rb'C:[/\\]Users[/\\]|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',data):raise ValueError('Private text')
        a.out.mkdir(parents=True);z.extractall(a.out)
    inner=json.loads((a.out/'manifest.json').read_text('utf-8'))
    if inner['target_sha256']!=RC or inner['target_size']!=0x1000000 or inner['status']!=m['status'] or inner['source_commit']!=m['source_commit']:raise ValueError('ZIP/external metadata binding')
    for line in (a.package/'v1.3-SHA256SUMS.txt').read_text('ascii').splitlines():
        digest,name=line.split('  ',1)
        if name not in ['ND3_B3TJ_K_v1.3_FROM_J.bps','ND3_Korean_v1.3.zip','v1.3-release-manifest.json'] or sha((a.package/name).read_bytes())!=digest:raise ValueError('Public checksum identity')
    def apply(src,dst):return subprocess.run([sys.executable,'-X','utf8',str(a.out/'apply_development.py'),str(src.resolve()),'--output',str(dst.resolve())],capture_output=True)
    output=a.out/'applied.gba';result=apply(a.j,output)
    if result.returncode or output.stat().st_size!=0x1000000 or sha(output.read_bytes())!=RC:raise ValueError('Actual included applier result')
    before=sha(output.read_bytes())
    if apply(a.j,output).returncode==0 or sha(output.read_bytes())!=before:raise ValueError('Output overwrite protection')
    rejected=a.out/'wrong-base.gba'
    if apply(a.wrong_base,rejected).returncode==0 or rejected.exists():raise ValueError('Wrong Japanese base protection')
    patch=a.out/'ND3_B3TJ_K_v1.3_FROM_J.bps';data=bytearray(patch.read_bytes());data[0]^=1;patch.write_bytes(data);rejected=a.out/'corrupted-patch.gba'
    if apply(a.j,rejected).returncode==0 or rejected.exists():raise ValueError('Corrupted patch protection')
    report=dict(status='PUBLIC_ASSET_CONTENT_AND_ACTUAL_APPLIER_PASS_RELEASE_GATES_SEPARATE',source_commit=m['source_commit'],candidate_sha256=RC,zip_sha256=m['zip_sha256'],patch_sha256=BPS,package_status=m['status'],member_count=len(expected),exact_allowlist=True,standalone_zip_patch_equal=True,actual_bundled_applier_exact_16MiB=True,wrong_base_rejected_without_output=True,existing_output_preserved=True,corrupt_patch_rejected_without_output=True,nested_archives=0,ROM_BIOS_SAV_font_binary_in_public_assets=False,limits=['The extracted verifier folder contains a local applied ROM and is private.','Package validation does not satisfy hardware or final auditor gates.'])
    (a.out/'PACKAGE_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n','utf-8');print(json.dumps(report))
if __name__=='__main__':main()
