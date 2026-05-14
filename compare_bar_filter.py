#!/usr/bin/env python3
"""Compare old (max bar ≤3×ATR) vs new (min bar ≥1×ATR) filter."""
import pandas as pd, numpy as np
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")

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

def backtest(df, name, bar_filter='old', bar_val=3.0):
    """bar_filter='old' means <=bar_val*ATR, 'new' means >=bar_val*ATR"""
    RISK = 100.0
    cfg = dict(mdist=3.0, sla=2.0, tb=1.0, tsr=1.5)
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
                pnl_r=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                t['pnlR']=round(pnl_r,2)
                t['pnlDollar']=round(pnl_r*RISK,2)
                t['win'] = pnl_r > 0
                t['durationDays'] = int((r['Date'] - pd.to_datetime(t['entryDate'])).days)
                pos=0

        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            if bar_filter == 'old':
                bok = r['bRng'] <= bar_val * atr
            else:
                bok = r['bRng'] >= bar_val * atr
            
            if dok and bok and xl:
                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                pos=1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'entryDate':r['Date'].strftime('%Y-%m-%d'),'pnlR':0,'pnlDollar':0,'win':False,'durationDays':0})
            elif dok and bok and xs:
                sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                pos=-1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'entryDate':r['Date'].strftime('%Y-%m-%d'),'pnlR':0,'pnlDollar':0,'win':False,'durationDays':0})

    # Close open trade
    if pos!=0 and trades:
        l=df.iloc[-1]
        pnl_r=((l['Close']-ep)/er if pos==1 else (ep-l['Close'])/er) if er>0 else 0
        trades[-1]['pnlR']=round(pnl_r,2)
        trades[-1]['pnlDollar']=round(pnl_r*RISK,2)
        trades[-1]['win']=pnl_r>0
        trades[-1]['durationDays']=int((l['Date']-pd.to_datetime(trades[-1]['entryDate'])).days)

    return trades

def metrics(trades, label):
    if not trades:
        return {'label':label, 'trades':0}
    wins = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    total_pnl = sum(t['pnlDollar'] for t in trades)
    total_profit = sum(t['pnlDollar'] for t in wins)
    total_loss = sum(t['pnlDollar'] for t in losses)
    wr = len(wins)/len(trades)*100
    pf = abs(total_profit/total_loss) if total_loss != 0 else float('inf')
    avg_r = sum(t['pnlR'] for t in trades)/len(trades)
    avg_win_dur = np.mean([t['durationDays'] for t in wins]) if wins else 0
    avg_loss_dur = np.mean([t['durationDays'] for t in losses]) if losses else 0
    
    # Max drawdown
    eq = 0; peak = 0; mdd = 0
    for t in trades:
        eq += t['pnlDollar']
        if eq > peak: peak = eq
        dd = peak - eq
        if dd > mdd: mdd = dd
    
    return {
        'label': label, 'trades': len(trades), 'wins': len(wins),
        'winRate': round(wr, 1), 'totalPnl': round(total_pnl, 0),
        'totalProfit': round(total_profit, 0), 'totalLoss': round(total_loss, 0),
        'pf': round(pf, 2), 'avgR': round(avg_r, 2), 'maxDD': round(mdd, 0),
        'avgWinDur': round(avg_win_dur, 1), 'avgLossDur': round(avg_loss_dur, 1),
    }

# Run comparison
files = sorted(DATA_DIR.glob("*.csv"))
stocks = {}
for f in files:
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    stocks[name] = load(f)

print("=" * 110)
print(f"{'':20s} | {'OLD: bar ≤ 3×ATR':>45s} | {'NEW: bar ≥ 1×ATR':>40s}")
print(f"{'Stock':20s} | {'Trades':>6s} {'WR%':>5s} {'P&L$':>8s} {'Profit$':>8s} {'Loss$':>8s} {'PF':>5s} {'AvgR':>5s} {'MaxDD':>6s} | {'Trades':>6s} {'WR%':>5s} {'P&L$':>8s} {'Profit$':>8s} {'Loss$':>8s} {'PF':>5s} {'AvgR':>5s} {'MaxDD':>6s}")
print("=" * 110)

all_old = []; all_new = []

for name, df in sorted(stocks.items()):
    old_trades = backtest(df, name, 'old', 3.0)
    new_trades = backtest(df, name, 'new', 1.0)
    all_old.extend(old_trades)
    all_new.extend(new_trades)
    
    o = metrics(old_trades, name)
    n = metrics(new_trades, name)
    
    print(f"{name:20s} | {o['trades']:6d} {o['winRate']:5.1f} {o['totalPnl']:8.0f} {o['totalProfit']:8.0f} {o['totalLoss']:8.0f} {o['pf']:5.2f} {o['avgR']:5.2f} {o['maxDD']:6.0f} | {n['trades']:6d} {n['winRate']:5.1f} {n['totalPnl']:8.0f} {n['totalProfit']:8.0f} {n['totalLoss']:8.0f} {n['pf']:5.2f} {n['avgR']:5.2f} {n['maxDD']:6.0f}")

print("=" * 110)
o = metrics(all_old, 'ALL')
n = metrics(all_new, 'ALL')
print(f"{'TOTAL':20s} | {o['trades']:6d} {o['winRate']:5.1f} {o['totalPnl']:8.0f} {o['totalProfit']:8.0f} {o['totalLoss']:8.0f} {o['pf']:5.2f} {o['avgR']:5.2f} {o['maxDD']:6.0f} | {n['trades']:6d} {n['winRate']:5.1f} {n['totalPnl']:8.0f} {n['totalProfit']:8.0f} {n['totalLoss']:8.0f} {n['pf']:5.2f} {n['avgR']:5.2f} {n['maxDD']:6.0f}")
print("=" * 110)

# Also test a few other min bar thresholds
print("\n\nSweep: min bar thresholds (ALL stocks combined)")
print(f"{'MinBar':>8s} {'Trades':>7s} {'WR%':>6s} {'P&L$':>9s} {'PF':>6s} {'AvgR':>6s} {'MaxDD$':>8s} {'AvgWinD':>8s} {'AvgLosD':>8s}")
print("-" * 75)
for mb in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
    all_t = []
    for name, df in sorted(stocks.items()):
        all_t.extend(backtest(df, name, 'new', mb))
    m = metrics(all_t, f'{mb}x')
    print(f"{mb:8.2f} {m['trades']:7d} {m['winRate']:6.1f} {m['totalPnl']:9.0f} {m['pf']:6.2f} {m['avgR']:6.2f} {m['maxDD']:8.0f} {m['avgWinDur']:8.1f} {m['avgLossDur']:8.1f}")
