"""Conditional dynamic-font experiment. Not a release product build."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from build_visibility_poc import J,K,IPS,sha
from survey_rom import ips_records
from text_codec import hangul_map,glyph_index,encode
from ui_text import selected_ui
from project_profile import project
from small_table_text import selections as small_table_selections

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--ips',type=Path,required=True)
    p.add_argument('--glyphs',type=Path,required=True);p.add_argument('--toolchain',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--speakers',type=Path)
    p.add_argument('--skills',type=Path)
    p.add_argument('--actors',type=Path)
    p.add_argument('--default-names',type=Path)
    p.add_argument('--simple-hook',action='store_true')
    p.add_argument('--lexicon',type=Path)
    p.add_argument('--ui',type=Path)
    p.add_argument('--small-tables',type=Path)
    p.add_argument('--dialogue-fixes',type=Path)
    p.add_argument('--recipes',type=Path)
    p.add_argument('--battle-captions',type=Path)
    p.add_argument('--name-keyboard',action='store_true')
    p.add_argument('--skill-headers',action='store_true')
    p.add_argument('--biographies',action='store_true')
    a=p.parse_args();j=a.j.read_bytes();ips=a.ips.read_bytes()
    if sha(j)!=J or sha(ips)!=IPS:raise ValueError('Unsupported input')
    legacy=bytearray(j);records,trunc=ips_records(ips)
    if trunc:raise ValueError('Unexpected truncate')
    for o,d in records:legacy[o:o+len(d)]=d
    legacy=bytes(legacy)
    if sha(legacy)!=K:raise ValueError('Legacy reconstruction mismatch')
    if legacy[0x1a38:0x1a40]!=bytes.fromhex('281c20385f2817d8'):raise ValueError('Hook source differs')
    a.out.mkdir(parents=True,exist_ok=False)
    def run(program,args):
        # Some Windows binutils print localized paths in the system code page.
        # Only diagnostics are decoded; machine artifacts remain binary.
        result=subprocess.run([str(a.toolchain/(f'arm-none-eabi-{program}.exe')),*map(str,args)],check=True,capture_output=True)
        return result.stdout.decode('utf-8',errors='backslashreplace')
    run('as',['-mcpu=arm7tdmi','-mthumb',ROOT/'source/small_font_hook.s','-o',a.out/'hook.o'])
    objects=[a.out/'hook.o']
    if a.simple_hook:
        run('as',['-mcpu=arm7tdmi','-mthumb',ROOT/'source/simple_font_hook.s','-o',a.out/'simple-hook.o'])
        objects.append(a.out/'simple-hook.o')
    run('ld',['-Ttext=0x09000000','-e','small_font_hook',*objects,'-o',a.out/'hook.elf'])
    run('objcopy',['-O','binary','--only-section=.text',a.out/'hook.elf',a.out/'hook.bin'])
    dis=run('objdump',['-d','-m','armv4t',a.out/'hook.elf'])
    (a.out/'hook.disassembly.txt').write_text(dis,encoding='utf-8')
    code=(a.out/'hook.bin').read_bytes()
    if len(code)>0x1000:raise ValueError('Code/font collision')
    glyphs=json.loads(a.glyphs.read_text(encoding='utf-8'))
    font=bytearray(4096*8)
    for code_id,c in hangul_map().items():
        if c not in glyphs:continue # scoped experimental repertoire only
        rows=glyphs[c]
        if len(rows)!=8 or any(len(r)!=8 or set(r)-{'.','#'} for r in rows):raise ValueError('Invalid bitmap')
        packed=bytes(sum(1<<x for x,v in enumerate(row) if v=='#') for row in rows)
        if not any(packed):raise ValueError('Blank Hangul')
        index=glyph_index(code_id);font[index*8:index*8+8]=packed
    for c in '브라운':
        if c not in glyphs:raise ValueError('Missing required glyph')
    # New source area is explicitly appended: prior bytes are never reclaimed.
    extension=bytearray(b'\xff'*(0x2000000-len(legacy)))
    extension[:len(code)]=code;extension[0x1000:0x1000+len(font)]=font
    writes=[(0x1a38,bytes.fromhex('004b1847')+struct.pack('<I',0x09000001),'Thumb dispatch trampoline'),
            (0x1bde70,encode('브라운')+b'\0\0','Compact Brown name, protected 8-byte slot')]
    if a.simple_hook:
        if legacy[0x1ddc:0x1de4]!=bytes.fromhex('101c20385e2807d8'):raise ValueError('Simple consumer source differs')
        symbols=run('nm',['-g','--defined-only',a.out/'hook.elf'])
        entry=[int(line.split()[0],16)|1 for line in symbols.splitlines() if line.split()[-1]=='simple_font_hook']
        if len(entry)!=1:raise ValueError('Missing simple hook symbol')
        # r3 is the live source pointer here; only r0 is disposable.
        writes.insert(0,(0x1ddc,bytes.fromhex('00480047')+struct.pack('<I',entry[0]),'Simple string consumer shares protected glyph cache'))
    speaker_count=0
    skill_count=0;large_repairs=0;skill_description_repairs=0
    actor_count=0;actor_large=0
    lexicon_counts={}
    ui_count=0
    small_table_count=0
    if a.speakers:
        catalog=json.loads(a.speakers.read_text(encoding='utf-8'))
        if catalog['schema']!=1 or catalog['policy']!='development_only_needs_review' or len(catalog['names'])!=93:raise ValueError('Invalid speaker catalog')
        writes.pop() # Keep every original speaker string; update table + append only.
        cursor=0x9000
        linked={}
        for index,text in enumerate(catalog['names']):
            if text is None:continue
            if any('\uac00'<=c<='\ud7a3' and c not in glyphs for c in text):raise ValueError('Missing speaker glyph')
            encoded=encode(text)+b'\0'
            if len(text)>8:raise ValueError('Speaker exceeds observed name box budget')
            if text not in linked:
                cursor=(cursor+3)&~3;linked[text]=0x09000000+cursor
                extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
            offset=0xec7944+index*20+4
            original=struct.unpack_from('<I',legacy,offset)[0]
            if not 0x081bdb00<=original<0x081be200:raise ValueError('Speaker source outside table family')
            writes.append((offset,struct.pack('<I',linked[text]),f'speaker-{index:03d} compact name: {text}'))
            speaker_count+=1
        large_names=catalog.get('large_names',[None]*93)
        if len(large_names)!=93:raise ValueError('Invalid large speaker identity count')
        for index,text in enumerate(large_names):
            if text is None:continue
            if index in (43,44,49,50) or len(text)>8:raise ValueError('Invalid static large speaker selection')
            if text not in linked:
                encoded=encode(text)+b'\0';cursor=(cursor+3)&~3;linked[text]=0x09000000+cursor
                extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
            offset=0xec7944+index*20
            original=struct.unpack_from('<I',legacy,offset)[0]
            if not 0x081bdb00<=original<0x081be200:raise ValueError('Large speaker pointer outside table family')
            writes.append((offset,struct.pack('<I',linked[text]),f'speaker-{index:03d} user-selected large name: {text}'))
        if cursor>0xa000:raise ValueError('Speaker/skill allocation overlap')
    if a.skills:
        catalog=json.loads(a.skills.read_text(encoding='utf-8'))
        if catalog['schema']!=1 or catalog['policy']!='development_only_needs_review' or len(catalog['records'])!=390:raise ValueError('Invalid skill catalog')
        skill_profile=json.loads((ROOT/'source/skill_text_profile.json').read_text(encoding='utf-8'))
        if sha(legacy[0x741ddc:0x741ddc+390*20])!=skill_profile['table_sha256']:raise ValueError('Skill source table changed')
        for guard in skill_profile['guards']:
            off=int(guard['offset'],0);raw=bytes.fromhex(guard['hex'])
            if legacy[off:off+len(raw)]!=raw:raise ValueError('Skill text consumer changed')
        cursor=0xa000;linked={}
        for index,row in enumerate(catalog['records']):
            if row['id']!=f'skill-{index:03d}':raise ValueError('Skill identity/order differs')
            at=0x741ddc+index*20
            if sha(legacy[at:at+20])!=row['source_record_sha256']:raise ValueError('Skill identity metadata changed')
            for field,text in [(0,row['compact']),(4,row['large_repair']),(8,row.get('description_repair'))]:
                if text is None:continue
                if field==0 and any(not ('\uac00'<=c<='\ud7a3' or 0x20<=ord(c)<=0x7e or c=='･') for c in text):raise ValueError('Unsupported compact character/control')
                if any('\uac00'<=c<='\ud7a3' and c not in glyphs for c in text):raise ValueError('Missing skill glyph')
                # Current development selection must fit the observed longest
                # inherited string. This is NOT a proof of every caller's box.
                if len(text)>(18 if field==8 else 13):raise ValueError('Skill text exceeds selected window')
                if field==8:
                    ptr=struct.unpack_from('<I',legacy,at+8)[0]-0x08000000
                    if sha(legacy[ptr:legacy.index(0,ptr)+1])!=row['description_original_sha256']:raise ValueError('Skill description source changed')
                    if '%' in text or '\n' in text or any(ord(c)<32 for c in text):raise ValueError('Unmodeled skill description control')
                encoded=encode(text)+b'\0'
                if encoded not in linked:
                    cursor=(cursor+3)&~3;linked[encoded]=0x09000000+cursor
                    extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
                offset=0x741ddc+index*20+field
                ptr=struct.unpack_from('<I',legacy,offset)[0]
                if not 0x081000c4<=ptr<0x08114000:raise ValueError('Skill pointer outside established text family')
                writes.append((offset,struct.pack('<I',linked[encoded]),f'{row["id"]} { {0:"compact",4:"large repair",8:"description repair"}[field]}: {text}'))
                if field==0:skill_count+=1
                elif field==4:large_repairs+=1
                else:skill_description_repairs+=1
        if cursor>0x20000:raise ValueError('Skill allocation outside declared extension area')
    if a.actors:
        catalog=json.loads(a.actors.read_text(encoding='utf-8'))
        if catalog['schema']!=1 or catalog['policy']!='development_only_needs_review' or len(catalog['records'])!=96:raise ValueError('Invalid actor catalog')
        cursor=0x20000;linked={}
        for index,row in enumerate(catalog['records']):
            offset=0x1000e4+index*72
            if row['id']!=f'actor-{index:03d}' or sha(j[offset:offset+72])!=row['source_record_sha256']:raise ValueError('Actor identity changed')
            for field,text in [(4,row['compact']),(0,row['large'])]:
                if text is None:continue
                if len(text)>8:raise ValueError('Actor name exceeds current 8-cell development design')
                if field==4 and any(not ('\uac00'<=c<='\ud7a3' or 0x20<=ord(c)<=0x7e or c=='･') for c in text):raise ValueError('Unsupported compact actor code')
                if any('\uac00'<=c<='\ud7a3' and c not in glyphs for c in text):raise ValueError('Missing actor glyph')
                encoded=encode(text)+b'\0'
                if encoded not in linked:
                    cursor=(cursor+3)&~3;linked[encoded]=0x09000000+cursor
                    extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
                writes.append((offset+field,struct.pack('<I',linked[encoded]),f'{row["id"]} {"compact" if field==4 else "large"}: {text}'))
                if field==4:actor_count+=1
                else:actor_large+=1
        if cursor>0x30000:raise ValueError('Actor extension budget exceeded')
    if a.default_names:
        if legacy[0xd6754:0xd675c]!=bytes.fromhex('70b5051c0c1c1421'):raise ValueError('Name import source differs')
        run('as',['-mcpu=arm7tdmi','-mthumb',ROOT/'source/name_import.s','-o',a.out/'name-import.o'])
        run('ld',['-Ttext=0x09000400','-e','name_import',a.out/'name-import.o','-o',a.out/'name-import.elf'])
        run('objcopy',['-O','binary','--only-section=.text',a.out/'name-import.elf',a.out/'name-import.bin'])
        importer=(a.out/'name-import.bin').read_bytes()
        if len(code)>0x400 or len(importer)>0x400:raise ValueError('Name import allocation overlaps')
        extension[0x400:0x400+len(importer)]=importer
        writes.append((0xd6754,bytes.fromhex('004b1847')+struct.pack('<I',0x09000401),'Five-slot import: preserve complete double-byte characters'))
        names=json.loads(a.default_names.read_text(encoding='utf-8'))
        if names['schema']!=1 or names['policy']!='development_only_needs_review' or len(names['names'])!=3:raise ValueError('Invalid default-name catalog')
        cursor=0x30000
        for i,name in enumerate(names['names']):
            if not 1<=len(name)<=5 or any(c not in glyphs for c in name):raise ValueError('Default name outside five-slot Hangul repertoire')
            encoded=encode(name)+b'\0'
            if len(encoded)>13:raise ValueError('Default exceeds name conversion buffer')
            cursor=(cursor+3)&~3;ptr=0x09000000+cursor
            extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
            for base in (0x741dc4,0x741dd0):
                writes.append((base+i*4,struct.pack('<I',ptr),f'New-game default name {i}: {name}'))
    if a.lexicon:
        if not a.simple_hook:raise ValueError('Item/enemy experiments require both small consumers')
        lexicon=json.loads(a.lexicon.read_text(encoding='utf-8'))
        if lexicon['schema']!=1 or lexicon['policy']!='development_only_needs_review':raise ValueError('Invalid lexicon policy')
        for group,base,stride,count,start in [('item',0x105758,24,123,0x40000),('monster',0x1021ac,56,212,0x50000)]:
            rows=lexicon['groups'][group]
            if len(rows)!=count:raise ValueError('Lexicon population differs')
            cursor=start;linked={}
            for i,row in enumerate(rows):
                offset=base+i*stride;text=row['compact']
                if row['id']!=f'{group}-{i:03d}' or sha(j[offset:offset+stride])!=row['source_record_sha256']:raise ValueError('Lexicon identity/source differs')
                if any(not ('\uac00'<=c<='\ud7a3' or 0x20<=ord(c)<=0x7e or c=='･') for c in text):raise ValueError('Unsupported lexicon code')
                if any('\uac00'<=c<='\ud7a3' and c not in glyphs for c in text):raise ValueError('Missing lexicon glyph')
                encoded=encode(text)+b'\0'
                if len(encoded)>32 or len(text)>15:raise ValueError('Lexicon exceeds simple formatter 32-byte scratch or 15-cell development design')
                if encoded not in linked:
                    cursor=(cursor+3)&~3;linked[encoded]=0x09000000+cursor
                    extension[cursor:cursor+len(encoded)]=encoded;cursor+=len(encoded)
                writes.append((offset,struct.pack('<I',linked[encoded]),f'{row["id"]} compact: {text}'))
            if cursor>start+0x10000:raise ValueError('Lexicon allocation exceeds declared extent')
            lexicon_counts[group]=count
    if a.ui:
        profile=json.loads((ROOT/'source/ui_profile.json').read_text(encoding='utf-8'))
        catalog=json.loads(a.ui.read_text(encoding='utf-8'))
        selected=selected_ui(profile,catalog,legacy,glyphs)
        if a.actors:
            actors=json.loads(a.actors.read_text(encoding='utf-8'))['records']
            heading=next(r['text'] for r in catalog['records'] if r['id']=='menu-team')
            if any(len(heading.replace('%s',r['compact']))>9 for r in actors):raise ValueError('Selected actor name exceeds team heading width')
        cursor=0x60000
        for identity,offset,encoded in selected:
            cursor=(cursor+3)&~3
            if cursor+len(encoded)>0x70000:raise ValueError('UI allocation budget exceeded')
            extension[cursor:cursor+len(encoded)]=encoded
            writes.append((offset,struct.pack('<I',0x09000000+cursor),f'{identity} visible UI translation'))
            cursor+=len(encoded);ui_count+=1
    if a.small_tables:
        profile=json.loads((ROOT/'source/small_tables.json').read_text(encoding='utf-8'))
        catalog=json.loads(a.small_tables.read_text(encoding='utf-8'))
        cursor=0x70000
        for identity,offset,encoded in small_table_selections(profile,catalog,legacy,glyphs):
            cursor=(cursor+3)&~3
            if cursor+len(encoded)>0x80000:raise ValueError('Small table extension allocation exceeded')
            extension[cursor:cursor+len(encoded)]=encoded
            writes.append((offset,struct.pack('<I',0x09000000+cursor),f'{identity} established non-dialogue table'))
            cursor+=len(encoded);small_table_count+=1
    dialogue_count=0
    if a.dialogue_fixes:
        from dialogue_text import selections as dialogue_selections
        profile=json.loads((ROOT/'source/dialogue_fixes.json').read_text(encoding='utf-8'))
        catalog=json.loads(a.dialogue_fixes.read_text(encoding='utf-8'))
        cursor=0x80000
        for identity,offset,encoded in dialogue_selections(profile,catalog,j,legacy):
            cursor=(cursor+3)&~3
            if cursor+len(encoded)>0x90000:raise ValueError('Dialogue correction allocation exceeded')
            extension[cursor:cursor+len(encoded)]=encoded
            writes.append((offset,struct.pack('<I',0x09000000+cursor),f'{identity} verified dialogue correction'))
            cursor+=len(encoded);dialogue_count+=1
    recipe_count=0
    if a.recipes:
        from recipe_text import selections as recipe_selections
        profile=json.loads((ROOT/'source/recipe_profile.json').read_text(encoding='utf-8'))
        catalog=json.loads(a.recipes.read_text(encoding='utf-8'));cursor=0x90000
        for recipe_id,offset,encoded in recipe_selections(profile,catalog,j,legacy):
            cursor=(cursor+3)&~3
            if cursor+len(encoded)>0xa0000:raise ValueError('Recipe string allocation exceeded')
            extension[cursor:cursor+len(encoded)]=encoded
            writes.append((offset,struct.pack('<I',0x09000000+cursor),recipe_id+' typed recipe string'))
            cursor+=len(encoded);recipe_count+=1
    caption_count=0
    if a.battle_captions:
        from battle_captions import selections as caption_selections
        profile=json.loads((ROOT/'source/battle_caption_profile.json').read_text(encoding='utf-8'))
        catalog=json.loads(a.battle_captions.read_text(encoding='utf-8'))
        writes.extend(caption_selections(profile,catalog,legacy,glyphs));caption_count=len(catalog['records'])
    keyboard_info=None
    if a.name_keyboard:
        if not a.default_names or not a.simple_hook:raise ValueError('Keyboard requires importer and both font consumers')
        from name_keyboard import install as install_keyboard
        keyboard_writes,keyboard_info=install_keyboard(legacy,extension,a.out,run)
        writes.extend(keyboard_writes)
    expected=[];out=bytearray(legacy)
    prior_end=0
    header_info=None
    if a.skill_headers:
        from skill_header_graphics import install as install_headers
        header_writes,header_info=install_headers(legacy,extension,glyphs)
        writes.extend(header_writes)
    biography_info=None
    if a.biographies:
        from biography_text import install as install_biographies
        biography_writes,biography_info=install_biographies(legacy,extension)
        writes.extend(biography_writes)
    for o,d,_ in sorted(writes):
        if o<prior_end or o+len(d)>len(legacy):raise ValueError('Overlapping or out-of-range write')
        prior_end=o+len(d)
    for o,d,reason in writes:
        expected.append(dict(offset=hex(o),before=legacy[o:o+len(d)].hex(),after=d.hex(),reason=reason))
        out[o:o+len(d)]=d
    out.extend(extension)
    allowed={i for o,d,_ in writes for i in range(o,o+len(d))}
    if any(x!=y and i not in allowed for i,(x,y) in enumerate(zip(legacy,out))):raise ValueError('Unexplained diff')
    if out[0xddcc4:0x1000c4]!=legacy[0xddcc4:0x1000c4]:raise ValueError('Legacy fonts or mapping changed')
    from nontext_contract import protected_regions
    protected=protected_regions(out)
    identity=project()
    (a.out/identity['rom_file']).write_bytes(out)
    report=dict(status='EXPERIMENT_NOT_RELEASE',target_sha256=sha(out),base_sha256=J,legacy_sha256=K,
        font_glyphs=len(glyphs),speaker_entries=speaker_count,skill_entries=skill_count,large_skill_repairs=large_repairs,actor_entries=actor_count,large_actor_changes=actor_large,lexicon_entries=lexicon_counts,ui_entries=ui_count,code_size=len(code),extension_size=len(extension),extension_sha256=sha(extension),writes=expected,
        inputs={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):sha(p.read_bytes()) for p in [a.glyphs,ROOT/'source/small_font_hook.s',*([a.speakers] if a.speakers else []),*([a.skills] if a.skills else []),*([a.actors] if a.actors else []),*([a.default_names,ROOT/'source/name_import.s'] if a.default_names else []),*([ROOT/'source/simple_font_hook.s'] if a.simple_hook else []),*([a.lexicon] if a.lexicon else [])]},
        limits=['124 active cached glyphs; remaining consumer paths and lifetime unverified','exhaustion deliberately emits ? as visible development failure','player-created names follow a separate path','32MB expansion requires target-device verification'])
    if a.ui:
        for path in [a.ui,ROOT/'source/ui_profile.json',ROOT/'tools/ui_text.py']:
            report['inputs'][str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)]=sha(path.read_bytes())
    report.update(version=identity['version'],rom_file=identity['rom_file'],stage=identity['stage'])
    report['small_table_entries']=small_table_count
    report['dialogue_corrections']=dialogue_count
    report['recipe_string_fields']=recipe_count
    report['battle_caption_sprites']=caption_count
    report['name_keyboard']=keyboard_info
    report['skill_header_graphics']=header_info
    report['biography_text']=biography_info
    report['skill_description_repairs']=skill_description_repairs
    if a.biographies:
        for name in ['source/biography_profile.json','translations/biographies.json','tools/biography_text.py']:
            report['inputs'][name]=sha((ROOT/name).read_bytes())
    if a.skill_headers:
        for name in ['source/skill_header_profile.json','translations/skill_headers.json','tools/skill_header_graphics.py']:
            report['inputs'][name]=sha((ROOT/name).read_bytes())
    if a.name_keyboard:
        for name in ['source/name_keyboard.s','source/name_keyboard_profile.json','translations/name_keyboard.json','tools/name_keyboard.py']:
            report['inputs'][name]=sha((ROOT/name).read_bytes())
    if a.battle_captions:
        for path in [a.battle_captions,ROOT/'source/battle_caption_profile.json',ROOT/'tools/battle_captions.py']:
            report['inputs'][str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)]=sha(path.read_bytes())
    if a.recipes:
        for path in [a.recipes,ROOT/'source/recipe_profile.json',ROOT/'tools/recipe_text.py']:
            report['inputs'][str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)]=sha(path.read_bytes())
    if a.dialogue_fixes:
        for path in [a.dialogue_fixes,ROOT/'source/dialogue_fixes.json',ROOT/'tools/dialogue_text.py']:
            report['inputs'][str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)]=sha(path.read_bytes())
    if a.small_tables:
        for path in [a.small_tables,ROOT/'source/small_tables.json',ROOT/'tools/small_table_text.py']:
            report['inputs'][str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)]=sha(path.read_bytes())
    report['inputs']['project.json']=sha((ROOT/'project.json').read_bytes())
    report['protected_nontext_regions']=protected
    report['inputs']['source/nontext_profile.json']=sha((ROOT/'source/nontext_profile.json').read_bytes())
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('writes','inputs')},ensure_ascii=False))
if __name__=='__main__':main()
