"""B3TJ K1.1 large-font mapping; small renderer is a separate consumer.

K1.1 maps KS X 1001 Hangul order to Shift-JIS slots starting at 889F,
skipping 7F and FD..FF trails. The renderer's physical row stride is 192.
Evidence: font sheet and 080021A8 consumer; runtime correspondence pending
for the complete repertoire. Unknown controls remain explicit raw tokens.
"""
from functools import lru_cache

# Original B3TJ substitutes these Greek-code font slots with kanji. Confirmed
# from the immutable Japanese font pixels (ambiguous-skill-glyphs.png); the
# same glyph slots are unchanged by K1.1. This is not standard CP932 text.
CUSTOM_GLYPHS=dict(zip('ΑΒΓΖΗΘΙΚΛ','鼬翔吼曼雹刹濤炸驟'))

@lru_cache(None)
def hangul_map():
    chars=[bytes([a,b]).decode('euc_kr') for a in range(0xb0,0xc9) for b in range(0xa1,0xff)]
    codes=[c for c in range(0x889f,0xa000) if 0x40 <= c%256 <= 0xfc and c%256 != 0x7f]
    return dict(zip(codes,chars))

def glyph_index(code):
    a,b=divmod(code,256)
    if not (0x81<=a<=0x9f or 0xe0<=a<=0xff):raise ValueError('Not a double-byte lead')
    return (a-(0x81 if a<=0x87 else 0x85))*192+b-0x40

def decode(raw,korean=False):
    out=[];i=0
    while i<len(raw):
        b=raw[i]
        if b in (0x0a,):out.append('\n');i+=1
        elif b<0x20:out.append(f'{{BYTE:{b:02X}}}');i+=1
        elif 0x20<=b<=0x7e:out.append(chr(b));i+=1
        elif 0xa1<=b<=0xdf:out.append(bytes([b]).decode('cp932'));i+=1
        elif 0x81<=b<=0x9f or 0xe0<=b<=0xfc:
            if i+1==len(raw):raise ValueError('Truncated double-byte character')
            code=int.from_bytes(raw[i:i+2],'big')
            value=hangul_map()[code] if korean and code in hangul_map() else raw[i:i+2].decode('cp932')
            out.append(CUSTOM_GLYPHS.get(value,value))
            i+=2
        else:raise ValueError(f'Unmodeled byte {b:02X}')
    return ''.join(out)

def encode(text):
    inverse={v:k.to_bytes(2,'big') for k,v in hangul_map().items()}
    result=bytearray()
    for c in text:
        if c in inverse:result.extend(inverse[c])
        elif c=='\n':result.append(10)
        else:
            raw=c.encode('cp932')
            if len(raw)==2 and int.from_bytes(raw,'big') in hangul_map():
                raise ValueError(f'Source glyph was replaced by Hangul: {c}')
            result.extend(raw)
    return bytes(result)
