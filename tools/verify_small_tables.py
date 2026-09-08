"""Verify finite non-dialogue table identity, original getters and both renderers."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from verify_simple_consumer import SimpleFixture
from text_codec import encode
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rom=a.rom.read_bytes()
    profile=json.loads((ROOT/'source/small_tables.json').read_text(encoding='utf-8'))
    translation={r['id']:r['text'] for r in json.loads((ROOT/'translations/small_tables.json').read_text(encoding='utf-8'))['records']}
    base=int(profile['rule_base'],16);size=profile['rule_count']*profile['rule_stride']
    if hashlib.sha256(rom[base:base+size]).hexdigest()!=profile['rule_sha256']:raise ValueError('Non-text team rules changed')
    count=0
    for mode in (0,1):
        f=Fixture(rom,mode);simple=SimpleFixture(rom,mode);u=f.uc
        for group in profile['groups']:
            for i,row in enumerate(group['records']):
                offset=int(row['pointer_offset'],16);ptr=struct.unpack_from('<I',rom,offset)[0];start=ptr-0x08000000
                text=translation[row['id']];raw=encode(text)
                if not 0x1070000<=start<0x1080000 or rom[start:rom.index(0,start)]!=raw:raise ValueError('Small table pointer/value mismatch')
                for register,value in [(UC_ARM_REG_R0,i),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(register,value)
                u.emu_start(int(group['consumer_getter'],16)|1,0x0203fff0,count=1000)
                if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_R0)!=ptr or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Original getter identity/return mismatch')
                f.draw(raw);simple.draw_simple(raw)
                if f.pixels()!=simple.pixels():raise ValueError('Small table consumer disagreement')
                if bytes(u.mem_read(0x02000004,1))[0] != 1+len(text):raise ValueError('Small table cell count mismatch')
                count+=1
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'selected_table_entries':len(translation),'getter_pointer_and_both_renderers_mode_cases':count,'non_text_team_rules_unchanged':True,'scope':'All adopted title/bonus slots, original index getters and two isolated small renderers. Normal-play representative screens and full reachability are separate.'}
    a.out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
