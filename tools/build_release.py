"""Explicit JP+legacy IPS → adopted translation → owned 16MiB → menu build.

No completed ROM or historical output directory is an input. Historical exact
hashes are checkpoints; adopted assets are editable raster/wording sources.
"""
import argparse, hashlib, json, struct, subprocess, sys
from pathlib import Path
import numpy as np
from project_profile import project
from survey_rom import ips_records
from tone_inplace import inventory, apply_overlay
from proofread_control import prepare_plan
from adopted_graphics import build as additional_graphics
from intro_graphics_stage import optimal_rle
from pack_release16 import pack
from bps import create_bps, apply_bps

ROOT=Path(__file__).resolve().parents[1]
ADOPTED=ROOT/'source/v13_adopted'
JP='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394'
OPT16='167323a79da8dddf64780b7ea706e44721c5cc647034300ee25239749547420c'
def sha(blob):return hashlib.sha256(blob).hexdigest()
def read(path):return json.loads(path.read_text('utf-8'))
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')

def apply_writes(base,writes):
    result=bytearray(base); mask=np.zeros(len(base),np.bool_); ledger=[]
    for row in sorted(writes,key=lambda x:x['offset']):
        at=row['offset'];data=row['payload'];end=at+len(data)
        if not 0<=at<end<=row['allowed_end']<=len(base) or mask[at:end].any():raise ValueError('Writer range/overlap: '+row['writer'])
        if sha(base[at:end])!=row['expected_sha256']:raise ValueError('Writer source guard: '+row['writer'])
        result[at:end]=data;mask[at:end]=True
        ledger.append({k:v for k,v in row.items() if k!='payload'}|{'payload_sha256':sha(data),'bytes':len(data)})
    result=bytes(result)
    if np.any((np.frombuffer(base,np.uint8)!=np.frombuffer(result,np.uint8))&~mask):raise ValueError('Unexplained change')
    return result,ledger

def assemble(tc,out,names,base,entry):
    out.mkdir(parents=True)
    def run(tool,args):return subprocess.check_output([str(tc/('arm-none-eabi-'+tool+'.exe')),*map(str,args)])
    objects=[]
    for name in names:
        target=out/(name+'.o');run('as',['-mcpu=arm7tdmi','-mthumb',ROOT/'source'/name,'-o',target]);objects.append(target)
    elf=out/'code.elf';run('ld',[f'-Ttext={hex(base)}','-e',entry,*objects,'-o',elf])
    run('objcopy',['-O','binary','--only-section=.text',elf,out/'code.bin'])
    nm=run('nm',['-a','--special-syms','--defined-only',elf]).decode('utf-8')
    (out/'disassembly.txt').write_bytes(run('objdump',['-d','-m','armv4t',elf]))
    table={p[2]:int(p[0],16) for line in nm.splitlines() if len(p:=line.split())>=3}
    return (out/'code.bin').read_bytes(),table

def rectangular(p):
    h,w=p.shape
    if h%8 or w%8:raise ValueError('Raster tile alignment')
    return bytes(int(p[ty*8+y,tx*8+x])|int(p[ty*8+y,tx*8+x+1])<<4 for ty in range(h//8) for tx in range(w//8) for y in range(8) for x in range(0,8,2))

def asset_payloads(assets):
    payloads={}
    for unit in assets['fixed_units']+assets['native_units']:
        kind=unit['kind'];raw=bytes.fromhex(unit['raster_index_hex'])
        dims={'town':(16,64),'title':(32,96),'group':(8,64),'native80':(16,80)}
        if kind in dims:h,w=dims[kind]
        else:
            h,w=(16,64) if unit.get('bank')=='0xe72ee0' else ((32,96) if unit.get('bank')=='0xe717cc' and unit.get('index')==2 else (32,64))
        pixels=np.frombuffer(raw,np.uint8).reshape(h,w)
        if np.any(pixels>15):raise ValueError('4bpp palette overflow')
        for half,row in enumerate(unit['resources']):
            if kind in ('town','group'):decoded=rectangular(pixels[:,32*half:32*(half+1)])
            elif kind=='title':decoded=rectangular(pixels[:,:64])+rectangular(pixels[:,64:])
            elif kind=='native80':decoded=b''.join(rectangular(pixels[:,x:min(x+32,w)]) for x in range(0,w,32))
            elif kind=='native_fixed' and w==96:decoded=rectangular(pixels[:,64:])+rectangular(pixels[:,:64])
            elif kind=='native_fixed' and unit.get('bank')=='0xe72ee0':decoded=rectangular(pixels[:,32:])+rectangular(pixels[:,:32])
            else:decoded=rectangular(pixels)
            packed=optimal_rle(decoded)
            if sha(decoded)!=row['new_decoded_sha256'] or sha(packed)!=row['new_stored_sha256']:raise ValueError('Editable raster regeneration differs '+row['resource_id'])
            payloads[row['resource_id']]=packed
    return payloads

def graphics_overlays(base,assets,tc,out):
    from gba_rle import unpack
    payloads=asset_payloads(assets)
    def stage(rows,cursor,frames=None,allocator=None):
        nonlocal base
        writes=[]
        def write(label,at,data,end):writes.append(dict(writer=label,offset=at,payload=data,allowed_end=end,expected_sha256=sha(base[at:at+len(data)])))
        for row in rows:
            bank=int(row['bank'],0);field=int(row['pointer_field'],0);at=int(row['source_start'],0);end=int(row['source_consumed_end'],0)
            if base[field:field+4].hex()!=row['expected_field_hex'] or sha(base[at:end])!=row['source_stored_sha256']:raise ValueError('Adopted graphic source identity differs')
            old,used=unpack(base,at,end,int.from_bytes(base[at+1:at+4],'little'))
            if used!=end or sha(old)!=row['source_decoded_sha256']:raise ValueError('Adopted graphic source decoded identity differs')
            blob=payloads[row['resource_id']]
            if row['strict_original_slot_fit']:
                target=at;owner=int(row['original_JP_consumed_end'],0)
            else:
                target=(cursor+3)&~3;cursor=target+len(blob);owner=0x11a0000
                write(row['resource_id']+' bank',field,struct.pack('<I',(target-bank)&0xffffffff),field+4)
            write(row['resource_id']+' editable raster',target,blob,owner)
        if frames:
            descriptor=(cursor+3)&~3;blob=bytes.fromhex(frames[0]['descriptor_hex']);cursor=descriptor+len(blob);write('shared header components',descriptor,blob,0x11a0000)
            for row in frames:
                at=(cursor+3)&~3;cursor=at+8;write(row['unit_id']+' frame',at,struct.pack('<II',1,0x08000000+descriptor),0x11a0000)
                field=int(row['frame_pointer_field'],0)
                if base[field:field+4].hex()!=row['expected_field_hex']:raise ValueError('Header frame identity')
                write(row['unit_id']+' header frame field',field,struct.pack('<I',0x08000000+at),field+4)
        if allocator:
            at=int(allocator['function_start'],0);end=int(allocator['function_end'],0)
            code,_=assemble(tc,out/'native-allocator',['native_dynamic_allocator.s'],0x08000000+at,'native_dynamic_start')
            if sha(base[at:end])!=allocator['before_sha256'] or sha(code)!=allocator['after_sha256']:raise ValueError('Selective allocator machine source differs')
            write('selective native allocator source',at,code,end)
        base,ledger=apply_writes(base,writes);return ledger,cursor
    fixed,cursor=stage(assets['fixed_resources'],0x1193e54)
    if sha(base)!='f7ac440b19a59128102a8d6fa7a4008ba92a241ff6fdb2f780bbdf1d669f32b6':raise ValueError('Fixed graphics historical checkpoint differs')
    native_rows=[r for u in assets['native_units'] for r in u['resources']]
    native,cursor=stage(native_rows,0x1194284,assets['native_frames'],read(ADOPTED/'native_allocator.json'))
    if sha(base)!='d6090e3c55fdf15dd7057689c229fbb893857db82ad47c7be2157dad5d62e48a':raise ValueError('Native graphics historical checkpoint differs')
    return base,{'fixed':fixed,'native':native,'arena_end':cursor}

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--ips',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    mode=p.add_mutually_exclusive_group();mode.add_argument('--baseline-only',action='store_true');mode.add_argument('--diagnostic-field-list',action='store_true');a=p.parse_args()
    if a.out.exists():p.error('Fresh output directory required')
    inputs={name:getattr(a,name).resolve() for name in ['j','ips']};data={name:path.read_bytes() for name,path in inputs.items()}
    if len(data['j'])!=0x1000000 or sha(data['j'])!=JP:raise ValueError('Exact Japanese B3TJ required')
    records,trunc=ips_records(data['ips']);legacy=bytearray(data['j'])
    if trunc:raise ValueError('Legacy IPS must not truncate')
    for at,blob in records:legacy[at:at+len(blob)]=blob
    legacy=bytes(legacy)
    if sha(legacy)!='8440f3e3db46c474c81cf84098798f07ab91aa13d48431c523c309a0af363010':raise ValueError('Exact legacy 1.1 IPS required')
    a.out.mkdir(parents=True);stage=a.out/'cumulative';args=['--j',a.j,'--ips',a.ips,'--toolchain',a.toolchain,'--out',stage,'--hook-source-dir',ROOT/'source/v12_hooks','--glyphs',ROOT/'fonts/dalmoori-wansung.json']
    for flag,file in [('speakers','speakers'),('skills','skills'),('actors','actors'),('default-names','default_names'),('lexicon','items-monsters'),('ui','ui'),('small-tables','small_tables'),('dialogue-fixes','dialogue_fixes'),('recipes','recipes'),('battle-captions','battle_captions')]:args+=['--'+flag,ROOT/f'translations/{file}.json']
    args+=['--dialogue-pool','review','--deduplicate-dialogue']
    for flag in ['simple-hook','name-keyboard','skill-headers','biographies','clothing-results','save-places','notices','inspect-eye','element-symbols','item-descriptions','mission-conditions','review-ui','splash-credit','costume-label','town-labels','title-staff','monster-descriptions']:args+=['--'+flag]
    with (a.out/'cumulative.log').open('w',encoding='utf-8') as log:subprocess.run([sys.executable,'-X','utf8',ROOT/'tools/build_small_font_experiment.py',*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    base=(stage/project()['rom_file']).read_bytes();checkpoints={}
    def check(name,blob,digest):
        if sha(blob)!=digest:raise ValueError(name+' historical checkpoint differs: '+sha(blob))
        checkpoints[name]=dict(bytes=len(blob),sha256=sha(blob));print(name,sha(blob),flush=True)
    check('v12',base,'8953b6a98a9b39e340aecdc74739598ee47c4d59088f688e471a81c289a67793')
    book=inventory(data['j'],legacy,base);base,tone_writes=apply_overlay(base,book,read(ROOT/'source/tone_full_review.json'));check('tone',base,'4c77deb68942d863642d2404202b4e1555b25f25f075a75fc3f43452a468151f')
    proof,writes,_=prepare_plan(base,data['j'],legacy,read(ADOPTED/'proofread.json'));base,proof_ledger=apply_writes(base,writes);check('proofread',base,'a1278ade7a168ac12c8ad859b07cd43f754107047133459956b7734957dbdb45')
    code,symbols=assemble(a.toolchain,a.out/'early-hook',['small_font_hook.s','simple_font_hook.s'],0x09000000,'small_font_hook')
    hook_writes=[dict(writer='early optimized hook',offset=0x1000000,payload=code,allowed_end=0x1000400,expected_sha256=sha(base[0x1000000:0x1000000+len(code)])),dict(writer='early simple entry',offset=0x1de0,payload=struct.pack('<I',symbols['simple_font_hook']|1),allowed_end=0x1de4,expected_sha256=sha(base[0x1de0:0x1de4]))]
    base,hook_ledger=apply_writes(base,hook_writes);check('early_performance',base,'8207ba4bfa6721a59cfede08e3cab17fa13b2fe2013fa7d55cf07c330749b39f')
    cumulative=proof['writes']+[{k:v for k,v in row.items() if k!='payload'}|{'payload_hex':row['payload'].hex()} for row in hook_writes]
    base,graphics=additional_graphics(base,data['j'],ADOPTED,cumulative);check('B0',base,'92140d48309d94dbecde2d129b64fd900d7ba41d68bdd22c671b9e7b18c0ea38')
    base,b1=graphics_overlays(base,read(ADOPTED/'graphics_assets.json'),a.toolchain,a.out);check('PRE32',base,'d6090e3c55fdf15dd7057689c229fbb893857db82ad47c7be2157dad5d62e48a')
    normal32=base
    base,b2=pack(base,read(ADOPTED/'packing16.json'),read(ADOPTED/'objects32.json'),read(ADOPTED/'references32.json'),a.toolchain,a.out/'packed16');check('PRE16',base,'4d8c1b15ec7f6dce6ef54b66953bd9d5faa10290c8c089f2b2bbabff58ecfed9')
    writes=[]
    for names,at,entry,extent in [(['description_pixel_kernel.s'],0x11a8,'pixel_even',620),(['menu_hook_16.s'],0xfc6a90,'small_font_hook',788)]:
        code,table=assemble(a.toolchain,a.out/entry,names,0x08000000+at,entry)
        if len(code)!=extent:raise ValueError('Menu optimized source extent')
        writes.append(dict(writer=entry,offset=at,payload=code,allowed_end=at+extent,expected_sha256=sha(base[at:at+extent])))
    base,menu=apply_writes(base,writes);check('OPT16',base,OPT16)
    fixes={};status='CLEAN_SOURCE_OPT16_REPRODUCED';stem='ND3_CLEAN_OPT16'
    if a.diagnostic_field_list:
        from v13_fixes import field_and_list
        fix_writes,fixes=field_and_list(base);base,fix_ledger=apply_writes(base,fix_writes);fixes['writes']=fix_ledger
        check('FIELD_LIST_V4',base,'c05242a8f11576c23a2ea7f3e2dfb92dcd52032b0bd054091eb3bbf4531f21dc')
        status='PRIVATE_FIELD_LIST_INTERMEDIATE_NOT_RC_MAP_NAMES_AND_OTHER_GATES_PENDING';stem='ND3_FIELD_LIST_V4_FROM_SOURCE'
    elif not a.baseline_only:
        from v13_fixes import final_fixes
        fix_writes,fixes=final_fixes(base);base,fix_ledger=apply_writes(base,fix_writes);fixes['writes']=fix_ledger
        check('RC16',base,'decedfd15fafe621be14edd2375a0c9f8f23ce99fceaf3f1abf44a00347526e4')
        status='PRIVATE_V13_RC16_ALL_SOURCE_BINDINGS_FINAL_INDEPENDENT_AND_HARDWARE_GATES_PENDING';stem='ND3_B3TJ_K_v1.3_RC16'
        normal_menu=[]
        for names,at,entry,extent in [(['description_pixel_kernel.s'],0x11a8,'pixel_even',620),(['menu_hook_32.s'],0x1000000,'small_font_hook',788)]:
            code,_=assemble(a.toolchain,a.out/('normal32-'+entry),names,0x08000000+at,entry)
            if len(code)!=extent:raise ValueError('Normal32 menu source extent')
            normal_menu.append(dict(writer='normal32 '+entry,offset=at,payload=code,allowed_end=at+extent,expected_sha256=sha(normal32[at:at+extent])))
        normal32,normal_menu_ledger=apply_writes(normal32,normal_menu)
        check('OPT32',normal32,'beca7cb1b008224841e610e73de08cfb538238be017fac1ba8dc0689e63155be')
        normal_writes,normal_fixes=final_fixes(normal32,True);normal32,normal_ledger=apply_writes(normal32,normal_writes)
        checkpoints['FIX32']=dict(bytes=len(normal32),sha256=sha(normal32))
        normal_fixes['writes']=normal_ledger
        normal_patch=create_bps(data['j'],normal32,b'ND3 v1.3 normal32 private source counterpart; hardware gates pending')
        if apply_bps(data['j'],normal_patch)!=normal32:raise ValueError('Normal32 cumulative BPS roundtrip')
        normal_name='ND3_B3TJ_K_v1.3_FIX32'
        (a.out/(normal_name+'.gba')).write_bytes(normal32);(a.out/(normal_name+'_FROM_J.bps')).write_bytes(normal_patch)
        dump(a.out/'NORMAL32_MANIFEST.json',dict(status='PRIVATE_NORMAL32_SOURCE_COUNTERPART_NOT_PUBLIC_RELEASE',ROM_file=normal_name+'.gba',ROM_sha256=sha(normal32),ROM_bytes=len(normal32),BPS_sha256=sha(normal_patch),menu=normal_menu_ledger,fixes=normal_fixes,new_extension_list_table_arena=[0x11a0000,0x11a0060]))
        dump(a.out/'EXPECTED_WRITES.json',dict(baseline_sha256=OPT16,ROM_sha256=sha(base),ROM_bytes=len(base),writes=fix_ledger,bindings={k:v for k,v in fixes.items() if k!='writes'}))
    patch=create_bps(data['j'],base,b'ND3 v1.3 clean-source private diagnostic; required final gates separate')
    if apply_bps(data['j'],patch)!=base:raise ValueError('Cumulative BPS roundtrip')
    (a.out/(stem+'.gba')).write_bytes(base);(a.out/(stem+'_FROM_J.bps')).write_bytes(patch)
    source_files=[ROOT/'project.json',ROOT/'requirements-dev.txt',*sorted((ROOT/'tools').glob('*.py')),*sorted((ROOT/'source').rglob('*')),*sorted((ROOT/'translations').glob('*.json')),*sorted((ROOT/'fonts').glob('*.json'))]
    source_hashes={f.relative_to(ROOT).as_posix():sha(f.read_bytes()) for f in source_files if f.is_file()}
    report={'status':status,'checkpoints':checkpoints,'ROM_file':stem+'.gba','ROM_sha256':sha(base),'ROM_bytes':len(base),'BPS_sha256':sha(patch),'input_sha256':{k:sha(v) for k,v in data.items()},'source_sha256':source_hashes,'toolchain_sha256':{tool:sha((a.toolchain/('arm-none-eabi-'+tool+'.exe')).read_bytes()) for tool in ['as','ld','objcopy','objdump','nm']},'stages':{'tone_writes':[{k:v for k,v in row.items() if k!='data'} for row in tone_writes],'proofread':proof_ledger,'early_hook':hook_ledger,'graphics':graphics,'B1':b1,'B2':b2,'menu':menu,'fixes':fixes}}
    dump(a.out/'BUILD_MANIFEST.json',report)
    for name,path in inputs.items():
        if path.read_bytes()!=data[name]:raise ValueError('Input mutated during build')
    print(report['status'],flush=True)
if __name__=='__main__':main()
