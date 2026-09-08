"""Create a cumulative, local-only development review package after hash checks."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from bps import create_bps,apply_bps
from build_visibility_poc import J,sha
from project_profile import project,rom_path

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    source=a.j.read_bytes();m=json.loads((a.build/'manifest.json').read_text(encoding='utf-8'))
    target=rom_path(a.build,m).read_bytes()
    if sha(source)!=J or len(source)!=0x1000000 or sha(target)!=m['target_sha256']:raise ValueError('Source/target mismatch')
    if m['status']!='EXPERIMENT_NOT_RELEASE':raise ValueError('This packager is only for development evidence')
    checks={}
    required=['consumer-verification.json','name-import-verification.json']
    if any(w['offset']=='0x1ddc' for w in m['writes']):required.append('simple-consumer-verification.json')
    if m.get('lexicon_entries'):required.append('integrated-name-verification.json')
    if m.get('ui_entries'):required.append('ui-verification.json')
    if m.get('small_table_entries'):required.append('small-tables-verification.json')
    if m.get('dialogue_corrections'):required.extend(['name-expansion-verification.json','dialogue-resource-verification.json'])
    if m.get('recipe_string_fields'):required.append('recipe-verification.json')
    if m.get('battle_caption_sprites'):required.append('battle-caption-verification.json')
    for filename in required:
        c=json.loads((a.build/filename).read_text(encoding='utf-8'))
        if c['status']!='PASS' or c['rom_sha256']!=m['target_sha256']:raise ValueError('Verification does not cover this exact artifact')
        checks[filename]=c
    if m.get('protected_nontext_regions'):
        c=json.loads((a.build/'nontext-verification.json').read_text(encoding='utf-8'))
        if c['status']!='PROTECTED_NON_TEXT_IDENTICAL' or c['rom_sha256']!=m['target_sha256']:raise ValueError('Non-text preservation does not cover artifact')
        checks['nontext-verification.json']=c
    runtime=json.loads((a.runtime/'runtime.json').read_text(encoding='utf-8'))
    visual=json.loads((a.runtime/'visual-observation.json').read_text(encoding='utf-8'))
    if runtime['status']!='REPLAY_AND_SAVE_CHECKS_PASS_VISUAL_INSPECTION_PENDING' or runtime['rom_sha256']!=m['target_sha256'] or runtime['ram_interventions']!=0 or not runtime['separate_process_reload']:raise ValueError('Normal input evidence does not match artifact')
    if visual['status']!='EXPECTED_SCREENS_OBSERVED' or visual['rom_sha256']!=m['target_sha256'] or visual['core_sha256']!=runtime['core_sha256']:raise ValueError('Image observation does not match runtime')
    captures={c['sha256'] for phase in runtime['phases'].values() for c in phase['captures']}
    if captures!={c['sha256'] for c in visual['captures']}:raise ValueError('Unreviewed or different runtime capture')
    for phase in runtime['phases'].values():
        if phase['rom_sha256']!=m['target_sha256'] or phase['core_sha256']!=runtime['core_sha256']:raise ValueError('Runtime phase binding differs')
        for c in phase['captures']:
            if sha(Path(c['path']).read_bytes())!=c['sha256']:raise ValueError('Runtime image changed after observation')
    saved=runtime['phases']['first-save']['save']
    if saved['size']!=8192 or saved['fixture_modified'] or runtime['phases']['reload']['input_save_sha256']!=saved['sha256'] or sha(Path(saved['path']).read_bytes())!=saved['sha256']:raise ValueError('Save/reload linkage differs')
    # Keep evidence identities in the package without disclosing local paths.
    checks['runtime-verification.json']={'status':'SCOPED_NORMAL_INPUT_AND_VISUAL_OBSERVATION_COMPLETE','rom_sha256':m['target_sha256'],'core_sha256':runtime['core_sha256'],'separate_process_reload':True,'save_sha256':saved['sha256'],'ram_interventions':0,'scope':runtime['scope'],'visual_observation':visual}
    a.out.mkdir(parents=True,exist_ok=False)
    patch=create_bps(source,target,b'ND3 B3TJ cumulative Korean development review; incomplete; not a release.')
    if apply_bps(source,patch)!=target:raise ValueError('BPS roundtrip mismatch')
    identity=project()
    if m.get('version')!=identity['version']:raise ValueError('Build version does not match selected project')
    patch_name=identity['patch_file'];(a.out/patch_name).write_bytes(patch)
    manifest={'status':'LOCAL_DEVELOPMENT_REVIEW_NOT_100_PERCENT_NOT_RELEASE','source_size':len(source),'source_sha256':J,'target_size':len(target),'target_sha256':sha(target),'patch_file':patch_name,'patch_sha256':sha(patch),'bps_roundtrip':True,'rom_included':False,'counts':{k:m[k] for k in ('font_glyphs','speaker_entries','skill_entries','actor_entries','large_skill_repairs','large_actor_changes','lexicon_entries','ui_entries')},'limits':m['limits']}
    manifest.update(version=identity['version'],small_table_entries=m.get('small_table_entries',0),dialogue_corrections=m.get('dialogue_corrections',0),recipe_string_fields=m.get('recipe_string_fields',0),battle_caption_sprites=m.get('battle_caption_sprites',0))
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,data in checks.items():(a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    for src,dest in [('tools/apply_development.py','apply_development.py'),('tools/bps.py','bps.py'),('fonts/LICENSE.dalmoori','LICENSE.dalmoori'),('docs/LICENSE.nd2-tools','LICENSE.nd2-tools'),('CREDITS.md','CREDITS.md'),('docs/REVIEW_README.md','먼저_읽어주세요.md')]:shutil.copyfile(ROOT/src,a.out/dest)
    archive=a.out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(a.out.iterdir()):z.write(path,path.name)
    report={'patch':str(a.out/patch_name),'patch_bytes':len(patch),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':sha(archive.read_bytes()),'target_sha256':sha(target),'status':manifest['status']}
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
