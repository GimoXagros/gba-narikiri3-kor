"""Adopted repaired 16MiB packing with freshly generated payloads and relinked code."""
import bisect,hashlib,json,struct,subprocess
from pathlib import Path
import numpy as np
from gba_rle import unpack
from packing_codecs import rle,optimal_lz77
from relink_release import relink
sha=lambda b:hashlib.sha256(b).hexdigest()
def pack(R,P,objects,references,toolchain,out):
 assert sha(R)==P["ROM_sha256"] and len(R)==0x2000000
 objs=objects+P['auxiliary_objects'];refs=references+P['auxiliary_refs'];chosen=P['attempts']['merged_mixed'];assert not chosen['failures']
 holes=sorted(P['merged_holes'],key=lambda x:x['start']);assert all(x['end']<=y['start'] for x,y in zip(holes,holes[1:]))
 for h in P['holes']:assert sha(R[h['start']:h['end']])==h['expected_sha256']
 locations={x['object']:x['new_start'] for x in chosen['placements']}
 for x in P['strict_restores']:
  if x['fit']:locations[x['object']]=x['original_start']
 locations['RAW_4BPP_ATLAS-01130000']=0xf1d8f4
 pending=list(P['aliases'])
 while pending:
  done=[]
  for x in pending:
   if x['canonical'] in locations:locations[x['object']]=locations[x['canonical']]+x.get('offset',0);done.append(x)
  assert done,'unresolved alias cycle'
  for x in done:pending.remove(x)
 moved=sorted([o for o in objs if o['id'] in locations],key=lambda x:x['start']);starts=[o['start'] for o in moved]
 def translate(at):
  i=bisect.bisect_right(starts,at)-1
  if i>=0 and at<moved[i]['end']:
   o=moved[i];return locations[o['id']]+at-o['start'],o['id']
  return at,None
 out.mkdir(parents=True)
 # Actual ARM7 object files/ELFs built twice at exact installed locations.
 code,code_reports=relink(R,objs,locations,translate,refs,out/'emitted-code',toolchain)
 payloads={};write_specs={}
 def object_payload(o):
  if o['id'] in code:return code[o['id']]
  if o['id']=='RAW_4BPP_ATLAS-01130000':return R[0x1130000:0x1137880]
  if o['id']=='BIOS_RLE-01137880':return optimal_lz77(unpack(R,0xf1d734+struct.unpack_from('<I',R,0xf1d754)[0],len(R),1280)[0])
  if o['kind']=='BIOS_RLE':
   raw,end=unpack(R,o['start'],o['end'],int.from_bytes(R[o['start']+1:o['start']+4],'little'));assert end==o['end'];return rle(raw)
  return R[o['start']:o['end']]
 byid={o['id']:o for o in objs};aliases={x['object'] for x in P['aliases']}
 for placement in chosen['placements']:
  o=byid[placement['object']];blob=object_payload(o);assert len(blob)==placement['bytes'];guard=placement['strlen_guard_bytes']
  if guard:
   assert o['kind']=='CSTRING' and blob.endswith(b'\0');blob+=R[o['end']:o['end']+guard]
  assert len(blob)==placement['allocated_bytes'];at=placement['new_start'];assert any(h['start']<=at and at+len(blob)<=h['end'] for h in holes)
  payloads[o['id']]=bytearray(blob);write_specs[o['id']]=(at,at+len(blob))
 for x in P['strict_restores']:
  if not x['fit']:continue
  o=byid[x['object']];blob=object_payload(o);assert len(blob)==x['new_bytes'] and len(blob)<=x['original_capacity'];at=x['original_start'];payloads[o['id']]=bytearray(blob);write_specs[o['id']]=(at,at+x['original_capacity'])
 atlas='RAW_4BPP_ATLAS-01130000';payloads[atlas]=bytearray(object_payload(byid[atlas]));write_specs[atlas]=(0xf1d8f4,0xf25174)
 independent=[];edges=[]
 for edge in refs:
  field,fo=translate(edge['field']);target,to=translate(edge['target'])
  if field==edge['field'] and target==edge['target']:continue
  assert 0<=field<0x1000000 and 0<=target<0x1000000
  value=((target-edge['bank'])&0xffffffff) if edge['kind']=='BANK_RELATIVE_U32' else 0x08000000+target+int(edge['thumb_bit']);blob=struct.pack('<I',value)
  if edge['kind']=='BANK_RELATIVE_U32':assert ((edge['bank']+value)&0xffffffff)==target
  row={**edge,'B2_field':field,'B2_target':target,'B2_hex':blob.hex(),'field_owner':fo,'target_owner':to};edges.append(row)
  if fo:
   assert fo in payloads and fo not in aliases;at=field-locations[fo];assert 0<=at<=len(payloads[fo])-4;payloads[fo][at:at+4]=blob
  else:independent.append((field,blob,row))
 C=bytearray(R[:0x1000000]);mask=np.zeros(len(C),dtype=bool);writes=[]
 def write(label,at,blob,end):
  assert 0<=at<at+len(blob)<=end<=len(C) and not mask[at:at+len(blob)].any(),(label,'writer collision')
  mask[at:at+len(blob)]=True;C[at:at+len(blob)]=blob;writes.append(dict(writer=label,start=at,end=at+len(blob),owner_end=end,expected_before_sha256=sha(R[at:at+len(blob)]),payload_sha256=sha(blob)))
 boot=rle(R[0xfbb600:0xfce200]);assert len(boot)==7507 and unpack(boot,0,len(boot),76800)[0]==R[0xfbb600:0xfce200]
 write('approved exactbootRLE',0xfbb600,boot,0xfbd354)
 before=R[0xfce200:0xfce284];assert sha(before)==P['original_boot_loader_sha256']
 boot_folder=out/'boot-loader';boot_folder.mkdir();(boot_folder/'loader_before.bin').write_bytes(before)
 root=Path(__file__).resolve().parents[1]
 def arm_tool(name,args):return subprocess.check_output([str(toolchain/('arm-none-eabi-'+name+'.exe')),*map(str,args)],cwd=boot_folder)
 arm_tool('as',['-mcpu=arm7tdmi',root/'source/boot_forcedblank.s','-o','boot.o'])
 arm_tool('ld',['-Ttext=0x08fce200','-e','loader_start','boot.o','-o','boot.elf'])
 arm_tool('objcopy',['-O','binary','--only-section=.text','boot.elf','boot.bin'])
 loader=(boot_folder/'boot.bin').read_bytes()
 if len(loader)!=132 or loader[:12]!=before[:12] or loader[48:92]!=before[48:92] or loader[96:]!=before[96:]:raise ValueError('Assembled loader modified protected source')
 (boot_folder/'disassembly.txt').write_bytes(arm_tool('objdump',['-d','-m','armv4t','boot.elf']))
 write('assembled bootv2 ARM36B',0xfce20c,loader[12:48],0xfce230);write('assembled forcedblankliteral',0xfce25c,loader[92:96],0xfce260)
 for oid,blob in payloads.items():at,end=write_specs[oid];write(oid,at,blob,end)
 for field,blob,row in independent:write('typedfield '+hex(field),field,blob,field+4)
 C=bytes(C);delta=np.frombuffer(R[:0x1000000],np.uint8)!=np.frombuffer(C,np.uint8);assert not np.any(delta & ~mask) and len(C)==16777216
 for row in edges:
  value=struct.unpack_from('<I',C,row['B2_field'])[0];target=((row['bank']+value)&0xffffffff) if row['kind']=='BANK_RELATIVE_U32' else (value&~int(row['thumb_bit']))-0x08000000;assert target==row['B2_target']
 content=[]
 for o in moved:
  at=locations[o['id']]
  if o['kind']=='CSTRING':
   old=R[o['start']:o['end']];assert C[at:at+len(old)]==old;content.append(dict(object=o['id'],B2_start=at,bytes=len(old),payload_sha256=sha(old),exact=True))
 assert C[0xddcc4:0x1000c4]==R[0xddcc4:0x1000c4]
 return C,dict(ROM_sha256=sha(C),ROM_bytes=len(C),locations=locations,placements=chosen['placements'],typed_edges=edges,emitted_code=code_reports,writes=writes,CString_identity=content,changed_bytes=int(delta.sum()),unexplained_changes=0)
