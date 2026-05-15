#!/usr/bin/env python3
"""Compare baseline shorts vs ATR-contraction-filtered shorts."""
import pandas as pd, numpy as np
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
RISK = 100.0

def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def add_ind(df, fast=10, slow=50, tl=20, sma200_len=200):
    df = df.copy()
    df['fSma'] = df['Close'].rolling(fast).mean()
    df['sSma'] = df['Close'].rolling(slow).mean()
    df['sma200'] = df['Close'].rolling(sma200_len).mean()
    df['tr'] = np.maximum(df['High']-df['Low'],
        np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_sma20'] = df['atr'].rolling(20).mean()  # SMA of ATR for contraction check
    df['tEma'] = df['Close'].ewm(span=tl, adjust=False).mean()
    df['bRng'] = df['High'] - df['Low']
    df['fAbv'] = (df['fSma'] > df['sSma']).astype(int)
    df['xUp'] = (df['fAbv']==1) & (df['fAbv'].shift(1)==0)
    df['xDn'] = (df['fAbv']==0) & (df['fAbv'].shift(1)==1)
    return df

def backtest(df, name, use_atr_filter=False):
    cfg = dict(mdist=3.0, mbar=2.0, sla=1.0, tb=1.0, tsr=2.5, short_tp_r=3.0)
    df = add_ind(df)
    trades = []; pos=0; ep=er=tsl=0.0; lcd=0; bsc=999

    for i in range(1, len(df)):
        r = df.iloc[i]; atr = r['atr']
        if pd.isna(atr) or atr<=0: continue
        if r['xUp']: lcd=1; bsc=0
        elif r['xDn']: lcd=-1; bsc=0
        else: bsc+=1

        if pos!=0:
            hsl=False; xp=0.0; reason=''
            if pos==1:
                if r['Low']<=tsl: xp=tsl; hsl=True; reason='SL'
                if not hsl:
                    cr=(r['Close']-ep)/er if er>0 else 0
                    if cr>=cfg['tsr']:
                        et=r['tEma']-cfg['tb']*atr
                        if et>tsl: tsl=et
                    if r['Low']<=tsl: xp=tsl; hsl=True; reason='Trail'
            else:
                tp_price = ep - cfg['short_tp_r'] * er
                if r['High']>=tsl:
                    xp=tsl; hsl=True; reason='SL'
                elif r['Low']<=tp_price:
                    xp=tp_price; hsl=True; reason='TP'
            if hsl:
                t=trades[-1]
                t['exitDate']=r['Date'].strftime('%Y-%m-%d')
                t['exitPrice']=round(xp,2)
                pnl_r=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                t['pnlR']=round(pnl_r,2)
                t['pnlDollar']=round(pnl_r*RISK,2)
                t['exitReason']=reason
                ed=pd.to_datetime(t['entryDate']); xd=r['Date']
                t['durationDays']=int((xd-ed).days)
                pos=0

        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            bok=r['bRng']<=cfg['mbar']*atr
            sma200_ok = not pd.isna(r['sma200']) and r['Close'] < r['sma200']

            # ATR contraction filter: ATR < SMA20(ATR)
            if use_atr_filter:
                atr_contracting = not pd.isna(r['atr_sma20']) and r['atr'] < r['atr_sma20']
            else:
                atr_contracting = True  # no filter

            if dok and bok and xl:
                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                qty=max(1,round(RISK/rk)) if rk>0 else 1
                pos=1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':name,'dir':'LONG','entryDate':r['Date'].strftime('%Y-%m-%d'),
                    'entryPrice':round(r['Close'],2),'sl':round(sl,2),'risk':round(rk,2),
                    'qty':qty,'exitDate':'','exitPrice':0,'pnlR':0,'pnlDollar':0,
                    'exitReason':'','durationDays':0})
            elif dok and bok and xs and sma200_ok and atr_contracting:
                sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                qty=max(1,round(RISK/rk)) if rk>0 else 1
                pos=-1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':name,'dir':'SHORT','entryDate':r['Date'].strftime('%Y-%m-%d'),
                    'entryPrice':round(r['Close'],2),'sl':round(sl,2),'risk':round(rk,2),
                    'qty':qty,'exitDate':'','exitPrice':0,'pnlR':0,'pnlDollar':0,
                    'exitReason':'','durationDays':0})

    if pos!=0 and trades:
        t=trades[-1]; l=df.iloc[-1]
        t['exitDate']=l['Date'].strftime('%Y-%m-%d')
        t['exitPrice']=round(l['Close'],2)
        pnl_r=((l['Close']-ep)/er if pos==1 else (ep-l['Close'])/er) if er>0 else 0
        t['pnlR']=round(pnl_r,2); t['pnlDollar']=round(pnl_r*RISK,2)
        t['exitReason']='Open'
        ed=pd.to_datetime(t['entryDate'])
        t['durationDays']=int((l['Date']-ed).days)

    return trades

def summarize(trades, label):
    longs = [t for t in trades if t['dir']=='LONG' and t['exitDate']]
    shorts = [t for t in trades if t['dir']=='SHORT' and t['exitDate']]
    
    def stats(tlist, tag):
        if not tlist:
            return f"  {tag}: 0 trades"
        n = len(tlist)
        wins = [t for t in tlist if t['pnlR']>0]
        wr = len(wins)/n*100
        pnl = sum(t['pnlDollar'] for t in tlist)
        gross_w = sum(t['pnlDollar'] for t in tlist if t['pnlDollar']>0)
        gross_l = abs(sum(t['pnlDollar'] for t in tlist if t['pnlDollar']<0))
        pf = gross_w/gross_l if gross_l>0 else float('inf')
        avg_d = np.mean([t['durationDays'] for t in tlist])
        return f"  {tag}: {n} trades | WR {wr:.1f}% | P&L ${pnl:+,.0f} | PF {pf:.2f} | Avg {avg_d:.0f}d"
    
    total_pnl = sum(t['pnlDollar'] for t in trades if t['exitDate'])
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(stats(longs, "LONGS "))
    print(stats(shorts, "SHORTS"))
    print(f"  TOTAL P&L: ${total_pnl:+,.0f}")
    print(f"{'='*60}")
    
    return {
        'short_trades': len(shorts),
        'short_wr': len([t for t in shorts if t['pnlR']>0])/len(shorts)*100 if shorts else 0,
        'short_pnl': sum(t['pnlDollar'] for t in shorts),
        'total_pnl': total_pnl,
        'long_pnl': sum(t['pnlDollar'] for t in longs),
    }

# Run both versions
all_base = []
all_atr = []
per_stock_base = {}
per_stock_atr = {}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    df = load(f)
    base = backtest(df, name, use_atr_filter=False)
    atr = backtest(df, name, use_atr_filter=True)
    all_base.extend(base)
    all_atr.extend(atr)
    
    # Per-stock short comparison
    bs = [t for t in base if t['dir']=='SHORT' and t['exitDate']]
    as_ = [t for t in atr if t['dir']=='SHORT' and t['exitDate']]
    if bs or as_:
        b_pnl = sum(t['pnlDollar'] for t in bs)
        a_pnl = sum(t['pnlDollar'] for t in as_)
        per_stock_base[name] = (len(bs), b_pnl)
        per_stock_atr[name] = (len(as_), a_pnl)

base_stats = summarize(all_base, "BASELINE (SMA200 only)")
atr_stats = summarize(all_atr, "ATR CONTRACTION FILTER (SMA200 + ATR < SMA20(ATR))")

# Per-stock breakdown
print(f"\n{'='*60}")
print("  PER-STOCK SHORT COMPARISON")
print(f"{'='*60}")
print(f"  {'Stock':<8} {'Base#':>5} {'Base P&L':>10} {'Filt#':>5} {'Filt P&L':>10} {'Delta':>10}")
print(f"  {'-'*50}")
for stock in sorted(set(list(per_stock_base.keys()) + list(per_stock_atr.keys()))):
    bn, bp = per_stock_base.get(stock, (0, 0))
    an, ap = per_stock_atr.get(stock, (0, 0))
    delta = ap - bp
    marker = " ✓" if delta > 0 else (" ✗" if delta < 0 else "")
    print(f"  {stock:<8} {bn:>5} {bp:>+10,.0f} {an:>5} {ap:>+10,.0f} {delta:>+10,.0f}{marker}")

# Verdict
print(f"\n{'='*60}")
short_delta = atr_stats['short_pnl'] - base_stats['short_pnl']
total_delta = atr_stats['total_pnl'] - base_stats['total_pnl']
print(f"  Short P&L change: ${short_delta:+,.0f}")
print(f"  Total P&L change: ${total_delta:+,.0f}")
if short_delta > 0:
    print(f"  >>> ATR CONTRACTION FILTER IS BETTER. Proceed with update.")
else:
    print(f"  >>> BASELINE IS BETTER. Do NOT update.")
print(f"{'='*60}")
