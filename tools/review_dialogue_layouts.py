"""Exact user-adopted phrases requiring more lines than either source edition."""
LAYOUTS = {
    'xlsx-2424': '말하면　통하고!　통하면\n말하지!　저승길　선물로\n수다나　실컷　떨자고!',
    'xlsx-1949': '마치　영웅들은　날아드는\n불방망이　속의　여름\n장수풍뎅이　같군!',
    'xlsx-1974': '이게　바로　"지성이면　감점"\n이라는　거지',
    'xlsx-2064': '이　세계에서는　선빵필승!\n일찍　일어나는　새가\n３갈드를　벌고%k\n공격은　최고의　방어!\n로마에　가면　로마　법을…\nＧｏ！　Ｇｏ！　Ｇｏ！',
    'xlsx-4458': '엑스피어는　어떻게　못　해도\n요의　문이라면……\n뚝딱　해치우지',
}

def approved(identity, text):
    import json
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'source/proper_name_layouts.json'
    extra=json.loads(path.read_text('utf-8')) if path.exists() else {}
    return LAYOUTS.get(identity) == text or extra.get(identity)==text
