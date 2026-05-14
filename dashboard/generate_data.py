#!/usr/bin/env python3
"""Generate backtest JSON data for the React dashboard. Risk = $100 per trade."""
import pandas as pd, numpy as np, json
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/data.json")

def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def add_ind(df, fast=10, slow=50, tl=20):
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

def backtest(df, name):
    RISK = 100.0
    cfg = dict(mdist=3.0, mbar=2.0, sla=2.0, tb=1.0, tsr=2.5)
    df = add_ind(df)
    trades = []; pos=0; ep=er=tsl=0.0; lcd=0; bsc=999

    for i in range(1, len(df)):
        r = df.iloc[i]; atr = r['atr']
        if pd.isna(atr) or atr<=0: continue
        if r['xUp']: lcd=1; bsc=0
        elif r['xDn']: lcd=-1; bsc=0
        else: bsc+=1

        if pos!=0:
            hsl=False; xp=0.0
            if pos==1:
                if r['Low']<=tsl: xp=tsl; hsl=True
                if not hsl:
                    cr=(r['Close']-ep)/er if er>0 else 0
                    if cr>=cfg['tsr']:
                        et=r['tEma']-cfg['tb']*atr
                        if et>tsl: tsl=et
            else:
                if r['High']>=tsl: xp=tsl; hsl=True
                if not hsl:
                    cr=(ep-r['Close'])/er if er>0 else 0
                    if cr>=cfg['tsr']:
                        et=r['tEma']+cfg['tb']*atr
                        if et<tsl: tsl=et
            if hsl:
                t=trades[-1]
                t['exitDate']=r['Date'].strftime('%Y-%m-%d')
                t['exitPrice']=round(xp,2)
                pnl_r=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                t['pnlR']=round(pnl_r,2)
                t['pnlDollar']=round(pnl_r*RISK,2)
                t['exitReason']='SL' if pnl_r<=0 else 'Trail'
                # Duration
                ed=pd.to_datetime(t['entryDate']); xd=r['Date']
                t['durationDays']=int((xd-ed).days)
                pos=0

        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            bok=r['bRng']<=cfg['mbar']*atr
            if dok and bok and xl:
                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                qty=max(1,round(RISK/rk)) if rk>0 else 1
                pos=1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':name,'dir':'LONG','entryDate':r['Date'].strftime('%Y-%m-%d'),
                    'entryPrice':round(r['Close'],2),'sl':round(sl,2),'risk':round(rk,2),
                    'qty':qty,'exitDate':'','exitPrice':0,'pnlR':0,'pnlDollar':0,
                    'exitReason':'','durationDays':0})
            elif dok and bok and xs:
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

    # Price series for charts
    prices = []
    for _, row in df.iterrows():
        if pd.notna(row['fSma']) and pd.notna(row['sSma']):
            prices.append({
                'date': row['Date'].strftime('%Y-%m-%d'),
                'close': round(row['Close'],2),
                'fSma': round(row['fSma'],2),
                'sSma': round(row['sSma'],2)
            })
    return trades, prices

# Run
all_data = {'stocks': {}, 'allTrades': [], 'settings': {
    'fastSma': 10, 'slowSma': 50, 'slAtrMult': 2.0,
    'trailEmaLen': 20, 'trailAtrBuf': 1.0, 'trailStartR': 2.5,
    'maxBarAtr': 2.0, 'maxDistAtr': 3.0, 'riskPerTrade': 100
}}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    trades, prices = backtest(load(f), name)
    all_data['stocks'][name] = {'trades': trades, 'prices': prices}
    all_data['allTrades'].extend(trades)
    print(f"{name}: {len(trades)} trades, {len(prices)} price bars")

# Sort all trades by date
all_data['allTrades'].sort(key=lambda t: t['entryDate'])

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_data))
print(f"\nWritten {OUT} ({OUT.stat().st_size//1024}KB)")
