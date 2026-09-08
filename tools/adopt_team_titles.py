"""Adopt the enumerated team-rule title and bonus tables; no heuristic writes."""
import hashlib,json,struct
from pathlib import Path
from text_codec import decode
ROOT=Path(__file__).resolve().parents[1]
TITLES=['칭호 없음','그레이트 헌터','둘은 라이벌','테일즈 히어로','테일즈 히로인','작은 거인','치유의 달인','사이언티스트','호쾌한 사람','숨겨진 과거','멋진 남자들','앗, 미안해!','쿨한 녀석들','그래플러','러브러브?','돈 좀 버나?','고집쟁이','요리 고수','형제의 의리','동물이 좋아','질풍처럼','바람둥이','부모 자식의 유대','비밀의 정체','삼각관계','검술 지도','학술 지도','베스트 파트너','짝사랑','검과 주먹과','돈의 망자','궁술의 기초','마술 지도','천재와 우민','렌즈 헌터']
BONUSES=['보너스 없음','TP 회복 UP','HP 회복 UP','갈드 획득 UP','레어 게터','아이템 게터','푸드 게터','지력 UP','TP 소모 감소','훔치기 UP','스피드 UP','어필','방어력 UP','캐스트 UP','기절 UP','도주 속도 UP','맷집 UP','타격력 UP','내열 방한']

def main():
    j=next(ROOT.glob('*[[]J[]]*.gba')).read_bytes();k=next(ROOT.glob('*[[]K[]]*.gba')).read_bytes()
    if hashlib.sha256(j).hexdigest()!='d083d66b818b1353a449af7f1dd4232b490c254a4107951a3749973d03a0a394':raise ValueError('Wrong source')
    rules=struct.unpack_from('<I',j,0x82dc)[0]-0x08000000
    rows=[struct.unpack_from('<8B4H',j,rules+i*16) for i in range(58)]
    if set(row[9] for row in rows)!=(set(range(35))-{23}) or max(row[10] for row in rows)!=18:raise ValueError('Team-rule population differs')
    profiles=[];translations=[]
    for group,base,values,getter in [('team-title',0x743cfc,TITLES,0x8330),('team-bonus',0x743cb0,BONUSES,0x8340)]:
        refs=[]
        for i,text in enumerate(values):
            offset=base+4*i;ptr=struct.unpack_from('<I',j,offset)[0];start=ptr-0x08000000
            raw=j[start:j.index(0,start)]
            if k[start:start+len(raw)+1]!=raw+b'\0':raise ValueError('Expected unchanged legacy table text')
            refs.append({'id':f'{group}-{i:03d}','pointer_offset':hex(offset),'source_pointer':hex(ptr),'source_raw':raw.hex()})
            translations.append({'id':f'{group}-{i:03d}','text':text,'review':'pending','basis':'Exact Japanese team title/bonus record; preserve UP without inventing mechanics'})
        profiles.append({'id':group,'base':hex(base),'count':len(values),'stride':4,'consumer_getter':hex(0x08000000+getter),'getter_bytes':j[getter:getter+16].hex(),'max_cells':9,'records':refs})
    out={'schema':1,'source_sha256':hashlib.sha256(j).hexdigest(),'scope':'Complete title and bonus arrays selected by the 58-record team rule resolver 0800823C; zero is the explicit no-title/no-bonus fallback',
         'rule_base':hex(rules),'rule_count':58,'rule_stride':16,'rule_sha256':hashlib.sha256(j[rules:rules+58*16]).hexdigest(),'rule_loop_guard_offset':'0x82ea','rule_loop_guard_hex':j[0x82ea:0x82ee].hex(),'rule_title_ids':sorted({r[9] for r in rows}),'rule_bonus_ids':sorted({r[10] for r in rows}),'reachability_note':'Title 23 and bonus 9/11 are not selected by these 58 rules; still preserve and translate the identified string slots, without asserting whole-game reachability','groups':profiles}
    (ROOT/'source/small_tables.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'translations/small_tables.json').write_text(json.dumps({'schema':1,'policy':'development_only_needs_review','records':translations},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'title':len(TITLES),'bonus':len(BONUSES),'rule_records':58}))

if __name__=='__main__':main()
