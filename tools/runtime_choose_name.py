"""Select a requested Korean/upper-case fixture name using normal buttons."""
import argparse,json,urllib.request
from text_codec import encode,hangul_map

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);p.add_argument('--expected',required=True);p.add_argument('--name',required=True);p.add_argument('--capture',required=True);p.add_argument('--confirm',action='store_true');a=p.parse_args()
    chars=list(hangul_map().values())
    if not 1<=len(a.name)<=5 or any(c not in chars and not 'A'<=c<='O' for c in a.name):raise ValueError('Unsupported fixture name')
    def api(req):
        r=urllib.request.Request(f'http://127.0.0.1:{a.port}',json.dumps(req).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(r,timeout=60) as response:return json.load(response)
    def read():return bytes.fromhex(api({'op':'read','address':'0x02012700','length':28})['hex'])
    def key(k):api({'op':'frames','count':1,'buttons':[k]});api({'op':'frames','count':40})
    def slots(text):return b''.join(encode(c)+bytes(4-len(encode(c))) for c in text)+bytes(4*(5-len(text)))
    state=read()
    if state[:20]!=slots(a.expected) or state[21]!=len(a.expected):raise ValueError('Expected name editor context differs')
    for _ in a.expected:key('b')
    for i,c in enumerate(a.name):
        state=read();page,x,y=state[20],state[22],state[23]
        if c in chars:target,cell=divmod(chars.index(c),90);ty,tx=divmod(cell,15)
        else:target,ty,tx=27,0,ord(c)-65
        forward,back=(target-page)%30,(page-target)%30
        for _ in range(min(forward,back)):key('r' if forward<=back else 'l')
        if x==15:key('left');x-=1
        for _ in range(y):key('up')
        for _ in range(x):key('left')
        for _ in range(ty):key('down')
        for _ in range(tx):key('right')
        state=read()
        if state[20]!=target or state[22:24]!=bytes([tx,ty]):raise ValueError('Observed candidate cursor differs')
        key('a');state=read()
        if state[:20]!=slots(a.name[:i+1]) or state[21]!=i+1:raise ValueError('Observed selected name differs')
    result=api({'op':'screenshot','name':a.capture+'.png'})
    if a.confirm:
        if read()[22:24]!=bytes([15,5]):key('start')
        api({'op':'frames','count':1,'buttons':['a']});api({'op':'frames','count':120})
    print(json.dumps({'name':a.name,'capture':result,'ram_interventions':0},ensure_ascii=False))

if __name__=='__main__':main()
