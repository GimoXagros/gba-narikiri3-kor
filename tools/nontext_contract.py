"""Protected B3TJ data spans, independently identified through their consumers."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def protected_regions(rom):
    profile=json.loads((ROOT/'source/nontext_profile.json').read_text(encoding='utf-8'))
    results=[]
    for record in profile['regions']:
        start,end=int(record['start'],0),int(record['end'],0)
        actual=hashlib.sha256(rom[start:end]).hexdigest()
        if len(rom)<end or actual!=record['sha256']:
            raise ValueError(f"Protected non-text region changed: {record['id']}")
        results.append({'id':record['id'],'bytes':end-start,'sha256':actual})
    return results
