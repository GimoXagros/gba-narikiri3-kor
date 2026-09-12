"""Typed recipe string fields; ingredient IDs and effect bytes are never text."""
import hashlib,struct
from text_codec import encode

def selections(profile,catalog,j,legacy):
    base=int(profile['base'],0);count=profile['count'];stride=profile['stride']
    if count!=22 or stride!=20 or len(profile['records'])!=count or len(catalog['records'])!=count:
        raise ValueError('Recipe population differs')
    if profile['schema']!=1 or catalog['policy']!='development_only_needs_review':raise ValueError('Recipe input policy differs')
    for rom in (j,legacy):
        if hashlib.sha256(rom[base:base+count*stride]).hexdigest()!=profile['table_sha256']:raise ValueError('Original recipe table differs')
        for g in profile['consumer_guards']:
            off=int(g['offset'],0);raw=bytes.fromhex(g['hex'])
            if rom[off:off+len(raw)]!=raw:raise ValueError('Recipe consumer differs')
    out=[]
    for i,(source,row) in enumerate(zip(profile['records'],catalog['records'])):
        if row['id']!=source['id'] or source['index']!=i:raise ValueError('Recipe identity/order differs')
        for field,delta,limit in [('large_name',0,28),('small_name',4,10),('description',8,18)]:
            ptr=struct.unpack_from('<I',legacy,base+i*20+delta)[0];start=ptr-0x08000000
            for key,rom in [('j',j),('legacy',legacy)]:
                raw=bytes.fromhex(source[field+'_'+key+'_raw'])
                if rom[start:start+len(raw)+1]!=raw+b'\0':raise ValueError('Recipe original string boundary differs')
            text=row.get(field)
            if text is None:
                if field=='small_name':raise ValueError('Missing recipe translation')
                continue
            if not text or len(text)>limit or any(c in text for c in ('%','@','\n')):raise ValueError('Recipe field layout/control differs')
            out.append((row['id']+'-'+field,base+i*20+delta,encode(text)+b'\0'))
    return out
