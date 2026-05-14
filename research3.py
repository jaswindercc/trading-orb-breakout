#!/usr/bin/env python3
"""
Round 3: Focused practical research.

Key findings from R1/R2:
- Wider SL (2.0-2.5×ATR) = huge reduction in B2B SLs
- Trail EMA 10 with 1.0 buffer, starting at 1.5R = ride momentum
- Fast SMAs (5/20) = too many whipsaws
- Slow SMAs (50/200) = too few trades (overfit)
- Sweet spot: SMA 10/50 or 10/100 with better filters

This round: smaller sweep, smarter scoring, opposite-cross exit.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path("/workspaces/jas/data")

def load_stock(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def load_all():
    stocks = {}
    for f in sorted(DATA_DIR.glob("*.csv")):
        name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
        stocks[name] = load_stock(f)
    return stocks

def add_ind(df, fast, slow, tl=20):
    df = df.copy()
    df['fSma'] = df['Close'].rolling(fast).mean()
    df['sSma'] = df['Close'].rolling(slow).mean()
    df['tr'] = np.maximum(df['High']-df['Low'],
        np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['atr'] = df['tr'].rolling(14).mean()
    df['tEma'] = df['Close'].ewm(span=tl, adjust=False).mean()
    df['bRng'] = df['High'] - df['Low']
    df['fAbv'] = (df['fSma'] > df['sSma']).astype(int)
    df['xUp'] = (df['fAbv']==1) & (df['fAbv'].shift(1)==0)
    df['xDn'] = (df['fAbv']==0) & (df['fAbv'].shift(1)==1)
    return df

@dataclass
class T:
    stk:str=""; ed:str=""; d:int=0; ep:float=0; sl:float=0; r:float=0
    xd:str=""; xp:float=0; xr:str=""; pr:float=0

@dataclass
class C:
    fast:int=10; slow:int=50
    mdist:float=1.5; mbar:float=2.0
    sla:float=1.5
    tl:int=20; tb:float=0.5; tsr:float=1.0
    utp:bool=False; tpr:float=3.0
    xclose:bool=True  # close on opposite cross (key new feature)

def bt(df, c, nm=""):
    df = add_ind(df, c.fast, c.slow, c.tl)
    ts=[]; pos=0; ep=er=tsl=0.0; edir=0; lcd=0; bsc=999
    
    for i in range(1, len(df)):
        r = df.iloc[i]; atr = r['atr']
        if pd.isna(atr) or atr<=0: continue
        
        if r['xUp']: lcd=1; bsc=0
        elif r['xDn']: lcd=-1; bsc=0
        else: bsc+=1
        
        if pos!=0:
            hsl=htp=False; xp=0.0
            
            if pos==1:
                if r['Low']<=tsl: xp=tsl; hsl=True
                elif c.utp:
                    tp=ep+er*c.tpr
                    if r['High']>=tp: xp=tp; htp=True
                if not hsl and not htp:
                    cr=(r['Close']-ep)/er if er>0 else 0
                    if cr>=c.tsr:
                        et=r['tEma']-c.tb*atr
                        if et>tsl: tsl=et
                if not hsl and not htp and c.xclose and lcd==-1 and bsc==0:
                    xp=r['Close']; hsl=True
            else:
                if r['High']>=tsl: xp=tsl; hsl=True
                elif c.utp:
                    tp=ep-er*c.tpr
                    if r['Low']<=tp: xp=tp; htp=True
                if not hsl and not htp:
                    cr=(ep-r['Close'])/er if er>0 else 0
                    if cr>=c.tsr:
                        et=r['tEma']+c.tb*atr
                        if et<tsl: tsl=et
                if not hsl and not htp and c.xclose and lcd==1 and bsc==0:
                    xp=r['Close']; hsl=True
            
            if hsl or htp:
                t=ts[-1]; t.xd=str(r['Date'].date()); t.xp=xp
                t.xr="TP" if htp else "XCross" if (c.xclose and bsc==0 and ((pos==1 and lcd==-1) or (pos==-1 and lcd==1))) else "SL"
                t.pr=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                pos=0
        
        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=c.mdist*atr
            bok=r['bRng']<=c.mbar*atr
            
            if dok and bok and xl:
                sl=r['Close']-c.sla*atr; rk=r['Close']-sl
                pos=1; ep=r['Close']; er=rk; tsl=sl
                ts.append(T(stk=nm,ed=str(r['Date'].date()),d=1,ep=r['Close'],sl=sl,r=rk))
            elif dok and bok and xs:
                sl=r['Close']+c.sla*atr; rk=sl-r['Close']
                pos=-1; ep=r['Close']; er=rk; tsl=sl
                ts.append(T(stk=nm,ed=str(r['Date'].date()),d=-1,ep=r['Close'],sl=sl,r=rk))
    
    if pos!=0 and ts:
        t=ts[-1]; l=df.iloc[-1]; t.xd=str(l['Date'].date()); t.xp=l['Close']
        t.xr="EOD"; t.pr=((l['Close']-ep)/er if pos==1 else (ep-l['Close'])/er) if er>0 else 0
    return ts

def met(ts):
    if not ts: return {'n':0,'wr':0,'tr':0,'dd':0,'cl':0,'b2b':0,'pf':0,'cal':0,'aw':0,'al':0}
    ps=[t.pr for t in ts]; ws=[p for p in ps if p>0]; ls=[p for p in ps if p<=0]
    cu=np.cumsum(ps); dd=(np.maximum.accumulate(cu)-cu).max() if len(cu)>0 else 0
    mc=cc=b=0
    for p in ps:
        if p<=0: cc+=1; b+=(1 if cc>=2 else 0); mc=max(mc,cc)
        else: cc=0
    tw=sum(ws) if ws else 0; tl2=abs(sum(ls)) if ls else 0.001; tr2=sum(ps)
    return {'n':len(ts),'wr':len(ws)/len(ts)*100,'tr':round(tr2,2),'dd':round(dd,2),
            'cl':mc,'b2b':b,'pf':round(tw/tl2,2),'cal':round(tr2/dd if dd>0 else tr2,2),
            'aw':round(np.mean(ws),2) if ws else 0,'al':round(np.mean(ls),2) if ls else 0}

def run(stocks, c, lab=""):
    at=[]; ps={}
    for nm,df in stocks.items():
        ts=bt(df,c,nm); ps[nm]=met(ts); at.extend(ts)
    m=met(at); m['lab']=lab
    m['ok']=all(ps[n]['n']>=2 for n in ps)  # at least 2 trades per stock
    return m, ps, at

def fmt(m):
    f="✓" if m.get('ok') else "✗"
    return (f"{m.get('lab',''):50s} {m['n']:3d}t WR{m['wr']:3.0f}% {m['tr']:+6.1f}R "
            f"DD{m['dd']:5.1f} CL{m['cl']} B2B{m['b2b']:3d} PF{m['pf']:5.2f} "
            f"Cal{m['cal']:6.2f} AvgW{m['aw']:+5.1f} AvgL{m['al']:+5.1f} {f}")

stocks = load_all()
print(f"Loaded {len(stocks)} stocks\n")

# Score: heavily penalize B2B, reward calmar
def sc(m):
    if m['n']<15: return -999  # need reasonable sample
    return m['cal'] - 0.2*m['b2b'] + 0.03*m['wr'] - 0.5*m['cl']

# ============================================================
# FOCUSED SWEEP
# ============================================================
print("=" * 130)
print("FOCUSED SWEEP")
print("=" * 130)

configs = []
for fast, slow in [(5,20),(5,50),(10,30),(10,50),(10,100),(20,50),(20,100)]:
    for sla in [1.5, 2.0, 2.5]:
        for tl,tb,tsr in [(10,0.5,1.0),(10,1.0,1.5),(20,0.5,1.0),(20,1.0,1.5)]:
            for mbar in [2.0, 3.0]:
                for mdist in [1.5, 3.0]:
                    for utp,tpr in [(False,0),(True,3.0),(True,5.0)]:
                        for xclose in [True, False]:
                            configs.append(C(fast=fast,slow=slow,sla=sla,tl=tl,tb=tb,tsr=tsr,
                                            mbar=mbar,mdist=mdist,utp=utp,tpr=tpr,xclose=xclose))

print(f"Testing {len(configs)} combinations...\n")

best_s = -999; best_c = None; best_m = None; best_p = None
top_10 = []

for i, c in enumerate(configs):
    lab = f"SMA{c.fast}/{c.slow} SL{c.sla} T{c.tl}/{c.tb}/{c.tsr} B{c.mbar} D{c.mdist} TP{'t' if not c.utp else c.tpr} X{c.xclose}"
    m, ps, _ = run(stocks, c, lab)
    s = sc(m)
    
    # Track top 10
    top_10.append((s, m, ps, c))
    top_10.sort(key=lambda x: x[0], reverse=True)
    top_10 = top_10[:10]
    
    if s > best_s:
        best_s = s; best_c = c; best_m = m; best_p = ps
        print(f"[{i+1}/{len(configs)}] NEW BEST (score={s:.2f}):")
        print(f"  {fmt(m)}")

print(f"\nDone. Tested {len(configs)} combinations.\n")

# ============================================================
# TOP 10 RESULTS
# ============================================================
print("=" * 130)
print("TOP 10 CONFIGURATIONS")
print("=" * 130)
for rank, (s, m, ps, c) in enumerate(top_10):
    print(f"#{rank+1} (score={s:.2f}): {fmt(m)}")

# ============================================================
# FINAL BEST DETAILED
# ============================================================
print("\n" + "=" * 130)
print("BEST CONFIGURATION - DETAILED")
print("=" * 130)

print(f"\nSettings:")
print(f"  SMA: {best_c.fast}/{best_c.slow}")
print(f"  SL: {best_c.sla}×ATR")
print(f"  Trail EMA: {best_c.tl}, buffer: {best_c.tb}×ATR, starts: {best_c.tsr}R")
print(f"  Big candle filter: {best_c.mbar}×ATR")
print(f"  Distance filter: {best_c.mdist}×ATR")
print(f"  TP: {'Fixed ' + str(best_c.tpr) + 'R' if best_c.utp else 'Pure Trail'}")
print(f"  Close on opposite cross: {best_c.xclose}")

print(f"\nCombined: {fmt(best_m)}")
print(f"\nPer-stock:")
for nm in sorted(best_p.keys()):
    p = best_p[nm]
    print(f"  {nm:6s}: {p['n']:2d}t WR{p['wr']:3.0f}% {p['tr']:+6.1f}R DD{p['dd']:4.1f} B2B{p['b2b']:2d} AvgW{p['aw']:+5.1f} AvgL{p['al']:+5.1f}")

# Trade log
print(f"\n--- Trade log ---")
_, _, at = run(stocks, best_c, "FINAL")
at.sort(key=lambda t: t.ed)
for t in at:
    ds="L" if t.d==1 else "S"
    print(f"  {t.stk:6s} {t.ed} {ds} @{t.ep:8.2f} → {t.xd} @{t.xp:8.2f} [{t.xr:6s}] {t.pr:+6.2f}R")

# ============================================================
# BASELINE COMPARISON
# ============================================================
print(f"\n" + "=" * 130)
print("BASELINE (current pine_orb) vs BEST")
print("=" * 130)

base = C()  # current defaults
m0, p0, _ = run(stocks, base, "BASELINE (SMA 10/50, SL 1.5, Trail 20)")
print(f"BEFORE: {fmt(m0)}")
print(f"AFTER:  {fmt(best_m)}")

print(f"\nPer-stock comparison:")
for nm in sorted(p0.keys()):
    b=p0[nm]; o=best_p[nm]
    print(f"  {nm:6s}: {b['tr']:+5.1f}R→{o['tr']:+5.1f}R | DD {b['dd']:4.1f}→{o['dd']:4.1f} | B2B {b['b2b']:2d}→{o['b2b']:2d} | WR {b['wr']:.0f}%→{o['wr']:.0f}%")
