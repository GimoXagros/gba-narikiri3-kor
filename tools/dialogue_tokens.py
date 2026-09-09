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


def validate_dialogue_formats(raw):
    """Only the k/l commands occur in the established dialogue population.

    Literal percent signs must use the full-width glyph. The original
    formatter can silently swallow the percent and following Hangul bytes.
    """
    cells = list(units(raw))
    for index, (off, char) in enumerate(cells):
        if char == b'%' and (index + 1 == len(cells) or cells[index + 1][1] not in (b'k', b'l')):
            raise ValueError(f'Unsafe dialogue percent/control at byte {off}')

def expand_expected(raw,names):
    out=bytearray();cursor=0
    for off,token in controls(raw):
        if token not in names:continue
        out.extend(raw[cursor:off]);out.extend(names[token]);cursor=off+2
    out.extend(raw[cursor:]);return bytes(out)
