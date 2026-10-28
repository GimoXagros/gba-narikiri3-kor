"""Final-layer checks for typed string references, extents and protected tables."""
import hashlib


def verify(base, candidate, metadata):
    if len(base)!=16777216 or len(candidate)!=len(base) or hashlib.sha256(base).hexdigest()!=metadata['baseline_sha256']:
        raise ValueError('Baseline identity or exact16MiB size')
    fields=set()
    changed_spans=0
    for row in metadata['strings']:
        at=row['offset']; end=at+row['length']
        if candidate[end]!=0 or [i for i,v in enumerate(candidate[at:end]) if v==0] != [i for i,v in enumerate(base[at:end]) if v==0]:
            raise ValueError(f'String extent/terminator changed at {at:#x}')
        before, after = base[at:end], candidate[at:end]
        changed_spans += before != after
        i=0
        while i<len(before):
            n=2 if 0x81<=before[i]<=0x9f or 0xe0<=before[i]<=0xfc else 1
            old=before[i:i+n]; new=after[i:i+n]
            allowed={old}
            if old==b'\x81\x40':allowed.add(b'\x16\x01')
            if old==b' ':allowed.add(b'\x17')
            if old==b'\n':allowed.update((b'\x17',b'\x18'))
            if new not in allowed:raise ValueError(f'Non-layout token mutation at {at+i:#x}')
            i+=n
        for field in row['pointer_fields']:
            if candidate[field:field+4]!=base[field:field+4]:raise ValueError(f'String pointer changed at {field:#x}')
            fields.add(field)
    for row in metadata['unchanged_regions']:
        if candidate[row['start']:row['end']]!=base[row['start']:row['end']]:raise ValueError('Protected region changed: '+row['label'])
    return dict(status='PASS_KNOWN_FIXED_TEXT_LAYOUT',candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                ROM_bytes=len(candidate),string_spans=len(metadata['strings']),pointer_fields=len(fields),
                changed_string_spans=changed_spans,only_space_softbreak_token_changes=True,
                protected_regions=len(metadata['unchanged_regions']),scope=metadata['scope'])
