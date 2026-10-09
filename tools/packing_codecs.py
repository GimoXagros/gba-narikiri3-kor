"""Adopted lossless BIOS codecs lifted from the reviewed packing implementation."""
from collections import defaultdict
import struct
from gba_rle import unpack
from verify_graphics_candidate_edges import decode_stream
def rle(blob):
    n=len(blob);cost=[0]*(n+1);act=[None]*(n+1)
    for i in range(n-1,-1,-1):
        best=(10**9,None)
        for size in range(1,min(128,n-i)+1):
            v=1+size+cost[i+size]
            if v<best[0]:best=(v,('lit',size))
        run=1
        while run<min(130,n-i) and blob[i+run]==blob[i]:run+=1
        for size in range(3,run+1):
            v=2+cost[i+size]
            if v<best[0]:best=(v,('run',size))
        cost[i],act[i]=best
    out=bytearray(struct.pack('<I',(n<<8)|0x30));i=0
    while i<n:
        kind,size=act[i]
        if kind=='lit':out.append(size-1);out.extend(blob[i:i+size])
        else:out.extend((128|size-3,blob[i]))
        i+=size
    assert unpack(out,0,len(out),n)==(blob,len(out))
    return bytes(out)

def optimal_lz77(data):
    """Exhaustive token/flag-phase DP for short graphics; VRAM distance>=2."""
    data=bytes(data);n=len(data);match=[];chains=defaultdict(list)
    for i in range(n):
        best=0;distance=0;key=data[i:i+3]
        for pos in reversed(chains[key]):
            d=i-pos
            if d>4096:break
            if d<2:continue
            size=0
            while size<18 and i+size<n and data[i+size]==data[i+size-d]:size+=1
            if size>best:best,distance=size,d
            if size==18:break
        match.append((best,distance));chains[key].append(i)
    dp=[[0]*8 for _ in range(n+1)];act=[[None]*8 for _ in range(n)]
    for i in range(n-1,-1,-1):
        for phase in range(8):
            nextphase=(phase+1)%8;cost=(1 if phase==0 else 0)
            best=cost+1+dp[i+1][nextphase];choice=(1,0)
            for size in range(3,match[i][0]+1):
                value=cost+2+dp[i+size][nextphase]
                if value<best:best=value;choice=(size,match[i][1])
            dp[i][phase]=best;act[i][phase]=choice
    out=bytearray(struct.pack('<I',(n<<8)|0x10));i=0;phase=0
    while i<n:
        if phase==0:flag_at=len(out);out.append(0)
        size,distance=act[i][phase]
        if distance:
            out[flag_at]|=1<<(7-phase);out.extend((((size-3)<<4)|((distance-1)>>8),(distance-1)&255))
        else:out.append(data[i])
        i+=size;phase=(phase+1)%8
    raw,used,_=decode_stream(out);assert raw==data and used==len(out) and len(out)==4+dp[0][0]
    return bytes(out)
