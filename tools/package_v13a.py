"""Explicit source-bound v1.3a user package; gate-free output is review only."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
from bps import apply_bps

ROOT=Path(__file__).resolve().parents[1]
JP='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394'
PROFILE=json.loads((ROOT/'source/v13a/release_profile.json').read_text('utf8'))
RC=PROFILE['target_sha256']
BPS=PROFILE['patch_sha256']
GATES=['SOURCE_QA','STATIC_BINARY_QA','RC_BUILD','RC_READBACK_QA','RUNTIME_SMOKE','boot_delay','reflow','preservation','clean_reproduction_package','public_tree_archive','hardware','final_auditor']
SOURCES={'apply_development.py':'tools/apply_development.py','bps.py':'tools/bps.py','CREDITS.md':'CREDITS.md','LICENSE.dalmoori':'fonts/LICENSE.dalmoori','LICENSE.nd2-tools':'docs/LICENSE.nd2-tools','logo.png':'logo.png','먼저_읽어주세요.md':'docs/RELEASE_README_V1_3A.md','검증_요약.md':'docs/FINAL_VALIDATION_V1_3A.md'}
sha=lambda b:hashlib.sha256(b).hexdigest()
def dump(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--j',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--commit',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--review-only',action='store_true');p.add_argument('--gates',type=Path);a=p.parse_args()
    if a.out.exists():p.error('Fresh package directory required')
    if not re.fullmatch('[0-9a-f]{40}',a.commit):p.error('Full exact source commit required')
    if git('rev-parse',a.commit+'^{commit}').decode().strip()!=a.commit:raise ValueError('Source commit identity')
    source=a.j.read_bytes();rom=(a.build/'ND3_B3TJ_K_v1.3a.gba').read_bytes();patch=(a.build/'ND3_B3TJ_K_v1.3a_FROM_J.bps').read_bytes();build=json.loads((a.build/'BUILD_MANIFEST.json').read_text('utf-8'))
    if len(source)!=0x1000000 or sha(source)!=JP or len(rom)!=0x1000000 or sha(rom)!=RC or sha(patch)!=BPS:raise ValueError('Exact source/candidate/patch binding')
    if build['ROM_sha256']!=RC or build['BPS_sha256']!=BPS or apply_bps(source,patch)!=rom:raise ValueError('Cumulative package roundtrip')
    for path,digest in build['source_sha256'].items():
        if sha(git('show',a.commit+':'+path))!=digest:raise ValueError('Build source differs from commit '+path)
    gate={name:'PENDING' for name in GATES};gate_sha=None;gate_details={}
    if a.gates:
        raw=a.gates.read_bytes();proof=json.loads(raw);gate_sha=sha(raw)
        if proof['candidate_sha256']!=RC or proof['source_commit']!=a.commit:raise ValueError('Gate candidate/commit binding')
        gate={name:proof['gates'][name]['status'] for name in GATES}
        # Only explicit public summaries enter assets; private evidence stays local.
        summary_keys=('public_summary','result_type','device','loader','individual_checklist_results','agent_hardware_execution','decision_authority')
        gate_details={name:{key:proof['gates'][name][key] for key in summary_keys if key in proof['gates'][name]} for name in GATES}
        if any(not isinstance(value,str) for row in gate_details.values() for value in row.values()):raise ValueError('Public gate summary strings required')
    if not a.review_only and any(gate[name]!=('GO' if name=='final_auditor' else 'DEFERRED_BY_USER' if name=='hardware' else 'PASS') for name in GATES):raise ValueError('Required v1.3a publication gates incomplete')
    if not a.review_only and (gate_details.get('hardware',{}).get('agent_hardware_execution')!='NOT_RUN' or gate_details.get('hardware',{}).get('decision_authority')!='USER_REQUESTED_POST_RELEASE_HARDWARE_VALIDATION'):raise ValueError('Hardware deferral must retain explicit user authority and NOT_RUN')
    status='UNPUBLISHED_REVIEW_REQUIRED_GATES_PENDING' if a.review_only else 'RELEASE_READY_GATES_BOUND_REMOTE_PUBLICATION_SEPARATE'
    public=dict(status=status,version='1.3a',source_commit=a.commit,source_tree=git('rev-parse',a.commit+'^{tree}').decode().strip(),source_size=len(source),source_sha256=JP,target_size=len(rom),target_sha256=RC,patch_file='ND3_B3TJ_K_v1.3a_FROM_J.bps',patch_sha256=BPS,legacy_ips_sha256='207e69c0617997ff410ee769030e9ea4e1dcc7f6500dde93e7154cd9a859179a',build_manifest_sha256=sha((a.build/'BUILD_MANIFEST.json').read_bytes()),toolchain_sha256=build['toolchain_sha256'],gates=gate,gate_evidence_sha256=gate_sha,bps_reapplication_exact=True,rom_bios_saves_included=False,limits=['Only the documented bounded PC checks are established.','Hardware/final audit status is recorded explicitly; no full-game or all-device guarantee.','The development legacy IPS is not a user prerequisite.'])
    public['gate_details']=gate_details
    members={name:git('show',a.commit+':'+path) for name,path in SOURCES.items()};members[public['patch_file']]=patch;members['manifest.json']=dump(public)
    for name,data in members.items():
        if '/' in name or '\\' in name or ':' in name:raise ValueError('Flat package member path')
        if name.endswith(('.gba','.sav','.srm','.zip','.ttf','.otf','.woff','.woff2')):raise ValueError('Forbidden public package type')
        if name!='logo.png' and name!=public['patch_file'] and re.search(rb'C:[/\\]Users[/\\]|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',data):raise ValueError('Private source text in user package')
    a.out.mkdir(parents=True);(a.out/public['patch_file']).write_bytes(patch)
    archive=a.out/'ND3_Korean_v1.3a.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(members.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data,compresslevel=9)
    external=dict(public,zip_file=archive.name,zip_sha256=sha(archive.read_bytes()),zip_bytes=archive.stat().st_size,members={name:dict(bytes=len(data),sha256=sha(data)) for name,data in sorted(members.items())},public_assets=[public['patch_file'],archive.name,'v1.3a-release-manifest.json','v1.3a-SHA256SUMS.txt'])
    (a.out/'v1.3a-release-manifest.json').write_bytes(dump(external))
    # No file contains its own checksum. ZIP hash is only in external manifest.
    names=[public['patch_file'],archive.name,'v1.3a-release-manifest.json'];(a.out/'v1.3a-SHA256SUMS.txt').write_text(''.join(sha((a.out/name).read_bytes())+'  '+name+'\n' for name in names),'ascii')
    print(status);print(sha(archive.read_bytes()))
if __name__=='__main__':main()
