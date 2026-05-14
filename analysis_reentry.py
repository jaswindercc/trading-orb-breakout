#!/usr/bin/env python3
"""
Deep analysis: Why do we miss trend continuations after exit?
Focus on SPY and all stocks. Find missed moves and potential re-entry rules.
"""
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

def add_ind(df):
    d = df.copy()
    d['fSma'] = d['Close'].rolling(10).mean()
    d['sSma'] = d['Close'].rolling(50).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr'] = d['tr'].rolling(14).mean()
    d['tEma'] = d['Close'].ewm(span=20, adjust=False).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp'] = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn'] = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)
    return d

def backtest_detailed(df, name, cfg):
    """Returns detailed trades with entry/exit info and gap analysis."""
    RISK = 100.0
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
                t['exitDate']=r['Date']
                t['exitPrice']=round(xp,2)
                pnl_r=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                t['pnlR']=round(pnl_r,2)
                t['pnlDollar']=round(pnl_r*RISK,2)
                t['exitIdx']=i
                t['exitReason']='trail' if pnl_r>0 else 'SL'
                # What was the trend state at exit?
                t['fAbv_at_exit'] = r['fAbv']
                pos=0

        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            bok=r['bRng']<=cfg['mbar']*atr
            if dok and bok and xl:
                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                pos=1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':name,'dir':'LONG','entryDate':r['Date'],
                    'entryPrice':round(r['Close'],2),'entryIdx':i,
                    'exitDate':None,'exitPrice':0,'pnlR':0,'pnlDollar':0,
                    'exitIdx':None,'exitReason':'','fAbv_at_exit':0})
            elif dok and bok and xs:
                sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                pos=-1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':name,'dir':'SHORT','entryDate':r['Date'],
                    'entryPrice':round(r['Close'],2),'entryIdx':i,
                    'exitDate':None,'exitPrice':0,'pnlR':0,'pnlDollar':0,
                    'exitIdx':None,'exitReason':'','fAbv_at_exit':0})

    return trades, df

# ================================================================
# ANALYSIS
# ================================================================
cfg = dict(mdist=3.0, mbar=2.0, sla=2.0, tb=1.0, tsr=2.5)

stocks = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    stocks[name] = load(f)

print("=" * 120)
print("ANALYSIS: Missed trend continuations after trail stop exits")
print("=" * 120)

all_gaps = []

for name in ['SPY', 'AAPL', 'AMD', 'GOOGL', 'META', 'NVDA', 'TSLA']:
    trades, df = backtest_detailed(stocks[name], name, cfg)
    
    print(f"\n{'='*80}")
    print(f"  {name}: {len(trades)} trades")
    print(f"{'='*80}")
    
    # For each winning exit (trail stop), analyze what happened next
    for i, t in enumerate(trades):
        if t['exitDate'] is None or t['exitReason'] != 'trail':
            continue
        
        exit_idx = t['exitIdx']
        exit_date = t['exitDate']
        exit_price = t['exitPrice']
        direction = t['dir']
        fAbv = t['fAbv_at_exit']
        
        # What was the trend state? (fast SMA still above slow = bullish trend intact)
        trend_intact = (fAbv == 1 and direction == 'LONG') or (fAbv == 0 and direction == 'SHORT')
        
        # How far did price go AFTER exit before the next cross?
        # Find next entry or end of data
        next_entry_idx = None
        if i + 1 < len(trades):
            next_entry_idx = trades[i+1]['entryIdx']
        
        end_idx = next_entry_idx if next_entry_idx else len(df) - 1
        
        # Price movement after exit
        post_exit = df.iloc[exit_idx:end_idx+1]
        if len(post_exit) < 2:
            continue
        
        if direction == 'LONG':
            max_after = post_exit['High'].max()
            missed_move = max_after - exit_price
            missed_pct = (missed_move / exit_price) * 100
        else:
            min_after = post_exit['Low'].min()
            missed_move = exit_price - min_after
            missed_pct = (missed_move / exit_price) * 100
        
        days_flat = len(post_exit)
        
        # Was there a pullback to EMA that could have been a re-entry?
        pullback_to_ema = False
        pullback_date = None
        for j in range(exit_idx + 1, min(exit_idx + 30, end_idx + 1)):
            if j >= len(df): break
            row = df.iloc[j]
            if pd.isna(row['tEma']) or pd.isna(row['fSma']) or pd.isna(row['sSma']): continue
            if direction == 'LONG':
                # Price pulled back near EMA20 while fast > slow (trend intact)
                if row['fSma'] > row['sSma'] and row['Low'] <= row['tEma'] * 1.01:
                    pullback_to_ema = True
                    pullback_date = row['Date']
                    break
            else:
                if row['fSma'] < row['sSma'] and row['High'] >= row['tEma'] * 0.99:
                    pullback_to_ema = True
                    pullback_date = row['Date']
                    break
        
        # Did we eventually re-enter?
        re_entered = next_entry_idx is not None and i + 1 < len(trades)
        re_entry_same_dir = re_entered and trades[i+1]['dir'] == direction
        
        gap_info = {
            'stock': name, 'dir': direction,
            'exit_date': exit_date.strftime('%Y-%m-%d'),
            'exit_price': exit_price,
            'pnlR': t['pnlR'],
            'trend_intact': trend_intact,
            'missed_move': round(missed_move, 2),
            'missed_pct': round(missed_pct, 1),
            'days_flat': days_flat,
            'pullback_to_ema': pullback_to_ema,
            'pullback_date': pullback_date.strftime('%Y-%m-%d') if pullback_date else '-',
            're_entered': re_entered,
            're_entry_same_dir': re_entry_same_dir,
        }
        all_gaps.append(gap_info)
        
        marker = "*** MISSED ***" if trend_intact and missed_pct > 3 else ""
        print(f"  Exit {exit_date.strftime('%Y-%m-%d')} {direction:>5s} @${exit_price:<8.2f} +{t['pnlR']:.1f}R | "
              f"Trend intact: {'YES' if trend_intact else 'no ':>3s} | "
              f"Missed: ${missed_move:>7.2f} ({missed_pct:>5.1f}%) over {days_flat:>3d}d | "
              f"EMA pullback: {'YES' if pullback_to_ema else 'no ':>3s} ({gap_info['pullback_date']:>10s}) | "
              f"Re-entered: {'YES' if re_entry_same_dir else 'no':>3s}  {marker}")

# ================================================================
# SUMMARY STATS
# ================================================================
print("\n\n" + "=" * 120)
print("SUMMARY: Missed opportunities after trail exits")
print("=" * 120)

gaps_with_trend = [g for g in all_gaps if g['trend_intact']]
gaps_with_ema_pb = [g for g in gaps_with_trend if g['pullback_to_ema']]
big_misses = [g for g in gaps_with_trend if g['missed_pct'] > 3]
big_misses_with_pb = [g for g in big_misses if g['pullback_to_ema']]

print(f"\nTotal trail exits analyzed: {len(all_gaps)}")
print(f"Exits where trend was STILL intact (fast SMA still correct side): {len(gaps_with_trend)} ({len(gaps_with_trend)/len(all_gaps)*100:.0f}%)")
print(f"  → Of those, price pulled back to EMA20 within 30 days: {len(gaps_with_ema_pb)} ({len(gaps_with_ema_pb)/len(gaps_with_trend)*100:.0f}%)")
print(f"  → Of those, missed move > 3%: {len(big_misses)} ({len(big_misses)/len(gaps_with_trend)*100:.0f}%)")
print(f"  → Big misses with EMA pullback (re-entry opportunity): {len(big_misses_with_pb)}")
print(f"\nAvg missed move (trend intact): ${np.mean([g['missed_move'] for g in gaps_with_trend]):.2f} ({np.mean([g['missed_pct'] for g in gaps_with_trend]):.1f}%)")
print(f"Avg days flat (trend intact): {np.mean([g['days_flat'] for g in gaps_with_trend]):.0f}")

if big_misses_with_pb:
    print(f"\n--- Biggest missed moves with EMA pullback re-entry opportunity ---")
    for g in sorted(big_misses_with_pb, key=lambda x: x['missed_pct'], reverse=True)[:15]:
        print(f"  {g['stock']:>6s} {g['exit_date']} {g['dir']:>5s} exited @${g['exit_price']:<8.2f} | Missed ${g['missed_move']:>8.2f} ({g['missed_pct']:>5.1f}%) | EMA pullback on {g['pullback_date']}")

# ================================================================
# POTENTIAL RE-ENTRY RULES
# ================================================================
print("\n\n" + "=" * 120)
print("TESTING RE-ENTRY RULES")
print("=" * 120)

def backtest_with_reentry(df, name, cfg, reentry_mode):
    """
    reentry_mode:
    'none' = current (no re-entry)
    'ema_pullback' = re-enter on pullback to EMA20 if trend still intact
    'ema_cross' = re-enter when price crosses back above EMA20 after pullback
    'next_bar_close' = re-enter N bars after trail exit if trend intact
    """
    RISK = 100.0
    df = add_ind(df)
    pnls = []; pos=0; ep=er=tsl=0.0; lcd=0; bsc=999
    last_exit_dir = 0; last_exit_idx = -999; trailing_was_hit = False

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
                pr=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                pnls.append(round(pr*RISK,2))
                trailing_was_hit = pr > 0
                last_exit_dir = pos
                last_exit_idx = i
                pos=0

        if pos==0:
            entered = False
            # Standard cross entry
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            bok=r['bRng']<=cfg['mbar']*atr
            if dok and bok and xl:
                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                pos=1; ep=r['Close']; er=rk; tsl=sl; entered=True
                trailing_was_hit=False
            elif dok and bok and xs:
                sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                pos=-1; ep=r['Close']; er=rk; tsl=sl; entered=True
                trailing_was_hit=False
            
            # Re-entry logic (only if no standard entry happened)
            if not entered and trailing_was_hit and (i - last_exit_idx) >= 2:
                trend_ok = False
                reentry_signal = False
                
                if last_exit_dir == 1 and r['fSma'] > r['sSma']:  # was long, trend still bullish
                    trend_ok = True
                elif last_exit_dir == -1 and r['fSma'] < r['sSma']:  # was short, trend still bearish
                    trend_ok = True
                
                if trend_ok and reentry_mode == 'ema_pullback':
                    # Price touched or dipped below EMA20 then closed above it
                    if last_exit_dir == 1:
                        if r['Low'] <= r['tEma'] and r['Close'] > r['tEma'] and bok:
                            reentry_signal = True
                    else:
                        if r['High'] >= r['tEma'] and r['Close'] < r['tEma'] and bok:
                            reentry_signal = True
                
                elif trend_ok and reentry_mode == 'ema_bounce':
                    # Price was below EMA, now closes back above (bounce off EMA)
                    if last_exit_dir == 1:
                        prev = df.iloc[i-1] if i > 0 else r
                        if prev['Close'] <= prev['tEma'] and r['Close'] > r['tEma'] and bok:
                            reentry_signal = True
                    else:
                        prev = df.iloc[i-1] if i > 0 else r
                        if prev['Close'] >= prev['tEma'] and r['Close'] < r['tEma'] and bok:
                            reentry_signal = True
                
                elif trend_ok and reentry_mode == 'pullback_sma':
                    # Price pulls back to fast SMA (not EMA)
                    if last_exit_dir == 1:
                        if r['Low'] <= r['fSma'] and r['Close'] > r['fSma'] and bok:
                            reentry_signal = True
                    else:
                        if r['High'] >= r['fSma'] and r['Close'] < r['fSma'] and bok:
                            reentry_signal = True
                
                if reentry_signal:
                    if last_exit_dir == 1:
                        sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                        pos=1; ep=r['Close']; er=rk; tsl=sl
                    else:
                        sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                        pos=-1; ep=r['Close']; er=rk; tsl=sl
                    trailing_was_hit=False

    if pos!=0:
        pr=((df.iloc[-1]['Close']-ep)/er if pos==1 else (ep-df.iloc[-1]['Close'])/er) if er>0 else 0
        pnls.append(round(pr*RISK,2))
    return pnls

def score(pnls):
    if len(pnls)<3: return None
    p=np.array(pnls); n=len(p)
    w=p[p>0]; l=p[p<=0]
    tp=p.sum(); tw=w.sum() if len(w) else 0; tl=l.sum() if len(l) else 0
    wr=len(w)/n*100; pf=abs(tw/tl) if tl!=0 else 99
    eq=np.cumsum(p); pk=np.maximum.accumulate(eq); dd=pk-eq; mdd=dd.max()
    rf=tp/mdd if mdd>0 else 99
    cl=0; mcl=0
    for x in p<=0:
        if x: cl+=1
        else: cl=0
        mcl=max(mcl,cl)
    return {'n':n,'wr':round(wr,1),'pnl':round(tp,0),'mdd':round(mdd,0),
            'pf':round(pf,2),'avgr':round((p/100).mean(),2),'rf':round(rf,2),'mcl':mcl}

modes = ['none', 'ema_pullback', 'ema_bounce', 'pullback_sma']
mode_labels = {
    'none': 'Current (no re-entry)',
    'ema_pullback': 'Re-enter on EMA20 pullback',
    'ema_bounce': 'Re-enter on EMA20 bounce',
    'pullback_sma': 'Re-enter on SMA10 pullback',
}

for mode in modes:
    print(f"\n--- {mode_labels[mode]} ---")
    print(f"{'Stock':>8s} {'Trd':>5s} {'WR%':>6s} {'P&L$':>8s} {'MDD$':>7s} {'PF':>6s} {'AvgR':>6s} {'RF':>6s} {'MCL':>4s}")
    
    all_pnls = []
    for name in ['SPY', 'AAPL', 'AMD', 'GOOGL', 'META', 'NVDA', 'TSLA']:
        df = add_ind(stocks[name])
        pnls = backtest_with_reentry(stocks[name], name, cfg, mode)
        all_pnls.extend(pnls)
        m = score(pnls)
        if m:
            print(f"{name:>8s} {m['n']:5d} {m['wr']:6.1f} {m['pnl']:8.0f} {m['mdd']:7.0f} {m['pf']:6.2f} {m['avgr']:6.2f} {m['rf']:6.2f} {m['mcl']:4d}")
        else:
            print(f"{name:>8s}  <3 trades")
    
    am = score(all_pnls)
    if am:
        print(f"{'TOTAL':>8s} {am['n']:5d} {am['wr']:6.1f} {am['pnl']:8.0f} {am['mdd']:7.0f} {am['pf']:6.2f} {am['avgr']:6.2f} {am['rf']:6.2f} {am['mcl']:4d}")

# Also test with different wait periods before re-entry
print("\n\n" + "=" * 120)
print("SENSITIVITY: EMA pullback re-entry with different min wait days")
print("=" * 120)

for wait in [2, 3, 5, 7, 10]:
    def bt_wait(df, name, cfg, wait_days):
        RISK = 100.0
        df = add_ind(df)
        pnls = []; pos=0; ep=er=tsl=0.0; lcd=0; bsc=999
        led=0; lei=-999; twh=False
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
                    pr=((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0
                    pnls.append(round(pr*RISK,2))
                    twh=pr>0; led=pos; lei=i; pos=0
            if pos==0:
                entered=False
                xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
                dk=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
                bk=r['bRng']<=cfg['mbar']*atr
                if dk and bk and xl:
                    sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                    pos=1; ep=r['Close']; er=rk; tsl=sl; entered=True; twh=False
                elif dk and bk and xs:
                    sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                    pos=-1; ep=r['Close']; er=rk; tsl=sl; entered=True; twh=False
                if not entered and twh and (i-lei)>=wait_days:
                    tok=False
                    if led==1 and r['fSma']>r['sSma']: tok=True
                    elif led==-1 and r['fSma']<r['sSma']: tok=True
                    if tok:
                        sig=False
                        if led==1 and r['Low']<=r['tEma'] and r['Close']>r['tEma'] and bk: sig=True
                        elif led==-1 and r['High']>=r['tEma'] and r['Close']<r['tEma'] and bk: sig=True
                        if sig:
                            if led==1:
                                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                                pos=1; ep=r['Close']; er=rk; tsl=sl
                            else:
                                sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                                pos=-1; ep=r['Close']; er=rk; tsl=sl
                            twh=False
        if pos!=0:
            pr=((df.iloc[-1]['Close']-ep)/er if pos==1 else (ep-df.iloc[-1]['Close'])/er) if er>0 else 0
            pnls.append(round(pr*RISK,2))
        return pnls
    
    all_p = []
    spy_p = []
    for name in ['SPY', 'AAPL', 'AMD', 'GOOGL', 'META', 'NVDA', 'TSLA']:
        p = bt_wait(stocks[name], name, cfg, wait)
        all_p.extend(p)
        if name == 'SPY': spy_p = p
    
    am = score(all_p)
    sm = score(spy_p)
    if am and sm:
        print(f"Wait {wait:2d}d: ALL {am['n']:4d}t {am['wr']:5.1f}% ${am['pnl']:>7.0f} DD${am['mdd']:>5.0f} PF={am['pf']:.2f} RF={am['rf']:.2f} MCL={am['mcl']} | SPY {sm['n']:3d}t {sm['wr']:5.1f}% ${sm['pnl']:>6.0f} DD${sm['mdd']:>4.0f}")
