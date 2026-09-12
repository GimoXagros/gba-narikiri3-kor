"""Build explicitly synthetic B3TJ review saves; never normal-play evidence.

Input EEPROM is immutable. Guest setters perform inventory, party, level and
chapter changes in an isolated CPU. Outputs require a new directory.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *

ROM_SHA = '1051612d3027c315596e28a5eb78451287bde5926e57d45268537c90c29b56ca'
SEED_SHA = '312bb57555b6d405d235d1affe240b29fedc0c73ddfa1e125607efb37d94e6c2'
BASE = 0x02001d80
FLAGS = BASE + 0x9e0
# 89 player costumes, including gender variants; excludes unused/NPC identities.
COSTUMES = [i for i in range(1, 94) if i not in (41, 43, 60, 87)]

def sha(b): return hashlib.sha256(b).hexdigest()
def swap(b): return b''.join(b[i:i+8][::-1] for i in range(0, len(b), 8))
def header(b):
    b[:8] = b'NARIKIRI'
    struct.pack_into('<II', b, 8, 0x0131cd45,
                     sum(struct.unpack('<%dI' % ((len(b)-16)//4), b[16:])) & 0xffffffff)
    return b

class Guest:
    def __init__(self, rom, block):
        self.u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for addr, size in [(0x08000000,0x2000000),(0x02000000,0x40000),
                           (0x03000000,0x8000),(0x04000000,0x1000)]:
            self.u.mem_map(addr, size)
        self.u.mem_write(0x08000000, rom)
        self.u.mem_write(BASE, bytes(block))
        self.calls = []
        self.u.hook_add(UC_HOOK_CODE, self.bios, begin=0x080dd42c, end=0x080dd42c)
        self.call(0x6118)
        self.call(0x7410)

    def bios(self, u, addr, size, _):
        # BIOS Div: signed quotient r0, remainder r1, abs quotient r3.
        a, b = [struct.unpack('<i', struct.pack('<I',u.reg_read(r)))[0]
                for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
        if not b: raise ValueError('Division by zero')
        q = (abs(a)//abs(b)) * (-1 if (a<0) != (b<0) else 1)
        for r, v in [(UC_ARM_REG_R0,q),(UC_ARM_REG_R1,a-q*b),(UC_ARM_REG_R3,abs(q))]:
            u.reg_write(r, v & 0xffffffff)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def call(self, pc, *args):
        for reg, val in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3), args):
            self.u.reg_write(reg, val)
        self.u.reg_write(UC_ARM_REG_SP,0x03007e00)
        self.u.reg_write(UC_ARM_REG_LR,0x0203fff1)
        self.u.emu_start(0x08000001+pc,0x0203fff0,count=2000000)
        if self.u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or self.u.reg_read(UC_ARM_REG_SP)!=0x03007e00:
            raise ValueError(f'Guest did not return safely: {pc:x}')
        self.calls.append([hex(pc),list(args)])
        return self.u.reg_read(UC_ARM_REG_R0)

def build(rom, seed, chapter):
    decoded = swap(seed)
    g = Guest(rom, decoded[:0xf00])
    for i in range(1,123): g.call(0x663c,i,15)
    for i in range(1,425): g.call(0x812c,i)
    for i in COSTUMES: g.call(0x812c,0x1a9+i)
    for i in range(41):
        g.call(0x7d48,i)
        addr = 0x02002c80+i*32
        while g.u.mem_read(addr+0x1d,1)[0] < 99: g.call(0x76c0,addr)
        g.call(0x79f8,addr)
        g.call(0x6374,i,100)
    # Library uses its own identity IDs; cover all 37 actual records.
    for i in range(37): g.call(0x812c,0x209+rom[0x1c06e0+i*24+20])
    for i in range(22): g.call(0x812c,0x678+i)
    g.call(0x6258,9999999)
    if chapter is not None:
        g.call(0x959c,chapter)
        g.call(0xa6c68)  # Original debug chapter synchronization, explicit cheat scope.
        # That debug helper clears one monster encounter bit at late chapters.
        # Restore collection completeness after chapter synchronization.
        for i in range(1,425): g.call(0x812c,i)
    g.call(0x7450)
    body = bytearray(g.u.mem_read(BASE,0xf00))
    # Guest validation against actual item/flag/library getters.
    assert all(g.call(0x6614,i)==15 for i in range(1,123))
    assert all(g.call(0x816c,0x1a9+i) for i in COSTUMES)
    assert all(g.call(0xcf4bc,i)==1 for i in range(37))
    assert all(g.call(0x816c,0x266+i) for i in range(41))
    assert all(g.call(0x816c,0x678+i) for i in range(22))
    assert all(g.call(0x816c,i) for i in range(1,425))
    assert all(body[0x88+i*20+0x11]==99 for i in range(41))
    # Only decoded fields established from guest accessors may change.
    allowed = set(range(0x10,0x28)) | set(range(0x88,0x3bc)) | set(range(0x9a8,0x9d1)) | set(range(0x9d8,0x9dc))
    allowed |= set(range(0x9e0,0xb70)) | set(range(0xb90,0xbce))
    if chapter is not None: allowed.add(0x9a0)
    changes = [i for i in range(16,0xf00) if body[i]!=decoded[i]]
    assert set(changes) <= allowed, [hex(i) for i in changes if i not in allowed]
    # Persistent collection block used by the original save subsystem.
    system = bytearray(0x200)
    system[0x10:0x1a0] = body[0x9e0:0xb70]
    system[0x1a0:0x1a8] = body[0x9d8:0x9e0]
    out = bytes(header(body)) + decoded[0xf00:0x1e00] + bytes(header(system))
    assert out[0xf00:0x1e00] == decoded[0xf00:0x1e00]
    for start, size in [(0,0xf00),(0x1e00,0x200)]:
        address = 0x02030000
        g.u.mem_write(address, out[start:start+size])
        assert g.call(0x8a08,address,size)==1
        g.u.mem_write(address+12,bytes([out[start+12]^1]))
        assert g.call(0x8a08,address,size)==0
    return swap(out), {'chapter':chapter,'changed_main_body_bytes':len(changes),
        'changed_offsets':[hex(i) for i in changes], 'guest_calls':len(g.calls),
        'costume_ids':COSTUMES,'party_slots':41,'level':99,'inventory_ids':[1,122],
        'inventory_quantity':15,'recipes':22,'biographies':37,'monster_flags':424,
        'provenance':'Synthetic review/cheat save, not normal completion or progression evidence'}

def main():
    p=argparse.ArgumentParser()
    for name in ('rom','seed','out'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();rom=a.rom.read_bytes();seed=a.seed.read_bytes()
    assert sha(rom)==ROM_SHA and sha(seed)==SEED_SHA
    a.out.mkdir(parents=True,exist_ok=False)
    report={'rom_sha256':sha(rom),'seed_sha256':sha(seed),'saves':[]}
    for name,chapter in [('ND3_v1.1a_review_collection',None),('ND3_v1.1a_review_postgame',22)]:
        data, row=build(rom,seed,chapter)
        (a.out/(name+'.sav')).write_bytes(data)
        row.update(file=name+'.sav',sha256=sha(data),size=len(data));report['saves'].append(row)
    (a.out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({r['file']:r['sha256'] for r in report['saves']}))

if __name__=='__main__': main()
