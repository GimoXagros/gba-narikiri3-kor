"""Assemble/apply fixed-address large-text and sprite-display wrappers.

All stored pointers and ROM size are preserved. Inputs must already contain the
separate description/UI text plan. No implicit file paths or ROM discovery.
"""
import json, subprocess
from pathlib import Path
PROGRAMS={
 'popup_names': [('text',0xfbba2c)],
 'skill_half': [('text',0xe73530)],
 'sprite_half': [('predicate',0xe7304c),('writer',0xe74778),('position',0xe74430),('count',0xe73204),('ascii',0xe73c0c)],
 'large_remaining': [('normalize',0xe73a6c),('mission',0xe73dc8)],
 'title_half': [('title',0xe738ac)],
 'caption_half': [('caption',0x167b0)],
}
PLANS=['SKILL_NAME_WRITE_PLAN.json','SPRITE_WRITE_PLAN.json','MISSION_WRITE_PLAN.json','TITLE_CAPTION_WRITE_PLAN.json','DIRECT_LARGE_WRITE_PLAN.json','FORWARDED_LARGE_WRITE_PLAN.json','POPUP_NAMES_WRITE_PLAN.json','FORWARDER_HELP_WRITE_PLAN.json']
def apply(base,toolchain,outdir,source_dir=None):
 source_dir=Path(source_dir or Path(__file__).resolve().parents[1]/'source/v13b/consumers');outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 assert len(base)==0x1000000,'ROM must stay 16 MiB'
 def tool(name):
  p=Path(toolchain)/('arm-none-eabi-'+name+'.exe');return str(p if p.exists() else p.with_suffix(''))
 assembled={}
 for stem,sections in PROGRAMS.items():
  obj=outdir/(stem+'.o');elf=outdir/(stem+'.elf');ld=source_dir/(stem+'.ld')
  if not ld.exists():
   assert len(sections)==1;section,at=sections[0];ld=outdir/(stem+'.ld');ld.write_text('SECTIONS { .text 0x%08x : { *(.text) } }'%(0x8000000+at),'ascii')
  subprocess.run([tool('as'),'-mcpu=arm7tdmi','-mthumb','-o',str(obj),str(source_dir/(stem+'.s'))],check=True)
  subprocess.run([tool('ld'),'-T',str(ld),'-o',str(elf),str(obj)],check=True)
  for section,at in sections:
   file=outdir/(stem+'-'+section+'.bin');subprocess.run([tool('objcopy'),'-O','binary','--only-section=.'+section,str(elf),str(file)],check=True);assembled[at]=file.read_bytes()
 result=bytearray(base);all_writes=[]
 for name in PLANS:
  plan=json.loads((source_dir/name).read_text('utf8'))
  for row in plan['writes']:
   at=row['offset'];expected=bytes.fromhex(row['before_hex']);payload=assembled.get(at,bytes.fromhex(row['payload_hex']))
   assert len(payload)==len(expected) and result[at:at+len(expected)]==expected,(hex(at),'guard drift')
   assert payload==bytes.fromhex(row['payload_hex']),(hex(at),'assembly drift')
   result[at:at+len(payload)]=payload;all_writes.append(row)
 assert len(result)==len(base)
 return bytes(result),dict(writes=all_writes,rom_size=len(result),source_strings_moved=0,source_pointer_writes=0)
