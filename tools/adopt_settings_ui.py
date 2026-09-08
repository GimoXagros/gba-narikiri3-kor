"""One-time adoption after inspecting four complete formatter loops."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    j=next(ROOT.glob('*[[]J[]]*.gba')).read_bytes()
    if hashlib.sha256(j).hexdigest()!='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394':raise ValueError('Wrong source')
    profile=json.loads((ROOT/'source/ui_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/ui.json').read_text(encoding='utf-8'))
    groups=[('strategy',0xf1d3c8,0xcd526,0xcd536,0xcd54c,12,['자유롭게 싸워라','전력을 다해 싸워라','방어를 굳혀라','힘을 아껴 싸워라','특기를 쓰지 마라']),
            ('control-mode',0xf1d494,0xd044e,0xd0454,0xd0468,6,['수동    ','반자동   ','자동 ']),
            ('text-speed',0xf1d4a0,0xd051e,0xd0524,0xd0538,4,['빠름  ','보통  ','느림  ']),
            ('display-mode',0xf1d4ac,0xd0632,0xd0638,0xd064c,5,['모드1  ','모드2  ','모드3  '])]
    for group,base,call,loop,literal,width,labels in groups:
        for i,text in enumerate(labels):
            identity=f'{group}-{i:02d}'
            if any(p['id']==identity for p in profile['records']):raise ValueError('Already adopted')
            off=base+i*4;ptr=struct.unpack_from('<I',j,off)[0];start=ptr-0x08000000;raw=j[start:j.index(0,start)]
            rec={'id':identity,'pointer_offset':hex(off),'original_pointer':hex(ptr),'original_raw':raw.hex(),'call_address':hex(0x08000000+call),'call_bytes':j[call:call+4].hex(),'consumer':'08001DA8','selected_max_cells':width,'variable_kinds':[],
                 'basis':'Complete strategy/setting loop: table base, 4-byte increment/index, inclusive count and formatter call inspected. Settings retain original cell widths because alternatives concatenate.',
                 'guards':[{'offset':hex(loop),'hex':j[loop:loop+4].hex()},{'offset':hex(literal),'hex':j[literal:literal+4].hex()}]}
            if group!='strategy':rec['exact_cells']=len(text)
            profile['records'].append(rec)
            catalog['records'].append({'id':identity,'text':text,'review':'pending','layout':'preserves individual setting field width; contextual inspection pending'})
    profile['scope']='Individually established UI literals and four complete strategy/settings loops; not all UI'
    (ROOT/'source/ui_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'translations/ui.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Adopted 14 strategy/settings labels')
if __name__=='__main__':main()
