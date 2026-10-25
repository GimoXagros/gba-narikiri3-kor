"""Build v1.3a cumulatively from immutable Japanese ROM and legacy IPS inputs."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from bps import create_bps,apply_bps
from v13a_changes import build

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['j','ips','toolchain','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error('Fresh output directory required')
    j=a.j.read_bytes();ips=a.ips.read_bytes()
    if len(j)!=16777216 or sha(j)!='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394':raise ValueError('Unsupported Japanese ROM')
    if sha(ips)!='207e69c0617997ff410ee769030e9ea4e1dcc7f6500dde93e7154cd9a859179a':raise ValueError('Legacy IPS identity')
    a.out.mkdir(parents=True)
    baseline=a.out/'baseline'
    with (a.out/'baseline.log').open('w',encoding='utf8') as log:
        subprocess.run([sys.executable,'-X','utf8',ROOT/'tools/build_release.py','--j',a.j.resolve(),'--ips',a.ips.resolve(),'--toolchain',a.toolchain.resolve(),'--out',baseline.resolve()],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    base=(baseline/'ND3_B3TJ_K_v1.3_RC16.gba').read_bytes()
    target,ledger=build(base,a.toolchain,a.out/'assembly')
    if len(target)!=len(j):raise ValueError('ROM growth forbidden')
    patch=create_bps(j,target,b'ND3 v1.3a cumulative Korean patch; exact16MiB')
    if apply_bps(j,patch)!=target:raise ValueError('Cumulative BPS roundtrip')
    name='ND3_B3TJ_K_v1.3a'
    for filename,data in [(name+'.gba',target),(name+'_FROM_J.bps',patch)]:
        temp=a.out/(filename+'.partial');temp.write_bytes(data)
        if temp.read_bytes()!=data:raise ValueError('Final artifact readback')
        temp.rename(a.out/filename)
    paths=[ROOT/'project.json',ROOT/'requirements-dev.txt',*sorted((ROOT/'tools').glob('*.py')),*sorted((ROOT/'source').rglob('*')),*sorted((ROOT/'translations').glob('*.json')),*sorted((ROOT/'fonts').glob('*.json'))]
    source_hashes={f.relative_to(ROOT).as_posix():sha(f.read_bytes()) for f in paths if f.is_file()}
    parent=json.loads((baseline/'BUILD_MANIFEST.json').read_text('utf8'))
    report=dict(version='1.3a',status='RC_BUILD_AND_READBACK_PASS_RUNTIME_QA_SEPARATE',ROM_file=name+'.gba',ROM_bytes=len(target),ROM_sha256=sha(target),BPS_file=name+'_FROM_J.bps',BPS_sha256=sha(patch),source_sha256=source_hashes,input_sha256=dict(j=sha(j),ips=sha(ips)),toolchain_sha256=parent['toolchain_sha256'],baseline_sha256=sha(base),writes=ledger,bps_roundtrip_exact=True,hardware='NOT_RUN_USER_SCHEDULED_AFTER_RELEASE')
    (a.out/'BUILD_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n','utf8')
    if a.j.read_bytes()!=j or a.ips.read_bytes()!=ips:raise ValueError('Input mutation')
    print(report['ROM_sha256'],report['ROM_bytes'])

if __name__=='__main__':main()
