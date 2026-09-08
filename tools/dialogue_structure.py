"""The indexed B3TJ dialogue VM resource, proven independently of text scans."""
import hashlib,json,struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def source_records(j,legacy):
    profile=json.loads((ROOT/'source/dialogue_profile.json').read_text(encoding='utf-8'))
    if hashlib.sha256(j).hexdigest()!=profile['source_sha256'] or hashlib.sha256(legacy).hexdigest()!=profile['legacy_sha256']:
        raise ValueError('Wrong immutable dialogue source')
    base=int(profile['table_offset'],0);end=int(profile['table_end'],0)
    if end-base!=profile['table_count']*4 or len(profile['streams'])!=profile['table_count']:
        raise ValueError('Invalid dialogue table boundary')
    for rom in (j,legacy):
        if hashlib.sha256(rom[base:end]).hexdigest()!=profile['table_sha256']:raise ValueError('Script pointer table differs')
        for g in profile['consumer_guards']:
            off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
            if rom[off:off+len(raw)]!=raw:raise ValueError('Dialogue structure consumer differs')
    result=[];occupied=set()
    for i,stream in enumerate(profile['streams']):
        start=int(stream['start'],0);stop=int(stream['end'],0)
        if stream['index']!=i or struct.unpack_from('<I',j,base+i*4)[0]!=0x08000000+start or (stop-start)%8:
            raise ValueError('Script index/stride differs')
        if not 0x100000<=start<stop<=0x1c4000:raise ValueError('Script outside adopted resource area')
        for rom in (j,legacy):
            if hashlib.sha256(rom[start:stop]).hexdigest()!=stream['sha256']:raise ValueError('Immutable VM instructions differ')
        for off in range(start,stop,8):
            if off in occupied:raise ValueError('Script instruction ranges overlap')
            occupied.add(off)
            opcode,speaker,ptr=struct.unpack_from('<HHI',j,off)
            if not 1<=opcode<=49 or (opcode==49)!=(off==stop-8):raise ValueError('Invalid opcode/termination')
            if opcode in profile['dialogue_opcodes']:result.append({'script_index':i,'record_offset':off,'opcode':opcode,'speaker':speaker,'pointer':ptr})
    # A text pointer must never land inside any adopted instruction, including
    # its operands. Resource membership is established before decoding text.
    for row in result:
        ptr=row['pointer']-0x08000000
        if not 0x100000<=ptr<0x1c4000 or any(ptr-n in occupied for n in range(8)):
            raise ValueError('Dialogue payload points into instructions/non-resource data')
    return result
