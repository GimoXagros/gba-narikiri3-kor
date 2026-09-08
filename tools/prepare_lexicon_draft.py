"""Select reviewable ND3 item/enemy name drafts from exact ND2 and user terms."""
import argparse,json,unicodedata
from pathlib import Path
from compare_nd2_names import key

ITEMS={19:'엘븐 부츠',41:'양배추',45:'감자',46:'우유',48:'해산물',49:'과일',
50:'오의 개전서',51:'엘븐 보우',53:'계약의 반지',54:'엘븐 로어',55:'닌도 혈앵',
58:'진홍 망토',59:'은테 안경',60:'베르세르크 애로우',61:'셀프 보우',62:'금 프라이팬',
65:'사냥꾼의 도끼',67:'레오노아 사전',68:'오제 피어스',72:'스톰브링거',73:'묠니르',
74:'희망의 펜던트',75:'칠흑의 페르소나',76:'에덴즈 파이어',77:'해롤드의 지팡이',
78:'요소의 문장',79:'월드 오브 원',80:'신자의 장속',81:'유니콘의 뿔',82:'코린의 방울',
83:'신자의 예복',84:'가이아 그리버',85:'강철 수갑',86:'프랑베르주',87:'데리스 엠블렘',
89:'셀시우스의 눈물',91:'검술서',93:'헌터 보우',95:'검은 옷',96:'검은 로브',97:'금 주판',
100:'여우 가면',103:'백과사전',104:'노코 버섯',106:'가죽 코트',107:'궁니르',109:'도적 대거',
110:'어둠의 구슬',111:'피로 물든 도끼',112:'기적의 펜던트',113:'크루시스의 휘석',114:'용의 비늘',
115:'호랑이 가죽',116:'페이크 퍼',117:'북채',119:'BC로드',120:'에테르',121:'RC로드',122:'고대의 열쇠'}
MONSTERS={133:'레드 로퍼',134:'AC로퍼',135:'블루 로퍼',136:'그린 로퍼',137:'컬프릿',138:'크리미널',
139:'우즈 웜',140:'트로픽스 웜',141:'마운트 웜',142:'빅풋',143:'마이코니드',144:'미니코이드',
145:'사로리사',146:'스피리움',147:'소서러',148:'세이지',149:'드루이드',150:'밴디트',151:'로그',
152:'루터',153:'머더',181:'나리키리 남',182:'나리키리 여',183:'나리키리 남',184:'나리키리 여',198:'HRX-2'}

def kana_key(text):
    text=key(text)
    return ''.join(chr(ord(c)+0x60) if '\u3041'<=c<='\u3096' else c for c in text)

def main():
    p=argparse.ArgumentParser();p.add_argument('--cross-reference',type=Path,required=True);p.add_argument('--terms',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Draft exists; edit explicitly')
    refs=json.loads(a.cross_reference.read_text(encoding='utf-8'));terms=json.loads(a.terms.read_text(encoding='utf-8'))
    names={kana_key(k):v for k,v in terms['characters'].items()}
    names.update({kana_key(r['j']):r['ko'] for r in terms['costumes'] if r['ko'] is not None})
    result={}
    for group,overrides in [('item',ITEMS),('monster',MONSTERS)]:
        rows=[]
        for i,r in enumerate(refs[group]):
            chosen=r['suggested'];basis='Exact Japanese-name match to authorized ND2 v0.9b';reference=r['nd2_reference']
            if group=='monster' and kana_key(r['japanese']) in names:
                chosen=names[kana_key(r['japanese'])];basis='User-selected character/costume spelling';reference='terminology.json'
            if i in overrides:chosen=overrides[i];basis='Explicit ND3 wording: user recipe reference / source phonetic name';reference='User list + immutable B3TJ; review pending'
            if chosen is None:raise ValueError(f'Missing name decision {r["id"]}')
            rows.append({'id':r['id'],'compact':chosen,'source_record_sha256':r['source_record_sha256'],'basis':basis,'reference':reference,'review':'pending','layout':'all_callers_pending'})
        result[group]=rows
    a.out.write_text(json.dumps({'schema':1,'policy':'development_only_needs_review','groups':result},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({g:{'records':len(r),'max_cells':max(len(x['compact']) for x in r)} for g,r in result.items()}))
if __name__=='__main__':main()
