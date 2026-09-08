"""Render original font pixels for skill names whose CP932 label is ambiguous."""
import json,struct
from pathlib import Path
from PIL import Image,ImageDraw
from text_codec import glyph_index
root=Path(__file__).resolve().parents[1]
j=next(root.glob('*[[]J].gba')).read_bytes()
rows=json.loads((root/'analysis/generated/skills.json').read_text(encoding='utf-8'))['records']
ids=[161,173,176,186,189,223,227,285,286,287,304,316,324,332,335,338]
im=Image.new('RGB',(420,len(ids)*24),'white');d=ImageDraw.Draw(im)
for row,i in enumerate(ids):
    raw=bytes.fromhex(rows[i]['large']['j_raw']);d.text((2,row*24+3),str(i),fill='black')
    x=40
    for off in range(0,len(raw),2):
        slot=glyph_index(int.from_bytes(raw[off:off+2],'big'))
        data=j[0xddcc4+slot*32:0xddcc4+(slot+1)*32]
        for y,v in enumerate(struct.unpack('<16H',data)):
            for k in range(16):
                if v&(1<<k): im.putpixel((x+k,row*24+y),(0,0,0))
        x+=16
im.resize((840,len(ids)*48),Image.Resampling.NEAREST).save(root/'analysis/generated/ambiguous-skill-glyphs.png')
