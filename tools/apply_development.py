"""Apply a verified cumulative BPS package to the exact clean Japanese ROM."""
import argparse,hashlib,json
from pathlib import Path
from bps import apply_bps

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser(description='ND3 한국어 패치를 지원하는 일본판 원본에 적용합니다.')
    p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    source=a.source.read_bytes()
    if len(source)!=m['source_size'] or sha(source)!=m['source_sha256']:raise ValueError('지원하는 B3TJ 일본판 원본과 일치하지 않습니다.')
    patch=(root/m['patch_file']).read_bytes()
    if sha(patch)!=m['patch_sha256']:raise ValueError('패치 파일 검증 실패')
    target=apply_bps(source,patch)
    if len(target)!=m['target_size'] or sha(target)!=m['target_sha256']:raise ValueError('결과 ROM 검증 실패')
    with a.output.open('xb') as f:f.write(target)
    print('패치 적용 및 SHA-256 검증 완료.')
if __name__=='__main__':main()
