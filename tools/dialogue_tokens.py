"""Read controls at character boundaries, never at a Shift-JIS trail byte."""
import re

NAME_CODES = b'01BDGKL'

def units(raw):
    i=0
    while i<len(raw):
        size=2 if 0x81<=raw[i]<=0x9f or 0xe0<=raw[i]<=0xfc else 1
        if i+size>len(raw): raise ValueError('Truncated dialogue character')
        yield i,raw[i:i+size]
        i+=size

def controls(raw):
    cells=list(units(raw));out=[]
    for (off,a),(_,b) in zip(cells,cells[1:]):
        if a==b'@' and len(b)==1 and b[0] in NAME_CODES:out.append((off,a+b))
        elif a==b'%' and len(b)==1 and (65<=b[0]<=90 or 97<=b[0]<=122):out.append((off,a+b))
    return out

def unsafe_expansion_sequences(raw):
    valid={off for off,token in controls(raw) if token.startswith(b'@')}
    return [m.start() for m in re.finditer(rb'@[01BDGKL]',raw) if m.start() not in valid]

def expand_expected(raw,names):
    out=bytearray();cursor=0
    for off,token in controls(raw):
        if token not in names:continue
        out.extend(raw[cursor:off]);out.extend(names[token]);cursor=off+2
    out.extend(raw[cursor:]);return bytes(out)
