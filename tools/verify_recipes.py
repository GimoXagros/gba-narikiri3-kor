"""Recipe getter, real list-render call path, and non-text table preservation."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R4,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();legacy=a.legacy.read_bytes();catalog=json.loads((ROOT/'translations/recipes.json').read_text(encoding='utf-8'));cases=0;fields=0
    for i,row in enumerate(catalog['records']):
        off=0x74c67c+i*20
        if rom[off+12:off+20]!=legacy[off+12:off+20]:raise ValueError('Recipe effects or ingredient IDs changed')
        for name,delta in [('large_name',0),('small_name',4),('description',8)]:
            ptr=struct.unpack_from('<I',rom,off+delta)[0]
            if row.get(name) is None:
                if rom[off+delta:off+delta+4]!=legacy[off+delta:off+delta+4]:raise ValueError('Unselected recipe field changed')
            else:
                start=ptr-0x08000000
                if not 0x1090000<=start<0x10a0000 or rom[start:rom.index(0,start)]!=encode(row[name]):raise ValueError('Recipe string relocation differs')
                fields+=1
    for mode in (0,1):
        f=Fixture(rom,mode);expected=Fixture(rom,mode);u=f.uc
        for i,row in enumerate(catalog['records']):
            f.draw(b'');u.reg_write(UC_ARM_REG_R0,i);u.reg_write(UC_ARM_REG_LR,0x0203fff1)
            u.emu_start(0x080097c9,0x0203fff0,count=1000)
            record=0x0874c67c+i*20
            if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_R0)!=record:raise ValueError('Original recipe getter differs')
            u.reg_write(UC_ARM_REG_R4,0x02000000);u.reg_write(UC_ARM_REG_R6,record);u.reg_write(UC_ARM_REG_SP,0x03007e00)
            # Executes original ldr [record+4], real variadic formatter and
            # modified small renderer; stop before the unrelated game query.
            u.emu_start(0x080d81bd,0x080d81c4,count=1000000)
            if u.reg_read(UC_ARM_REG_PC)!=0x080d81c4 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Recipe display path did not return')
            expected.draw(encode(row['small_name']))
            if f.pixels()!=expected.pixels():raise ValueError('Recipe original list call renders different glyphs')
            cases+=1
    report={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'recipe_records':22,'selected_string_fields':fields,'original_getter_and_list_renderer_cases':cases,'effect_and_ingredient_bytes_preserved':True,
            'scope':'All 22 recipe identities; original getter and small-list call path in both modes. Large name/description pointer contents checked; natural cooking/results/layout remain separate.'}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
