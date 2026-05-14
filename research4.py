#!/usr/bin/env python3
"""Fast parameter sweep: find best entry/exit rules. Numpy arrays for speed."""
import pandas as pd, numpy as np
from pathlib import Path
import time as tmod

DATA_DIR = Path("/workspaces/jas/data")

def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def precompute(df):
    d = df.copy()
    d['fSma10'] = d['Close'].rolling(10).mean()
    d['sSma50'] = d['Close'].rolling(50).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr'] = d['tr'].rolling(14).mean()
    d['bRng'] = d['High'] - d['Low']
    fAbv = (d['fSma10'] > d['sSma50']).astype(int)
    d['xUp'] = (fAbv==1) & (fAbv.shift(1)==0)
    d['xDn'] = (fAbv==0) & (fAbv.shift(1)==1)
    for elen in [10, 20, 30]:
        d[f'tEma{elen}'] = d['Close'].ewm(span=elen, adjust=False).mean()
    return d

def bt(df, sla, tsr, tb, mdist, te, bm, blo, bhi):
    RISK = 100.0
    ec = f'tEma{te}'
    C=df['Close'].values; H=df['High'].values; L=df['Low'].values
    A=df['atr'].values; F=df['fSma10'].values; B=df['bRng'].values
    XU=df['xUp'].values; XD=df['xDn'].values; E=df[ec].values
    
    trades=[]; pos=0; ep=er=tsl=0.0; lcd=0; bsc=999
    for i in range(1, len(df)):
        a=A[i]
        if np.isnan(a) or a<=0: continue
        c=C[i]; h=H[i]; lo=L[i]
        if XU[i]: lcd=1; bsc=0
        elif XD[i]: lcd=-1; bsc=0
        else: bsc+=1
        if pos!=0:
            hsl=False; xp=0.0
            if pos==1:
                if lo<=tsl: xp=tsl; hsl=True
                if not hsl:
                    cr=(c-ep)/er if er>0 else 0
                    if cr>=tsr:
                        et=E[i]-tb*a
                        if et>tsl: tsl=et
            else:
                if h>=tsl: xp=tsl; hsl=True
                if not hsl:
                    cr=(ep-c)/er if er>0 else 0
                    if cr>=tsr:
                        et=E[i]+tb*a
                        if et<tsl: tsl=et
            if hsl:
                pr=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                trades.append(round(pr*RISK,2))
                pos=0
        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dk=abs(c-F[i])<=mdist*a
            br=B[i]
            if bm==0: bk=True
            elif bm==1: bk=br>=blo*a
            elif bm==2: bk=br<=bhi*a
            else: bk=br>=blo*a and br<=bhi*a
            if dk and bk and xl:
                sl=c-sla*a; rk=c-sl
                pos=1; ep=c; er=rk; tsl=sl
            elif dk and bk and xs:
                sl=c+sla*a; rk=sl-c
                pos=-1; ep=c; er=rk; tsl=sl
    if pos!=0:
        pr=((C[-1]-ep)/er if pos==1 else (ep-C[-1])/er) if er>0 else 0
        trades.append(round(pr*RISK,2))
    return trades

def score_trades(pnls):
    if len(pnls)<5: return None
    p=np.array(pnls); n=len(p)
    w=p[p>0]; l=p[p<=0]
    tp=p.sum(); tw=w.sum() if len(w) else 0; tl=l.sum() if len(l) else 0
    wr=len(w)/n*100; pf=abs(tw/tl) if tl!=0 else 99; ar=(p/100).mean()
    eq=np.cumsum(p); pk=np.maximum.accumulate(eq); dd=pk-eq; mdd=dd.max()
    cl=0; mcl=0
    for x in p<=0:
        if x: cl+=1
        else: cl=0
        mcl=max(mcl,cl)
    rf=tp/mdd if mdd>0 else 99
    return {'n':n,'w':len(w),'wr':round(wr,1),'pnl':round(tp,0),
            'profit':round(tw,0),'loss':round(tl,0),'pf':round(pf,2),
            'avgr':round(ar,2),'mdd':round(mdd,0),'mcl':mcl,'rf':round(rf,2)}

stocks = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    stocks[name] = precompute(load(f))
print(f"Loaded {len(stocks)} stocks\n")

# Sweep
bar_opts = [
    (0,0,0,"NoFilt"),
    (2,0,3.0,"Max≤3"),
    (2,0,2.0,"Max≤2"),
    (1,0.5,0,"Min≥.5"),
    (1,0.75,0,"Min≥.75"),
    (3,0.5,3.0,".5-3"),
    (3,0.5,2.0,".5-2"),
    (3,0.75,2.5,".75-2.5"),
]
sla_v=[1.5,2.0,2.5,3.0]
tsr_v=[1.0,1.5,2.0,2.5]
tb_v=[0.5,0.75,1.0,1.5]
md_v=[3.0,5.0]
te_v=[10,20]

total=len(bar_opts)*len(sla_v)*len(tsr_v)*len(tb_v)*len(md_v)*len(te_v)
print(f"Testing {total} combos...")
t0=tmod.time()

results=[]
for bm,blo,bhi,blbl in bar_opts:
    for sla in sla_v:
        for tsr in tsr_v:
            for tb in tb_v:
                for md in md_v:
                    for te in te_v:
                        ap=[]; sp={}
                        for nm,df in stocks.items():
                            p=bt(df,sla,tsr,tb,md,te,bm,blo,bhi)
                            ap.extend(p); sp[nm]=p
                        m=score_trades(ap)
                        if m is None: continue
                        spy_p=round(sum(sp.get('SPY',[])),0)
                        worst=min(round(sum(v),0) for v in sp.values())
                        ps=sum(1 for v in sp.values() if sum(v)>0)
                        sc=(m['pnl']*1.0 - m['mdd']*3.0 + m['rf']*200
                            + (m['wr']-40)*20 - m['mcl']*30
                            + (m['pf']-1.0)*500 + ps*100 - max(0,-worst)*2)
                        results.append({
                            'bl':blbl,'sla':sla,'tsr':tsr,'tb':tb,'md':md,'te':te,
                            'sc':round(sc,0),**m,'spy':spy_p,'wst':worst,'ps':ps,'sp':sp})

elapsed=tmod.time()-t0
print(f"Done in {elapsed:.1f}s. {len(results)} valid.\n")
results.sort(key=lambda x:x['sc'],reverse=True)

print("="*155)
print(f"{'#':>3} {'Bar':>8} {'SL':>4} {'TSR':>4} {'TB':>4} {'MD':>3} {'TE':>3} | {'Trd':>4} {'WR%':>5} {'P&L$':>7} {'MDD$':>6} {'PF':>5} {'AvgR':>5} {'RF':>5} {'MCL':>4} {'SPY$':>6} {'Wst$':>6} {'+S':>3} | {'Score':>7}")
print("-"*155)
for i,r in enumerate(results[:30]):
    print(f"{i+1:3d} {r['bl']:>8} {r['sla']:4.1f} {r['tsr']:4.1f} {r['tb']:4.1f} {r['md']:3.0f} {r['te']:3d} | {r['n']:4d} {r['wr']:5.1f} {r['pnl']:7.0f} {r['mdd']:6.0f} {r['pf']:5.2f} {r['avgr']:5.2f} {r['rf']:5.2f} {r['mcl']:4d} {r['spy']:6.0f} {r['wst']:6.0f} {r['ps']:3d} | {r['sc']:7.0f}")

# Per-stock for top 5
print("\n\n"+"="*90)
print("PER-STOCK: Top 5 configs")
print("="*90)
for rank in range(5):
    r=results[rank]
    print(f"\n--- #{rank+1}: Bar={r['bl']} SL={r['sla']} TSR={r['tsr']} TB={r['tb']} MD={r['md']:.0f} TE={r['te']} (Score={r['sc']}) ---")
    print(f"{'Stock':>8} {'Trd':>5} {'WR%':>6} {'P&L$':>8} {'MDD$':>7} {'PF':>6} {'AvgR':>6} {'MCL':>4}")
    for nm in sorted(stocks.keys()):
        p=r['sp'].get(nm,[])
        m=score_trades(p)
        if m is None:
            print(f"{nm:>8}  <5 trades ({len(p)})")
            continue
        print(f"{nm:>8} {m['n']:5d} {m['wr']:6.1f} {m['pnl']:8.0f} {m['mdd']:7.0f} {m['pf']:6.2f} {m['avgr']:6.2f} {m['mcl']:4d}")
    am=score_trades([x for v in r['sp'].values() for x in v])
    print(f"{'TOTAL':>8} {am['n']:5d} {am['wr']:6.1f} {am['pnl']:8.0f} {am['mdd']:7.0f} {am['pf']:6.2f} {am['avgr']:6.2f} {am['mcl']:4d}")

# vs current
print("\n\n"+"="*90)
print("CURRENT vs BEST")
print("="*90)
best=results[0]
curr=None
for r in results:
    if r['bl']=='Max≤3' and r['sla']==2.0 and r['tsr']==1.5 and r['tb']==1.0 and r['md']==3.0 and r['te']==20:
        curr=r; break
if curr:
    print(f"\nCurrent: Max≤3  SL=2.0 TSR=1.5 TB=1.0 MD=3 TE=20")
    print(f"Best:    {best['bl']:>6}  SL={best['sla']} TSR={best['tsr']} TB={best['tb']} MD={best['md']:.0f} TE={best['te']}")
    print(f"\n{'Metric':>18} {'Current':>10} {'Best':>10} {'Delta':>10}")
    print("-"*52)
    for k,l in [('n','Trades'),('wr','Win Rate %'),('pnl','Total P&L $'),('mdd','Max DD $'),('pf','Profit Factor'),('avgr','Avg R'),('rf','Recovery Factor'),('mcl','Max Consec Loss'),('spy','SPY P&L $'),('wst','Worst Stock $'),('ps','Profitable Stks')]:
        cv=curr[k]; bv=best[k]; d=bv-cv
        print(f"{l:>18} {cv:>10} {bv:>10} {d:>+10}")
    
    # Per-stock comparison
    print(f"\n{'Stock':>8} | {'--- Current ---':>25} | {'--- Best ---':>25}")
    print(f"{'':>8} | {'Trd':>4} {'WR%':>5} {'P&L$':>7} {'MDD$':>6} | {'Trd':>4} {'WR%':>5} {'P&L$':>7} {'MDD$':>6} | {'Better?':>8}")
    for nm in sorted(stocks.keys()):
        cm=score_trades(curr['sp'].get(nm,[])); bm2=score_trades(best['sp'].get(nm,[]))
        cn=cm['n'] if cm else 0; cw=cm['wr'] if cm else 0; cp=cm['pnl'] if cm else 0; cd=cm['mdd'] if cm else 0
        bn=bm2['n'] if bm2 else 0; bw=bm2['wr'] if bm2 else 0; bp=bm2['pnl'] if bm2 else 0; bd=bm2['mdd'] if bm2 else 0
        tag="✓" if bp>cp and bd<=cd else ("~" if bp>cp else "✗")
        print(f"{nm:>8} | {cn:4d} {cw:5.1f} {cp:7.0f} {cd:6.0f} | {bn:4d} {bw:5.1f} {bp:7.0f} {bd:6.0f} | {tag:>8}")
