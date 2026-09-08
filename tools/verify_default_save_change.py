"""Prove the intentional dev03->dev04 default-name save delta, read-only."""
import argparse, hashlib, json, struct
from pathlib import Path
from text_codec import encode
from save_contract import opening_save

def decode(raw):
    if len(raw)!=8192: raise ValueError('Wrong EEPROM size')
    out=bytearray(b''.join(raw[i:i+8][::-1] for i in range(0,len(raw),8)))
    if struct.unpack_from('<I',out,12)[0] != sum(struct.unpack('<956I',out[16:0xf00]))&0xffffffff:
        raise ValueError('Game checksum invalid')
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    old=a.old.read_bytes();new=a.new.read_bytes();before=decode(old);after=decode(new)
    previous=before.copy();previous[12:16]=bytes(4);previous[0x9dc:0x9e0]=bytes(4)
    if hashlib.sha256(previous).hexdigest()!='68695495a3b74f0bfdd11477a3db703273ebca5efce99885dbb2f2fb00f517cc':
        raise ValueError('Not the prior approved opening state')
    for offset in (0x68,0x7b):
        if before[offset:offset+13]!=encode('드림호').ljust(13,b'\0') or after[offset:offset+13]!=encode('드림').ljust(13,b'\0'):
            raise ValueError('Unexpected ship-name field change')
        previous[offset:offset+13]=after[offset:offset+13]
    actual=after.copy();actual[12:16]=bytes(4);actual[0x9dc:0x9e0]=bytes(4)
    if previous!=actual:raise ValueError('Unrelated save data changed')
    report={'status':'PASS_ONLY_INTENDED_DEFAULT_NAME_DELTA', 'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),
            'decoded_name_field_offsets':['0x68','0x7b'],'old_name':'드림호','new_name':'드림',
            'changed_offsets':[hex(i) for i,(x,y) in enumerate(zip(before,after)) if x!=y],
            'current_contract':opening_save(new),'scope':'Fresh-game deterministic trace only; does not migrate existing user saves.'}
    with a.out.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
