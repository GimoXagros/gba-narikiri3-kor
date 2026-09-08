"""One-time adoption of manually inspected literal calls; never a build scan."""
import json,struct,re
from pathlib import Path
from text_codec import decode

ROOT=Path(__file__).resolve().parents[1]
# Literal, actual call, selected text. No numeric tables or effect data writes.
ROWS=[
 ('battle-magic-disabled',0x12b68,0x12b4e,'마법 금지'),
 ('battle-result-experience',0xc5f88,0xc5f08,'경험치 %8d'),
 ('monster-gald',0xcdc0c,0xcdbd6,'갈드 %5d'),
 ('monster-attack',0xcdf28,0xcde58,'공격    %5d\n'),
 ('monster-defense',0xcdf2c,0xcde66,'방어    %5d\n'),
 ('monster-intelligence',0xcdf30,0xcde74,'지력    %5d\n'),
 ('monster-agility',0xcdf34,0xcde82,'민첩    %5d\n'),
 ('monster-drops',0xcdf38,0xcde8c,'드롭 아이템'),
 ('monster-magic-resistant',0xcdf50,0xcdf0e,'\n마법에 강함'),
 ('monster-attack-unknown',0xcdfc0,0xcdf90,'공격    ?????\n'),
 ('monster-defense-unknown',0xcdfc4,0xcdf9a,'방어    ?????\n'),
 ('monster-intelligence-unknown',0xcdfc8,0xcdfa4,'지력    ?????\n'),
 ('monster-agility-unknown',0xcdfcc,0xcdfae,'민첩    ?????\n'),
 ('monster-element',0xce0e0,0xce008,'속성\n'),
 ('monster-element-strong',0xce0e4,0xce012,'강함\n\n\n\n'),
 ('monster-element-weak',0xce0e8,0xce01c,'약함'),
 ('costume-modifier-heading',0xcf008,0xcefb0,'능력치 보정\n'),
 ('costume-modifier-attack',0xcf014,0xcefd4,'공격력   %4d\n'),
 ('costume-modifier-defense',0xcf018,0xcefe0,'방어력   %4d\n'),
 ('costume-modifier-intelligence',0xcf01c,0xcefec,'지력     %4d\n'),
 ('costume-modifier-agility',0xcf020,0xceff8,'민첩     %4d'),
 ('costume-stat-attack',0xcf9c0,0xcf940,'공격    %4d\n'),
 ('costume-stat-defense',0xcf9c4,0xcf94e,'방어    %4d\n'),
 ('costume-stat-intelligence',0xcf9c8,0xcf95c,'지력    %4d\n'),
 ('costume-stat-agility',0xcf9cc,0xcf96a,'민첩    %4d\n'),
 ('costume-stat-experience',0xcf9d0,0xcf976,'EXP %4d/100\n'),
 ('costume-equipment-heading',0xcf9d4,0xcf980,'장비\n'),
 ('shop-select-item',0xd0eec,0xd0e98,'아이템 선택'),
 ('shop-select-count',0xd0ef0,0xd0eb0,'개수 선택\n'),
 ('shop-confirm',0xd0ef4,0xd0ec8,'결정'),
 ('shop-gald',0xd180c,0xd17ec,'%l갈드 %7d'),
 ('shop-total',0xd1818,0xd17fc,'%l합계 %7d'),
 ('reward-experience',0xd567c,0xd5630,'경험치'),
 ('reward-money',0xd5680,0xd563e,'돈'),
 ('reward-participation',0xd5684,0xd564c,'참가'),
 ('food-shop-gald',0xd86e0,0xd86d4,'%l갈드 %7d'),
 ('food-shop-total',0xd8700,0xd86f4,'%l합계 %7d'),
 ('food-shop-select-item',0xd8dbc,0xd8d32,'아이템 선택'),
 ('food-shop-confirm',0xd8dc0,0xd8d4a,'결정'),
 ('food-shop-view-info',0xd8dc4,0xd8d62,'정보 보기'),
]

def main():
    legacy=next(ROOT.glob('*[[]K[]]*.gba')).read_bytes()
    profile=json.loads((ROOT/'source/ui_profile.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'translations/ui.json').read_text(encoding='utf-8'))
    existing={x['id'] for x in profile['records']}
    for identity,lit,call,text in ROWS:
        if identity in existing:raise ValueError('Already adopted: '+identity)
        ptr=struct.unpack_from('<I',legacy,lit)[0];at=ptr-0x08000000
        raw=legacy[at:legacy.index(0,at)]
        # Check a real r1 literal load in the short inspected argument setup.
        loads=[]
        for pos in range(call-12,call,2):
            half=struct.unpack_from('<H',legacy,pos)[0]
            if half&0xff00==0x4900 and ((pos+4)&~3)+(half&255)*4==lit:loads.append(pos)
        if len(loads)!=1:raise ValueError('Inspected argument load differs: '+identity)
        pos=loads[0]
        row={'id':identity,'pointer_offset':hex(lit),'original_pointer':hex(ptr),'original_raw':raw.hex(),
             'call_address':f'{0x08000000+call:08X}','call_bytes':legacy[call:call+4].hex(),'consumer':'08001DA8',
             'selected_max_cells':20,'basis':'Individually inspected r1 literal argument and original format call. Korean label shortened; original numeric conversion and newline/reset order retained. Runtime page validation separate.',
             'variable_kinds':[], 'guards':[{'offset':hex(pos),'hex':legacy[pos:call+4].hex()}]}
        nums=re.findall(r'%([0-9]+)d',text)
        if nums:
            if len(nums)!=1:raise ValueError('Unexpected additional numeric parameter')
            width=int(nums[0]);values=[0,1,10,10**width-1]
            if width==5:values+=[65535]
            if width==4 and identity!='costume-stat-experience':values+=[-1,-32768,32767]
            if width>=7:values+=[2147483647]
            row['format_samples']=[[n] for n in dict.fromkeys(values)]
            row['variable_kinds']=['original_numeric_argument']
        # Bound relative to original spelling as well as the visible 20-cell
        # test window. Kana voice marks can overlay, so do not infer equality
        # of numeric x anchors from byte count.
        old=decode(raw).replace('%h','').replace('%l','')
        if len(text.replace('%l',''))>len(old):raise ValueError('New literal length is not conservative: '+identity)
        profile['records'].append(row)
        catalog['records'].append({'id':identity,'text':text,'review':'source_and_call_inspected','layout':'isolated_formatter_and_runtime_review_pending'})
    profile['scope']='Individually established UI literals and actual consumers; not the complete UI population'
    for name,value in [('source/ui_profile.json',profile),('translations/ui.json',catalog)]:
        (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Adopted',len(ROWS),'explicit UI literals')

if __name__=='__main__':main()
