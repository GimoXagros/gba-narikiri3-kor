"""Original save-location mode/ID selection and real small-text output."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from verify_small_consumer import Fixture
from text_codec import encode,decode
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rom=a.rom.read_bytes();old=a.legacy.read_bytes();profile=json.loads((ROOT/'source/save_place_profile.json').read_text(encoding='utf-8'));rows=json.loads((ROOT/'translations/save_places.json').read_text(encoding='utf-8'))['records']
    selected_ui_literals={v for at in (0xd01e4,0xd01fc) for v in range(at,at+4)}
    for g in profile['guards']:
        at=int(g['offset'],0)
        for i,value in enumerate(bytes.fromhex(g['hex'])):
            if at+i not in selected_ui_literals and rom[at+i]!=value:raise ValueError('Save mode/ID selection or window changed')
    for i,row in enumerate(rows):
        ptr=struct.unpack_from('<I',rom,0xf1d3dc+i*4)[0]-0x08000000
        if not 0x10f0000<=ptr<0x10f1000 or rom[ptr:rom.index(0,ptr)]!=encode(row['text']):raise ValueError('Save place pointer/text differs')
    if rom[0xf1d48c:0xf1d490]!=old[0xf1d48c:0xf1d490] or rom[0x1c1aec:0x1c1af0]!=old[0x1c1aec:0x1c1af0]:raise ValueError('Unselected test label changed')
    ui={r['id']:r['text'] for r in json.loads((ROOT/'translations/ui.json').read_text(encoding='utf-8'))['records']}
    cases=[(2,i,rows[i]['text']) for i in range(44)]+[(3,65535,ui['save-town']),(10,65535,ui['save-town'])]+[(11,i,rows[25]['text']) for i in (0,43,65535)]+[(m,65535,'') for m in (0,1,4,5,6,7,8,9,12)]
    count=0;maximum=0
    for fontmode in (0,1):
        f=Fixture(rom,fontmode);expected=Fixture(rom,fontmode);u=f.uc;y=5 if fontmode else 6
        for mode,index,label in cases:
            state=bytearray(32);struct.pack_into('<hH',state,16,mode,index);u.mem_write(0x02001d20,bytes(state))
            u.mem_write(0x03000060,bytes(2048));u.mem_write(0x02000000,bytes([4,1,26,9,4,y,1,13]))
            for reg,value in [(UC_ARM_REG_R0,0x02000000),(UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x0203fff1)]:u.reg_write(reg,value)
            u.emu_start(0x080d01c5,0x0203fff0,count=5000000)
            if u.reg_read(UC_ARM_REG_PC)!=0x0203fff0 or u.reg_read(UC_ARM_REG_SP)!=0x03007e00:raise ValueError('Save place consumer return/stack differs')
            if bytes(u.mem_read(0x02001d20,32))!=bytes(state):raise ValueError('Save location display changed save-state fields')
            text=ui['save-place-label']+label
            if len(text)>22:raise ValueError('Save place exceeds original 22-cell window')
            expected.draw(encode(text+'\n'),x=4,y=y,mark_mode=1)
            if f.pixels()!=expected.pixels():raise ValueError(f'Save place mode {mode} index {index} pixels differ')
            maximum=max(maximum,len(text));count+=1
    r={'status':'PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),'selected_location_pointer_fields':44,'mode_index_renderer_cases':count,'maximum_label_plus_location_cells':maximum,'original_window_cells':22,'save_state_fields_preserved':True,'test_slot_preserved':True,'scope':'Actual D01C4 mode/ID selection and formatter/renderer in both modes; all selected dungeon IDs, town modes, fixed colosseum branch and no-location modes. CPU state fixtures are not live save edits. Normal dungeon save progression remains separate.'}
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))


if __name__=='__main__':main()
