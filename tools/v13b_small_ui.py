import json,struct,subprocess,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SOURCE=ROOT/'source/v13b/small-ui'
sha=lambda b:hashlib.sha256(b).hexdigest()
def bl(at,target):
 d=target-at-4
 assert d%2==0 and -(1<<22)<=d<(1<<22)
 return struct.pack('<HH',0xf000|((d>>12)&0x7ff),0xf800|((d>>1)&0x7ff))
def build(base,toolchain,outdir,small_label_print,address=0x08fbc3dc,*,row_cached_tile,small_composite):
 base=bytes(base); assert len(base)==0x1000000
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=False);toolchain=Path(toolchain)
 def run(t,args):return subprocess.check_output([str(toolchain/('arm-none-eabi-'+t+'.exe')),*map(str,args)])
 calls={}
 for at in [0xc9c0,0xc9896,0xca3b0,0xca42e,0xca82e,0xca8aa,0xcef38,0xcfa62,0xcc56c,0xcd812,0xcc09c,0xcc0c2,0xd1c88,0xd2a4c,0xd2a74,0xd42fc,0xd437c]:calls[at]='small_all_format'
 profiles=json.loads((ROOT/'source/ui_profile.json').read_text('utf8'))['records']
 texts={x['id']:x['text'] for x in json.loads((ROOT/'translations/ui.json').read_text('utf8'))['records']}
 exclusions={'save-place-label':'fixed following location column','save-time-single':'fixed numeric time columns','save-time-double':'fixed numeric time columns'}
 ledger=[]
 calls[0xd42fc]='centered_format_helper';calls[0xd437c]='centered_format_helper'
 for row in profiles:
  ident=row['id'];text=texts[ident];call=int(row['call_address'],16)
  if row['consumer']=='080B0CD8':status='NO_SPACE_KEEP_ICONS'
  elif ident in exclusions:status='EXCEPTION' if not ident.startswith('scroll-') else 'PENDING';
  elif row['consumer']=='08001A10':
   if ident=='field-team-suffix':calls[call-0x08000000]='small_direct';status='SCOPED_HALFSPACE'
   else:status='NO_SPACE'
  elif ident.startswith('scroll-hint-'):calls[call-0x08000000]='small_ui_format';status='SCOPED_HALFSPACE'
  elif ' ' not in text:status='NO_SPACE'
  elif text.endswith(' ') or '  ' in text or ('%' in text and '%s' not in text and '%l' not in text):status='ALIGNMENT_KEEP'
  else:calls[call-0x08000000]='small_ui_format';status='SCOPED_HALFSPACE'
  ledger.append({'id':ident,'status':status,'reason':exclusions.get(ident,''),'call_address':hex(call)})
 source=outdir/'assembled.s'
 table='\n.balign 4\nscope_table:\n'+''.join(f'.word {hex(at+0x08000005)}, {dict(small_all_format=0,small_ui_format=1,small_direct=2,centered_format_helper=3)[sym]}\n' for at,sym in sorted(calls.items()))+'.word 0,0\n'
 traps=[int.from_bytes(base[int(r['pointer_offset'],0):int(r['pointer_offset'],0)+4],'little') for r in profiles if r['id'] in ['trap-menu-02','trap-menu-03']]
 table+='trap_format_pointers:\n'+''.join(f'.word {hex(v)}\n' for v in traps)
 source.write_text((SOURCE/'small_ui.s').read_text('utf8')+table+(SOURCE/'ui_label.s').read_text('utf8'),'utf8')
 obj=outdir/'small_ui.o';elf=outdir/'small_ui.elf';binary=outdir/'small_ui.bin'
 run('as',['-mcpu=arm7tdmi','--defsym',f'SMALL_LABEL_PRINT={small_label_print|1}','--defsym',f'ROW_CACHED_TILE={row_cached_tile|1}','--defsym',f'SMALL_COMPOSITE={small_composite|1}',source,'-o',obj])
 run('ld',[f'-Ttext={hex(address)}','-e','small_ui_format',obj,'-o',elf])
 run('objcopy',['-O','binary',elf,binary]);payload=binary.read_bytes()
 symbols={p[2]:int(p[0],16) for l in run('nm',['-n',elf]).decode().splitlines() if len(p:=l.split())>=3}
 assert address+len(payload)<=0x08fbcd2c
 result=bytearray(base);at=address-0x08000000
 if base[at:at+len(payload)]!=b'\xff'*len(payload):raise ValueError('Boot reclaim must precede small UI code')
 result[at:at+len(payload)]=payload
 writes=[{'offset':at,'bytes':len(payload),'before_sha256':sha(base[at:at+len(payload)]),'after_sha256':sha(payload),'kind':'boot-reclaimed-code-requires-reclaim-stage'}]
 for at,sym in sorted(calls.items()):
  oldtarget=0x08001a10 if sym=='small_direct' else 0x08001da8
  expected=bl(at+0x08000000,oldtarget)
  if base[at:at+4]!=expected:raise ValueError(f'Caller guard {at:x}: {base[at:at+4].hex()} != {expected.hex()}')
  data=bl(at+0x08000000,0x08001d90);result[at:at+4]=data
  writes.append({'offset':at,'bytes':4,'before_hex':expected.hex(),'after_hex':data.hex(),'symbol':sym})
 # Preserve the original variadic entry; only scoped callers use the second veneer.
 expected=base[0x1d88:0x1da8]
 assert expected.hex()=='30b5051c0432054c201c00f01bfc281c211cfff739fe30bc01bc004768140003'
 data=bytes.fromhex('004b1847')+struct.pack('<I',symbols['small_native_helper']|1)
 data+=bytes.fromhex('0eb400b5004b1847')+struct.pack('<I',symbols['small_native_format']|1)
 result[0x1d88:0x1d88+len(data)]=data
 writes.append({'offset':0x1d88,'bytes':len(data),'before_hex':base[0x1d88:0x1d88+len(data)].hex(),'after_hex':data.hex(),'symbol':'native helper and scoped variadic veneers'})
 report={'symbols':symbols,'code_bytes':len(payload),'writes':writes,'ui_ledger':ledger,'rom_size':len(result),'input_sha256':sha(base),'output_sha256':sha(result),'runtime':'NOT_RUN','scope':'Scoped callsites, original strings and pointer fields unchanged. CPU-only test artifact until boot reclaim integration.'}
 (outdir/'BUILD.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 return bytes(result),report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--small-label',type=lambda x:int(x,0),required=True);p.add_argument('--row-cached-tile',type=lambda x:int(x,0),required=True);p.add_argument('--small-composite',type=lambda x:int(x,0),required=True);a=p.parse_args()
 result,report=build(a.rom.read_bytes(),a.toolchain,a.out,a.small_label,row_cached_tile=a.row_cached_tile,small_composite=a.small_composite);(a.out/'SMALL_UI_CPU_ONLY.gba').write_bytes(result);print(report['code_bytes'],report['output_sha256'])
