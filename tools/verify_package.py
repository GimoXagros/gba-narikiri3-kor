"""Exercise the actual ZIP's applier, supported base and no-overwrite rule."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--j',type=Path,required=True);p.add_argument('--wrong-base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(a.archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or any('/' in n or '\\' in n or ':' in n or n in ('.','..') for n in names):raise ValueError('Unexpected package member path')
        if any(Path(n).suffix.lower() not in ('.py','.json','.md','.bps','.dalmoori','.nd2-tools') for n in names):raise ValueError('Unexpected package member type')
        z.extractall(a.out)
    manifest=json.loads((a.out/'manifest.json').read_text(encoding='utf-8'))
    if sha(a.wrong_base)==manifest['source_sha256']:raise ValueError('Negative fixture is not a wrong base')
    def apply(base,target):
        return subprocess.run([sys.executable,'-X','utf8',str((a.out/'apply_development.py').resolve()),str(base.resolve()),'--output',str(target.resolve())],capture_output=True)
    result=a.out/'applied.gba'
    process=apply(a.j,result)
    if process.returncode or sha(result)!=manifest['target_sha256']:raise ValueError('Actual ZIP application differs')
    prior=sha(result)
    if apply(a.j,result).returncode==0 or sha(result)!=prior:raise ValueError('Existing output was not protected')
    rejected=a.out/'wrong-base-result.gba'
    if apply(a.wrong_base,rejected).returncode==0 or rejected.exists():raise ValueError('Unsupported base was not rejected before output')
    report={'status':'PASS','archive_sha256':sha(a.archive),'target_sha256':sha(result),'source_sha256':sha(a.j),'actual_included_applier_roundtrip':True,'wrong_base_rejected_without_output':True,'existing_output_rejected_without_change':True,'archive_has_no_rom_or_save':True,'member_count':len(names)}
    (a.out/'package-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
