"""Rebuild only the four established battle caption sprites and placements."""
import hashlib,struct

def selections(profile,catalog,legacy,glyphs):
    if profile['schema']!=1 or catalog['schema']!=1 or catalog['policy']!='development_only_needs_review':raise ValueError('Invalid caption policy')
    for guard in profile['guards']:
        a=int(guard['offset'],0);raw=bytes.fromhex(guard['hex'])
        if legacy[a:a+len(raw)]!=raw:raise ValueError('Battle caption consumer/structure guard differs')
    a=int(profile['graphics_offset'],0);size=profile['graphics_size']
    if hashlib.sha256(legacy[a:a+size]).hexdigest()!=profile['graphics_sha256']:raise ValueError('Battle sprite bank differs')
    rows={r['id']:r for r in catalog['records']}
    if len(rows)!=4 or set(rows)!={r['id'] for r in profile['records']}:raise ValueError('Caption identities differ')
    repertoire=[]
    for row in profile['records']:
        text=rows[row['id']]['text']
        if not 1<=len(text)<=4 or any(c not in glyphs for c in text):raise ValueError('Caption outside four-cell Hangul design')
        for c in text:
            if c not in repertoire:repertoire.append(c)
    if len(repertoire)>profile['tile_pool_count']:raise ValueError('Caption tile pool exhausted')
    writes=[];pool=int(profile['tile_pool_offset'],0)
    for i,c in enumerate(repertoire):
        pixels=[15 if p=='#' else 0 for line in glyphs[c] for p in line]
        if len(pixels)!=64:raise ValueError('Caption glyph is not 8x8')
        raw=bytes(pixels[n]|pixels[n+1]<<4 for n in range(0,64,2))
        writes.append((pool+i*32,raw,'battle caption glyph '+c))
    for row in profile['records']:
        a=int(row['layout_offset'],0);raw=bytes.fromhex(row['original_layout_hex'])
        if len(raw)!=32 or legacy[a:a+32]!=raw:raise ValueError('Caption placement source differs')
        text=rows[row['id']]['text'];start=(24-len(text)*8)//2
        # Eight fixed object slots: visible letter frames first, then their
        # original dark background frame, unused slots disabled by frame 0.
        entries=[(profile['glyph_frame_first']+repertoire.index(c),start+i*8,0,0) for i,c in enumerate(text)]
        entries += [(5,start+i*8-2,-1,0) for i in range(len(text))]
        entries += [(0,0,0,0)]*(8-len(entries))
        writes.append((a,b''.join(struct.pack('<bbbb',*e) for e in entries),row['id']+' caption-only sprite layout: '+text))
    return writes
