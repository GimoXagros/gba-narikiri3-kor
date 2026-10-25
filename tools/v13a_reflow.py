"""Apply explicit reviewed line-layout decisions without moving any string."""
from build_release import apply_writes
from v13a_changes import read,sha

def apply_reflow(rom):
    writes=[]
    for row in read('linebreaks.json'):
        at=int(row['pointer'],0)-0x08000000
        old=bytes.fromhex(row['old_hex']);new=bytes.fromhex(row['new_hex'])
        if rom[at:at+len(old)]!=old or len(old)!=len(new):raise ValueError('Reviewed break source mismatch')
        if old.count(b'\n')!=new.count(b'\n') or old.replace(b'\n',b'\x16\x01')!=new.replace(b'\n',b'\x16\x01'):raise ValueError('Reviewed break meaning/control change')
        writes.append(dict(writer=row['binding_id']+' reviewed break',offset=at,allowed_end=at+len(old),expected_sha256=sha(old),payload=new))
    rom,prior=apply_writes(rom,writes)
    profile=read('reflow.json');writes=[]
    joins={row['offset']-2 for row in profile['writes'] if row['payload_hex']=='18'}
    spaces=profile.get('joined_space_offsets',[])
    if set(spaces)!=joins or len(spaces)!=len(joins):raise ValueError('Joined separator population mismatch')
    for at in spaces:
        if rom[at:at+2]!=b'\x81\x40':raise ValueError('Joined separator source mismatch')
        writes.append(dict(writer='reviewed joined word space',offset=at,allowed_end=at+2,expected_sha256=sha(b'\x81\x40'),payload=b'\x16\x01'))
    rom,separators=apply_writes(rom,writes);writes=[]
    offsets=[row['offset'] for row in profile['writes']]
    if len(offsets)!=profile['adopted_unique_lf'] or len(set(offsets))!=len(offsets):raise ValueError('Reflow population mismatch')
    for row in profile['writes']:
        at=row['offset'];token=bytes.fromhex(row['payload_hex'])
        if token not in (b'\x17',b'\x18'):raise ValueError('Unapproved reflow token')
        if rom[at]!=10:raise ValueError('Approved reflow byte is not LF')
        if token==b'\x18' and rom[at-2:at]!=b'\x16\x01':raise ValueError('Zero-width join requires preceding word space')
        writes.append(dict(writer='reviewed soft line break',offset=at,allowed_end=at+1,expected_sha256=sha(b'\n'),payload=token))
    result,soft=apply_writes(rom,writes)
    restored=bytearray(result)
    for at in offsets:restored[at]=10
    if bytes(restored)!=rom:raise ValueError('Unexplained reflow difference')
    return result,dict(reviewed_linebreaks=prior,joined_word_spaces=separators,soft_linebreaks=soft)
