"""Normal controller-only keyboard exercise; RAM reads are observations only."""
import argparse,json,urllib.request
from pathlib import Path
from text_codec import encode,hangul_map

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Do not overwrite runtime evidence')
    observations=[]
    def api(request):
        data=json.dumps(request).encode();req=urllib.request.Request(f'http://127.0.0.1:{a.port}',data,{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=60) as response:result=json.load(response)
        if not result['ok']:raise ValueError(result)
        return result
    def key(button):
        api({'op':'frames','count':1,'buttons':[button]});api({'op':'frames','count':40})
    def context():
        result=api({'op':'read','address':'0x02012700','length':28});observations.append(result)
        return bytes.fromhex(result['hex'])
    def capture(name):api({'op':'screenshot','name':name+'.png'})
    current=context()
    if current[:20]!=b''.join(encode(c)+b'\0\0' for c in '훌리오')+bytes(8) or current[20:24]!=bytes([0,3,0,0]):raise ValueError('Expected fresh first keyboard state')
    expected_names=current[:20]
    for button,delta in [('r',1),('l',-1)]:
        for step in range(30):
            page=((step+1)*delta)%30;key(button);current=context()
            if current[:20]!=expected_names or current[20:24]!=bytes([page,3,0,0]):raise ValueError('Runtime page/retained name differs')
            if button=='r' and page in (26,27,28,29,0):capture(f'keyboard-cycle-page-{page:02d}')
    # Delete a whole Hangul syllable with each B press.
    for count in (2,1,0):
        key('b');current=context()
        want=b''.join(encode(c)+b'\0\0' for c in '훌리오'[:count])+bytes((5-count)*4)
        if current[:20]!=want or current[21]!=count:raise ValueError('Runtime whole-slot delete differs')
    chars=list(hangul_map().values())
    def choose(c):
        current=context();page=current[20];x=current[22];y=current[23]
        if c in chars:
            index=chars.index(c);target,cell=divmod(index,90);ty,tx=divmod(cell,15)
        else:target,ty,tx=27,0,ord(c)-ord('A')
        forward=(target-page)%30;back=(page-target)%30
        for _ in range(min(forward,back)):key('r' if forward<=back else 'l')
        # Place y=0 first to avoid the three-action side column's row wrap.
        for _ in range(y):key('up')
        for _ in range(x):key('left')
        for _ in range(ty):key('down')
        for _ in range(tx):key('right')
        current=context()
        if current[20]!=target or current[22:24]!=bytes([tx,ty]):raise ValueError('Candidate cursor differs')
        key('a')
    text='가A나B힝'
    for i,c in enumerate(text):
        choose(c);current=context()
        want=b''.join(encode(ch)+bytes(4-len(encode(ch))) for ch in text[:i+1])+bytes((4-i)*4)
        if current[:20]!=want or current[21]!=i+1:raise ValueError('Runtime selected character differs')
    capture('keyboard-five-mixed-name')
    # Original full-name path moves the cursor to Confirm. Move back into a
    # candidate cell and try A; the five-character buffer must stay unchanged.
    saved=current[:20];key('left');key('a');current=context()
    if current[:20]!=saved or current[21]!=5:raise ValueError('Sixth input changed name')
    capture('keyboard-full-name-retained')
    # Delete last syllable and select it again, then use the final empty cell.
    key('b');choose('힝');key('b')
    current=context()
    # Full-name auto cursor was side x15/y5; move to blank x14/y5 on page 26.
    if current[22:24]!=bytes([15,5]):raise ValueError('Expected original automatic confirm cursor')
    key('left');before=context();key('a');after=context()
    if before!=after:raise ValueError('Blank candidate changed name or cursor')
    choose('힝');capture('keyboard-final-mixed-name')
    report={'status':'SCOPED_NORMAL_CONTROLLER_KEYBOARD_PASS','custom_name':text,'ram_interventions':0,'observations':observations,'limits':['Not yet committed to save in this stage','Screenshots require visual observation','One deterministic opening context address; do not reuse for unrelated scenes']}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':report['status'],'observations':len(observations)},ensure_ascii=False))

if __name__=='__main__':main()
