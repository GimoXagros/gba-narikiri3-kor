"""Reproduce the cumulative draft from immutable inputs and verify emitted code."""
import argparse,hashlib,json,platform,subprocess,sys
from pathlib import Path
from importlib.metadata import version
from project_profile import project

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--j',type=Path,required=True)
    p.add_argument('--ips',type=Path,required=True)
    p.add_argument('--toolchain',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    def run(script,args):
        subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools'/script),*map(str,args)],cwd=ROOT,check=True)
    out=a.out.resolve();j=a.j.resolve();ips=a.ips.resolve();tc=a.toolchain.resolve()
    run('build_small_font_experiment.py',['--j',j,'--ips',ips,'--toolchain',tc,'--out',out,
        '--glyphs',ROOT/'fonts/dalmoori-wansung.json','--speakers',ROOT/'translations/speakers.json',
        '--skills',ROOT/'translations/skills.json','--actors',ROOT/'translations/actors.json',
        '--default-names',ROOT/'translations/default_names.json','--simple-hook',
        '--lexicon',ROOT/'translations/items-monsters.json','--ui',ROOT/'translations/ui.json',
        '--small-tables',ROOT/'translations/small_tables.json','--dialogue-fixes',ROOT/'translations/dialogue_fixes.json',
        '--recipes',ROOT/'translations/recipes.json','--battle-captions',ROOT/'translations/battle_captions.json','--name-keyboard','--skill-headers','--biographies','--clothing-results','--save-places','--notices','--inspect-eye','--element-symbols','--item-descriptions','--splash-credit','--costume-label'])
    # Reconstruct the immutable legacy input solely for the comparison fixture.
    from survey_rom import ips_records
    legacy=bytearray(j.read_bytes());records,trunc=ips_records(ips.read_bytes())
    if trunc:raise ValueError('Unexpected IPS truncation')
    for offset,data in records:legacy[offset:offset+len(data)]=data
    legacy_path=out/'legacy-fixture.gba';legacy_path.write_bytes(legacy)
    rom=out/project()['rom_file']
    checks=[('verify_small_consumer.py','consumer-verification.json',['--legacy',legacy_path,'--glyphs',ROOT/'fonts/dalmoori-wansung.json']),
            ('verify_simple_consumer.py','simple-consumer-verification.json',['--legacy',legacy_path,'--glyphs',ROOT/'fonts/dalmoori-wansung.json']),
            ('verify_cache_replacement.py','cache-replacement-verification.json',[]),
            ('verify_name_import.py','name-import-verification.json',[]),
            ('verify_integrated_names.py','integrated-name-verification.json',[]),
            ('verify_ui_format.py','ui-verification.json',[]),
            ('verify_trap_menu.py','trap-menu-verification.json',['--legacy',legacy_path]),
            ('verify_small_tables.py','small-tables-verification.json',[]),
            ('verify_nontext.py','nontext-verification.json',[]),
            ('verify_graphics_candidate_edges.py','graphics-candidate-edge-verification.json',[]),
            ('verify_name_expansion.py','name-expansion-verification.json',[]),
            ('verify_dialogue_resource.py','dialogue-resource-verification.json',['--j',j,'--legacy',legacy_path]),
            ('verify_dialogue_pixels.py','dialogue-pixel-verification.json',['--legacy',legacy_path,'--all-records','--j',j]),
            ('verify_dialogue_audit.py','dialogue-audit-verification.json',['--legacy',legacy_path,'--j',j]),
            ('verify_recipes.py','recipe-verification.json',['--legacy',legacy_path]),
            ('verify_battle_captions.py','battle-caption-verification.json',['--legacy',legacy_path]),
            ('verify_name_keyboard.py','name-keyboard-verification.json',['--legacy',legacy_path]),
            ('verify_skill_headers.py','skill-header-verification.json',['--legacy',legacy_path]),
            ('verify_biographies.py','biography-verification.json',['--legacy',legacy_path,'--j',j]),
            ('verify_splash_credit.py','splash-credit-verification.json',['--legacy',legacy_path]),
            ('verify_costume_label.py','costume-label-verification.json',['--legacy',legacy_path]),
            ('verify_internal_battle_menu.py','internal-battle-menu-verification.json',[]),
            ('verify_skill_text.py','skill-text-verification.json',['--legacy',legacy_path]),
            ('verify_clothing_results.py','clothing-result-verification.json',['--legacy',legacy_path]),
            ('verify_save_places.py','save-place-verification.json',['--legacy',legacy_path]),
            ('verify_notices.py','notice-verification.json',['--legacy',legacy_path]),
            ('verify_inspect_eye.py','inspect-eye-verification.json',['--legacy',legacy_path]),
            ('verify_element_symbols.py','element-symbol-verification.json',['--legacy',legacy_path]),
            ('verify_item_descriptions.py','item-description-pixel-verification.json',['--legacy',legacy_path]),
            ('verify_auxiliary_exclusions.py','auxiliary-exclusion-verification.json',[])]
    for script,filename,extra in checks:run(script,['--rom',rom,'--out',out/filename,*extra])
    files=[*sorted((ROOT/'tools').glob('*.py')),*sorted((ROOT/'source').glob('*')),
           *sorted((ROOT/'translations').glob('*.json')),ROOT/'fonts/dalmoori-wansung.json',ROOT/'requirements-dev.txt',ROOT/'project.json',ROOT/'qa/dialogue-review-v1.1a.json']
    provenance={'status':'ISOLATED_CPU_CHECKS_PASS_RUNTIME_AND_REVIEW_SEPARATE',
                'python':platform.python_version(),'packages':{n:version(n) for n in ['pillow','numpy','capstone','fonttools','unicorn']},
                'toolchain':{name:hashlib.sha256((tc/f'arm-none-eabi-{name}.exe').read_bytes()).hexdigest() for name in ['as','ld','objcopy','objdump','nm']},
                'repository_inputs':{str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
                'target_sha256':hashlib.sha256(rom.read_bytes()).hexdigest()}
    (out/'reproduction.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'out':str(out),'target_sha256':provenance['target_sha256'],'status':provenance['status']}))

if __name__=='__main__':main()
