"""Actual emitted code for a selected final allocation, preserving source snapshot."""
import hashlib,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def relink(R,objects,locations,translate,refs,out,TC):
 out.mkdir(exist_ok=False);reports=[];blobs={}
 def run(tool,args):return subprocess.run([str(TC/('arm-none-eabi-'+tool+'.exe')),*map(str,args)],capture_output=True,check=True).stdout.decode('utf-8',errors='backslashreplace')
 symbols={'RELOC_SMALL_FONT':0x08000000+locations['SMALL_FONT_1BPP-01001000'],'RELOC_KEYBOARD_HEADERS':0x08000000+locations['KEYBOARD_HEADER_POINTERS-010B2400'],'RELOC_KEYBOARD_ROWS':0x08000000+locations['KEYBOARD_ROW_POINTERS-010B2000'],'RELOC_KEYBOARD_CELLS':0x08000000+locations['KEYBOARD_INPUT_CELLS-010B0000']}
 inputs=[('hook','small_font_hook',['small_font_hook.s','simple_font_hook.s']),('name-import','name_import',['name_import.s']),('name-keyboard','keyboard_draw',['name_keyboard.s']),('clothing-measure','clothing_measure',['clothing_measure.s']),('inspect-eye','inspect_eye_text',['inspect_eye.s'])]
 replacements={'small_font_hook.s':{'0x09001000':'RELOC_SMALL_FONT'},'simple_font_hook.s':{'0x09001000':'RELOC_SMALL_FONT'},'inspect_eye.s':{'0x09001000':'RELOC_SMALL_FONT'},'name_keyboard.s':{'0x090b2400':'RELOC_KEYBOARD_HEADERS','0x090b2000':'RELOC_KEYBOARD_ROWS','0x090b0000':'RELOC_KEYBOARD_CELLS'}}
 for name,entry,files in inputs:
  owner=next(o for o in objects if o['kind']=='THUMB_CODE' and o['owners']==[name]);base=0x08000000+locations[owner['id']];folder=out/name;folder.mkdir();srcs=[];hashes={}
  for f in files:
   raw=(ROOT/'source'/f).read_bytes();text=raw.decode('utf-8');hashes[f]=sha(raw)
   for old,sym in replacements.get(f,{}).items():assert text.count(old)==1;text=text.replace(old,sym)
   path=folder/f;path.write_text(text,'utf-8');srcs.append(path)
  bins=[];tables=[]
  for label in ('a','b'):
   build=folder/label;build.mkdir();assembled=[]
   for src in srcs:
    path=build/(src.name+'.o');run('as',['-mcpu=arm7tdmi','-mthumb',src,'-o',path]);assembled.append(path)
   elf=build/(name+'.elf');args=[f'-Ttext={hex(base)}','-e',entry,*assembled]
   for symbol,value in symbols.items():args+=['--defsym',f'{symbol}={hex(value)}']
   run('ld',args+['-o',elf]);path=build/(name+'.bin');run('objcopy',['-O','binary','--only-section=.text',elf,path]);nm=run('nm',['-a','--special-syms','--defined-only',elf]);(build/'symbols.txt').write_text(nm,'utf-8');(build/'disassembly.txt').write_text(run('objdump',['-d','-m','armv4t',elf]),'utf-8');bins.append(path.read_bytes());tables.append(nm)
  assert bins[0]==bins[1] and tables[0]==tables[1] and len(bins[0])==owner['bytes'];expected=bytearray(R[owner['start']:owner['end']])
  for edge in refs:
   if owner['start']<=edge['field']<owner['end']:
    target=translate(edge['target'])[0];value=((target-edge['bank'])&0xffffffff) if edge['kind']=='BANK_RELATIVE_U32' else 0x08000000+target+int(edge['thumb_bit']);struct.pack_into('<I',expected,edge['field']-owner['start'],value)
  assert bins[0]==expected,(name,'unexplained machine bytes after relink')
  table={p[2]:int(p[0],16) for line in tables[0].splitlines() if len(p:=line.split())>=3};assert table[entry]==base
  report=dict(name=name,object=owner['id'],old_start=owner['start'],new_start=base-0x08000000,bytes=len(bins[0]),source_hashes=hashes,binary_sha256=sha(bins[0]),AB_identical=True,entry_thumb_pointer=base|1,only_typed_literal_changes=True)
  if name=='hook':
   report['simple_thumb_pointer']=table['simple_font_hook']|1;assert len(bins[0])<0x400
   at=table['hangul_nibble_lut']-base;assert list(struct.unpack_from('<16H',bins[0],at))==[sum(15<<(4*b) for b in range(4) if n&(1<<b)) for n in range(16)]
  reports.append(report);blobs[owner['id']]=bins[0]
 return blobs,reports
