#!/usr/bin/env python3
"""
Deep ATR-based short filter analysis.
Question: Can we use ATR characteristics at entry time to avoid bad shorts?

Examines:
  Part 1: ATR profile of winning vs losing shorts (what's different?)
  Part 2: ATR% threshold filters (min volatility to enter short)
  Part 3: ATR expansion/contraction filters (is volatility growing?)
  Part 4: ATR percentile rank filters (is current ATR high relative to history?)
  Part 5: ATR trend filters (is ATR trending up = expanding vol?)
  Part 6: Combined filters (ATR + existing SMA200)
  Part 7: ATR-based dynamic SL for shorts (wider stop when vol is high)
  Part 8: ATR-based dynamic TP for shorts (lower TP when vol is low)
  Part 9: Per-stock ATR analysis (which stocks have the right ATR profile?)
  Part 10: Recommendation
"""
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

def add_ind(df):
    df = df.copy()
    df['fSma'] = df['Close'].rolling(10).mean()
    df['sSma'] = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean()
    df['tr'] = np.maximum(df['High']-df['Low'],
        np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['atr'] = df['tr'].rolling(14).mean()
    df['tEma'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['bRng'] = df['High'] - df['Low']
    df['fAbv'] = (df['fSma'] > df['sSma']).astype(int)
    df['xUp'] = (df['fAbv']==1) & (df['fAbv'].shift(1)==0)
    df['xDn'] = (df['fAbv']==0) & (df['fAbv'].shift(1)==1)
    
    # ATR-derived features
    df['atr_pct'] = df['atr'] / df['Close'] * 100  # ATR as % of price
    df['atr_sma20'] = df['atr'].rolling(20).mean()  # 20-bar SMA of ATR
    df['atr_sma50'] = df['atr'].rolling(50).mean()  # 50-bar SMA of ATR
    df['atr_ratio'] = df['atr'] / df['atr_sma20']   # ATR relative to its own average
    df['atr_expanding'] = (df['atr'] > df['atr_sma20']).astype(int)  # 1 = vol expanding
    df['atr_pct_rank20'] = df['atr'].rolling(20).rank(pct=True)  # percentile rank in last 20 bars
    df['atr_pct_rank50'] = df['atr'].rolling(50).rank(pct=True)  # percentile rank in last 50 bars
    df['atr_change5'] = df['atr'].pct_change(5)  # ATR 5-day change rate
    df['atr_change10'] = df['atr'].pct_change(10)  # ATR 10-day change rate
    df['mom20'] = df['Close'].pct_change(20)  # 20-day momentum
    
    return df

def backtest_shorts(df, name, filters=None, sl_mult=1.0, tp_r=3.0):
    """Backtest only short trades with configurable filters."""
    cfg = dict(mdist=3.0, mbar=2.0, sla=sl_mult, tb=1.0, tsr=2.5)
    trades = []; pos=0; ep=er=tsl=0.0; lcd=0; bsc=999

    for i in range(1, len(df)):
        r = df.iloc[i]; atr = r['atr']
        if pd.isna(atr) or atr<=0: continue
        if r['xUp']: lcd=1; bsc=0
        elif r['xDn']: lcd=-1; bsc=0
        else: bsc+=1

        if pos!=0:
            hsl=False; xp=0.0; reason=''
            tp_price = ep - tp_r * er
            if r['High']>=tsl:
                xp=tsl; hsl=True; reason='SL'
            elif r['Low']<=tp_price:
                xp=tp_price; hsl=True; reason='TP'
            if hsl:
                t=trades[-1]
                t['exitDate']=r['Date'].strftime('%Y-%m-%d')
                t['exitPrice']=round(xp,2)
                pnl_r=((ep-xp)/er) if er>0 else 0
                t['pnlR']=round(pnl_r,2)
                t['pnlDollar']=round(pnl_r*RISK,2)
                t['exitReason']=reason
                ed=pd.to_datetime(t['entryDate']); xd=r['Date']
                t['durationDays']=int((xd-ed).days)
                pos=0

        if pos==0:
            xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            bok=r['bRng']<=cfg['mbar']*atr
            sma200_ok = not pd.isna(r['sma200']) and r['Close'] < r['sma200']
            
            if dok and bok and xs and sma200_ok:
                # Apply additional filters
                skip = False
                if filters:
                    for f_name, f_col, f_op, f_val in filters:
                        val = r.get(f_col, np.nan)
                        if pd.isna(val):
                            skip = True; break
                        if f_op == '>' and not (val > f_val): skip = True; break
                        if f_op == '<' and not (val < f_val): skip = True; break
                        if f_op == '>=' and not (val >= f_val): skip = True; break
                        if f_op == '<=' and not (val <= f_val): skip = True; break
                
                if not skip:
                    sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                    qty=max(1,round(RISK/rk)) if rk>0 else 1
                    pos=-1; ep=r['Close']; er=rk; tsl=sl
                    trades.append({
                        'stock':name,'dir':'SHORT',
                        'entryDate':r['Date'].strftime('%Y-%m-%d'),
                        'entryPrice':round(r['Close'],2),
                        'sl':round(sl,2),'risk':round(rk,2),
                        'qty':qty,'exitDate':'','exitPrice':0,
                        'pnlR':0,'pnlDollar':0,'exitReason':'','durationDays':0,
                        # Store ATR features at entry for analysis
                        'atr_pct': round(r['atr_pct'],3) if not pd.isna(r['atr_pct']) else None,
                        'atr_ratio': round(r['atr_ratio'],3) if not pd.isna(r['atr_ratio']) else None,
                        'atr_expanding': int(r['atr_expanding']) if not pd.isna(r['atr_expanding']) else None,
                        'atr_pct_rank20': round(r['atr_pct_rank20'],3) if not pd.isna(r['atr_pct_rank20']) else None,
                        'atr_pct_rank50': round(r['atr_pct_rank50'],3) if not pd.isna(r['atr_pct_rank50']) else None,
                        'atr_change5': round(r['atr_change5'],4) if not pd.isna(r['atr_change5']) else None,
                        'atr_change10': round(r['atr_change10'],4) if not pd.isna(r['atr_change10']) else None,
                        'mom20': round(r['mom20'],4) if not pd.isna(r['mom20']) else None,
                    })

    # Close open position
    if pos!=0 and trades:
        t=trades[-1]; l=df.iloc[-1]
        t['exitDate']=l['Date'].strftime('%Y-%m-%d')
        t['exitPrice']=round(l['Close'],2)
        pnl_r=((ep-l['Close'])/er) if er>0 else 0
        t['pnlR']=round(pnl_r,2); t['pnlDollar']=round(pnl_r*RISK,2)
        t['exitReason']='Open'
        t['durationDays']=int((l['Date']-pd.to_datetime(t['entryDate'])).days)

    return [t for t in trades if t['exitDate']]

def summarize(trades, label=""):
    if not trades:
        return {'label':label,'n':0,'w':0,'l':0,'wr':0,'pnl':0,'avg_r':0,'pf':0,'avg_d':0,'tp':0,'tl':0}
    wins = [t for t in trades if t['pnlDollar']>0]
    losses = [t for t in trades if t['pnlDollar']<=0]
    pnl = sum(t['pnlDollar'] for t in trades)
    tp = sum(t['pnlDollar'] for t in wins) if wins else 0
    tl = sum(t['pnlDollar'] for t in losses) if losses else 0
    wr = len(wins)/len(trades)*100
    pf = abs(tp/tl) if tl!=0 else float('inf')
    avg_r = np.mean([t['pnlR'] for t in trades])
    avg_d = np.mean([t['durationDays'] for t in trades])
    return {'label':label,'n':len(trades),'w':len(wins),'l':len(losses),
            'wr':round(wr,1),'pnl':round(pnl,0),'avg_r':round(avg_r,2),
            'pf':round(pf,2),'avg_d':round(avg_d,1),'tp':round(tp,0),'tl':round(tl,0)}

def print_summary_table(results):
    print(f"  {'Strategy':<45} {'#T':>3} {'W':>3} {'L':>3} {'WR%':>5} {'P&L':>8} {'AvgR':>6} {'PF':>5} {'AvgD':>5}")
    print(f"  {'─'*90}")
    for r in results:
        pf_s = f"{r['pf']:.2f}" if r['pf'] != float('inf') else '∞'
        print(f"  {r['label']:<45} {r['n']:>3} {r['w']:>3} {r['l']:>3} {r['wr']:>5.1f} {r['pnl']:>8.0f} {r['avg_r']:>6.2f} {pf_s:>5} {r['avg_d']:>5.1f}")

# Load all stocks
stocks = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    stocks[name] = add_ind(load(f))
    
print("="*120)
print("DEEP ATR ANALYSIS: Can ATR characteristics predict short trade success?")
print("="*120)
print(f"12 stocks: {', '.join(sorted(stocks.keys()))}")
print()

# ═══════════════════════════════════════════════════════════════
# PART 1: Profile winning vs losing shorts
# ═══════════════════════════════════════════════════════════════
print("="*120)
print("PART 1: ATR PROFILE OF WINNING vs LOSING SHORTS")
print("="*120)
print("  What ATR conditions exist when we enter shorts that win vs shorts that lose?\n")

all_shorts = []
for name, df in sorted(stocks.items()):
    all_shorts.extend(backtest_shorts(df, name))

wins = [t for t in all_shorts if t['pnlDollar'] > 0]
losses = [t for t in all_shorts if t['pnlDollar'] <= 0]

features = ['atr_pct', 'atr_ratio', 'atr_expanding', 'atr_pct_rank20', 'atr_pct_rank50', 
            'atr_change5', 'atr_change10', 'mom20']

print(f"  {'Feature':<20} {'Wins(n={len(wins)})':>15} {'Losses(n={len(losses)})':>15} {'Diff':>10} {'Direction':>12}")
print(f"  {'─'*75}")

for feat in features:
    w_vals = [t[feat] for t in wins if t[feat] is not None]
    l_vals = [t[feat] for t in losses if t[feat] is not None]
    if w_vals and l_vals:
        w_mean = np.mean(w_vals)
        l_mean = np.mean(l_vals)
        diff = w_mean - l_mean
        direction = "WIN higher" if diff > 0 else "LOSS higher"
        print(f"  {feat:<20} {w_mean:>15.4f} {l_mean:>15.4f} {diff:>+10.4f} {direction:>12}")

print()
print("  Distribution detail:")
for feat in ['atr_pct', 'atr_ratio', 'atr_pct_rank50']:
    w_vals = sorted([t[feat] for t in wins if t[feat] is not None])
    l_vals = sorted([t[feat] for t in losses if t[feat] is not None])
    if w_vals and l_vals:
        print(f"\n  {feat}:")
        print(f"    Winners:  min={min(w_vals):.3f}  25%={np.percentile(w_vals,25):.3f}  "
              f"med={np.median(w_vals):.3f}  75%={np.percentile(w_vals,75):.3f}  max={max(w_vals):.3f}")
        print(f"    Losers:   min={min(l_vals):.3f}  25%={np.percentile(l_vals,25):.3f}  "
              f"med={np.median(l_vals):.3f}  75%={np.percentile(l_vals,75):.3f}  max={max(l_vals):.3f}")

# ═══════════════════════════════════════════════════════════════
# PART 2: ATR% threshold filters
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 2: ATR% THRESHOLD FILTERS")
print("="*120)
print("  Only short when ATR% (daily volatility) exceeds a minimum threshold.\n")

results = []
# Baseline: current strategy (SMA200 + TP3R)
results.append(summarize(all_shorts, "A. Baseline (SMA200 + TP3R)"))

for thresh in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, 
            filters=[('atr_pct', 'atr_pct', '>=', thresh)]))
    results.append(summarize(trades, f"B. ATR% >= {thresh}%"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 3: ATR expansion/contraction filters
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 3: ATR EXPANSION/CONTRACTION FILTERS")
print("="*120)
print("  Only short when volatility is expanding (ATR > its own average).\n")

results = [summarize(all_shorts, "A. Baseline (SMA200 + TP3R)")]

# ATR expanding (above its 20-day SMA)
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[('expanding', 'atr_expanding', '>=', 1)]))
results.append(summarize(trades, "C1. ATR expanding (ATR > SMA20 of ATR)"))

# ATR contracting
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[('contracting', 'atr_expanding', '<=', 0)]))
results.append(summarize(trades, "C2. ATR contracting (ATR < SMA20 of ATR)"))

# ATR ratio thresholds (ATR/SMA20_ATR)
for ratio in [1.1, 1.2, 1.3, 1.5]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, filters=[('ratio', 'atr_ratio', '>=', ratio)]))
    results.append(summarize(trades, f"C3. ATR ratio >= {ratio} (strongly expanding)"))

# ATR accelerating (5-day change positive)
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[('accel', 'atr_change5', '>', 0)]))
results.append(summarize(trades, "C4. ATR 5d change > 0 (accelerating vol)"))

# ATR accelerating fast (10-day change > 10%)
for chg in [0.05, 0.10, 0.15, 0.20]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, filters=[('accel10', 'atr_change10', '>=', chg)]))
    results.append(summarize(trades, f"C5. ATR 10d change >= {chg*100:.0f}%"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 4: ATR percentile rank filters
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 4: ATR PERCENTILE RANK FILTERS")
print("="*120)
print("  Only short when ATR is in a high percentile of its recent history.\n")

results = [summarize(all_shorts, "A. Baseline (SMA200 + TP3R)")]

for pct in [0.5, 0.6, 0.7, 0.8, 0.9]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, filters=[('rank20', 'atr_pct_rank20', '>=', pct)]))
    results.append(summarize(trades, f"D1. ATR rank20 >= {pct:.0%} (top {100-pct*100:.0f}%)"))

for pct in [0.5, 0.6, 0.7, 0.8, 0.9]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, filters=[('rank50', 'atr_pct_rank50', '>=', pct)]))
    results.append(summarize(trades, f"D2. ATR rank50 >= {pct:.0%} (top {100-pct*100:.0f}%)"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 5: Combined ATR filters
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 5: COMBINED ATR FILTERS (best from above)")
print("="*120)
print("  Combine ATR% threshold + expansion + rank for maximum selectivity.\n")

results = [summarize(all_shorts, "A. Baseline (SMA200 + TP3R)")]

# Combo: ATR% >= 2.5 + expanding
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('atr_pct', 'atr_pct', '>=', 2.5),
        ('expanding', 'atr_expanding', '>=', 1)]))
results.append(summarize(trades, "E1. ATR% >= 2.5 + expanding"))

# Combo: ATR% >= 3.0 + expanding
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('atr_pct', 'atr_pct', '>=', 3.0),
        ('expanding', 'atr_expanding', '>=', 1)]))
results.append(summarize(trades, "E2. ATR% >= 3.0 + expanding"))

# Combo: ATR% >= 2.5 + rank50 >= 70%
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('atr_pct', 'atr_pct', '>=', 2.5),
        ('rank50', 'atr_pct_rank50', '>=', 0.7)]))
results.append(summarize(trades, "E3. ATR% >= 2.5 + rank50 >= 70%"))

# Combo: ATR% >= 3.0 + rank50 >= 70%
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('atr_pct', 'atr_pct', '>=', 3.0),
        ('rank50', 'atr_pct_rank50', '>=', 0.7)]))
results.append(summarize(trades, "E4. ATR% >= 3.0 + rank50 >= 70%"))

# Combo: expanding + rank50 >= 70%
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('expanding', 'atr_expanding', '>=', 1),
        ('rank50', 'atr_pct_rank50', '>=', 0.7)]))
results.append(summarize(trades, "E5. Expanding + rank50 >= 70%"))

# Combo: expanding + ATR 10d change >= 10%
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('expanding', 'atr_expanding', '>=', 1),
        ('accel10', 'atr_change10', '>=', 0.10)]))
results.append(summarize(trades, "E6. Expanding + ATR 10d change >= 10%"))

# Combo: ATR% >= 2.5 + expanding + neg momentum
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('atr_pct', 'atr_pct', '>=', 2.5),
        ('expanding', 'atr_expanding', '>=', 1),
        ('mom', 'mom20', '<', 0)]))
results.append(summarize(trades, "E7. ATR% >= 2.5 + expanding + neg mom"))

# Combo: ATR% >= 3.0 + expanding + neg momentum
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('atr_pct', 'atr_pct', '>=', 3.0),
        ('expanding', 'atr_expanding', '>=', 1),
        ('mom', 'mom20', '<', 0)]))
results.append(summarize(trades, "E8. ATR% >= 3.0 + expanding + neg mom"))

# Combo: rank50 >= 60% + neg momentum
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('rank50', 'atr_pct_rank50', '>=', 0.6),
        ('mom', 'mom20', '<', 0)]))
results.append(summarize(trades, "E9. Rank50 >= 60% + neg mom"))

# Combo: ATR ratio >= 1.1 + neg momentum
trades = []
for name, df in sorted(stocks.items()):
    trades.extend(backtest_shorts(df, name, filters=[
        ('ratio', 'atr_ratio', '>=', 1.1),
        ('mom', 'mom20', '<', 0)]))
results.append(summarize(trades, "E10. ATR ratio >= 1.1 + neg mom"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 6: Dynamic SL for shorts (wider stop in high vol)
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 6: DYNAMIC STOP LOSS FOR SHORTS")
print("="*120)
print("  Wider SL in high volatility = fewer stop-outs, but smaller position.\n")

results = [summarize(all_shorts, "A. Baseline (SL 1.0 ATR, TP 3R)")]

for sl in [1.25, 1.5, 1.75, 2.0]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, sl_mult=sl, tp_r=3.0))
    results.append(summarize(trades, f"F1. SL {sl}x ATR, TP 3R"))

# Wider SL + lower TP (quicker exit)
for sl, tp in [(1.5, 2.0), (1.5, 2.5), (2.0, 2.0), (2.0, 3.0), (1.25, 2.0)]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, sl_mult=sl, tp_r=tp))
    results.append(summarize(trades, f"F2. SL {sl}x ATR, TP {tp}R"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 7: Dynamic TP for shorts
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 7: DIFFERENT TP LEVELS FOR SHORTS")
print("="*120)
print("  Lower TP = more frequent wins but smaller gains.\n")

results = [summarize(all_shorts, "A. Baseline (TP 3R)")]

for tp in [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, tp_r=tp))
    results.append(summarize(trades, f"G. TP {tp}R"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 8: Best combined filter + TP sweep
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 8: BEST ATR FILTERS + TP SWEEP")
print("="*120)
print("  Take the best ATR filter combos and test with different TP levels.\n")

results = [summarize(all_shorts, "A. Baseline (SMA200 + TP3R)")]

# Test top filters with various TP
best_filters = [
    ("ATR% >= 2.5 + expanding", [('atr_pct', 'atr_pct', '>=', 2.5), ('expanding', 'atr_expanding', '>=', 1)]),
    ("ATR% >= 3.0 + expanding", [('atr_pct', 'atr_pct', '>=', 3.0), ('expanding', 'atr_expanding', '>=', 1)]),
    ("Expanding + rank50>=70%", [('expanding', 'atr_expanding', '>=', 1), ('rank50', 'atr_pct_rank50', '>=', 0.7)]),
    ("ATR ratio>=1.1 + neg mom", [('ratio', 'atr_ratio', '>=', 1.1), ('mom', 'mom20', '<', 0)]),
]

for f_name, f_list in best_filters:
    for tp in [2.0, 2.5, 3.0, 4.0]:
        trades = []
        for name, df in sorted(stocks.items()):
            trades.extend(backtest_shorts(df, name, filters=f_list, tp_r=tp))
        results.append(summarize(trades, f"H. {f_name}, TP {tp}R"))

print_summary_table(results)

# ═══════════════════════════════════════════════════════════════
# PART 9: Per-stock ATR profile
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 9: PER-STOCK ATR ANALYSIS")
print("="*120)
print("  Which stocks have the right ATR profile for shorts?\n")

print(f"  {'Stock':>6} {'AvgATR%':>8} {'#Shorts':>7} {'WR%':>5} {'P&L':>7} {'AvgATR% Win':>12} {'AvgATR% Loss':>13} {'ATR% Diff':>10}")
print(f"  {'─'*75}")

for name in sorted(stocks.keys()):
    df = stocks[name]
    avg_atr_pct = df['atr_pct'].dropna().mean()
    shorts = backtest_shorts(df, name)
    if not shorts: continue
    w = [t for t in shorts if t['pnlDollar'] > 0]
    l = [t for t in shorts if t['pnlDollar'] <= 0]
    wr = len(w)/len(shorts)*100
    pnl = sum(t['pnlDollar'] for t in shorts)
    w_atr = np.mean([t['atr_pct'] for t in w if t['atr_pct']]) if w else 0
    l_atr = np.mean([t['atr_pct'] for t in l if t['atr_pct']]) if l else 0
    diff = w_atr - l_atr
    print(f"  {name:>6} {avg_atr_pct:>8.2f} {len(shorts):>7} {wr:>5.1f} {pnl:>7.0f} {w_atr:>12.3f} {l_atr:>13.3f} {diff:>+10.3f}")

# ═══════════════════════════════════════════════════════════════
# PART 10: Best filter applied per stock
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("PART 10: BEST FILTER APPLIED — PER-STOCK BREAKDOWN")
print("="*120)

# Pick top 3 strategies and show per-stock
top_strategies = [
    ("Baseline (SMA200+TP3R)", None, 3.0),
    ("ATR%>=2.5 + expanding, TP3R", [('atr_pct','atr_pct','>=',2.5),('expanding','atr_expanding','>=',1)], 3.0),
    ("ATR%>=3.0 + expanding, TP3R", [('atr_pct','atr_pct','>=',3.0),('expanding','atr_expanding','>=',1)], 3.0),
    ("Expanding+rank50>=70%, TP3R", [('expanding','atr_expanding','>=',1),('rank50','atr_pct_rank50','>=',0.7)], 3.0),
    ("ATR ratio>=1.1+neg mom, TP3R", [('ratio','atr_ratio','>=',1.1),('mom','mom20','<',0)], 3.0),
]

for s_name, s_filters, s_tp in top_strategies:
    print(f"\n  ── {s_name} ──")
    total_trades = 0; total_pnl = 0; total_wins = 0
    for name in sorted(stocks.keys()):
        df = stocks[name]
        trades = backtest_shorts(df, name, filters=s_filters, tp_r=s_tp)
        if not trades: 
            print(f"    {name:>6}: no shorts")
            continue
        w = len([t for t in trades if t['pnlDollar']>0])
        pnl = sum(t['pnlDollar'] for t in trades)
        wr = w/len(trades)*100
        total_trades += len(trades); total_pnl += pnl; total_wins += w
        print(f"    {name:>6}: {len(trades):>2}t  {w}W/{len(trades)-w}L  WR {wr:>5.1f}%  P&L ${pnl:>+7.0f}")
    total_wr = total_wins/total_trades*100 if total_trades else 0
    print(f"    {'TOTAL':>6}: {total_trades:>2}t  {total_wins}W/{total_trades-total_wins}L  WR {total_wr:>5.1f}%  P&L ${total_pnl:>+7.0f}")

# ═══════════════════════════════════════════════════════════════
# RECOMMENDATION
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*120)
print("RECOMMENDATION")
print("="*120)

# Find best by P&L and best by WR among combos with >= 10 trades
all_results = []
test_configs = [
    ("Baseline", None, 1.0, 3.0),
    ("ATR%>=2.5+expanding, TP3R", [('atr_pct','atr_pct','>=',2.5),('expanding','atr_expanding','>=',1)], 1.0, 3.0),
    ("ATR%>=3.0+expanding, TP3R", [('atr_pct','atr_pct','>=',3.0),('expanding','atr_expanding','>=',1)], 1.0, 3.0),
    ("Expanding+rank50>=70%, TP3R", [('expanding','atr_expanding','>=',1),('rank50','atr_pct_rank50','>=',0.7)], 1.0, 3.0),
    ("ATR%>=2.5+expanding, TP2R", [('atr_pct','atr_pct','>=',2.5),('expanding','atr_expanding','>=',1)], 1.0, 2.0),
    ("ATR%>=3.0+expanding, TP2R", [('atr_pct','atr_pct','>=',3.0),('expanding','atr_expanding','>=',1)], 1.0, 2.0),
    ("ATR ratio>=1.1+neg mom, TP3R", [('ratio','atr_ratio','>=',1.1),('mom','mom20','<',0)], 1.0, 3.0),
    ("ATR ratio>=1.1+neg mom, TP2R", [('ratio','atr_ratio','>=',1.1),('mom','mom20','<',0)], 1.0, 2.0),
    ("Expanding+rank50>=70%, TP2R", [('expanding','atr_expanding','>=',1),('rank50','atr_pct_rank50','>=',0.7)], 1.0, 2.0),
    ("SL1.5+TP2R", None, 1.5, 2.0),
    ("ATR%>=2.5+exp, SL1.5, TP2R", [('atr_pct','atr_pct','>=',2.5),('expanding','atr_expanding','>=',1)], 1.5, 2.0),
    ("ATR%>=3.0+exp, SL1.5, TP3R", [('atr_pct','atr_pct','>=',3.0),('expanding','atr_expanding','>=',1)], 1.5, 3.0),
]

for label, filters, sl, tp in test_configs:
    trades = []
    for name, df in sorted(stocks.items()):
        trades.extend(backtest_shorts(df, name, filters=filters, sl_mult=sl, tp_r=tp))
    s = summarize(trades, label)
    all_results.append(s)

# Filter for minimum trades
viable = [r for r in all_results if r['n'] >= 8]
if viable:
    best_pnl = max(viable, key=lambda r: r['pnl'])
    best_wr = max(viable, key=lambda r: r['wr'])
    best_pf = max(viable, key=lambda r: r['pf'] if r['pf'] != float('inf') else 0)
    
    print(f"\n  BEST by P&L:           {best_pnl['label']}")
    print(f"    {best_pnl['n']}t, {best_pnl['w']}W/{best_pnl['l']}L, WR {best_pnl['wr']}%, P&L ${best_pnl['pnl']:.0f}, PF {best_pnl['pf']}")
    print(f"\n  BEST by Win Rate:      {best_wr['label']}")
    print(f"    {best_wr['n']}t, {best_wr['w']}W/{best_wr['l']}L, WR {best_wr['wr']}%, P&L ${best_wr['pnl']:.0f}, PF {best_wr['pf']}")
    print(f"\n  BEST by Profit Factor: {best_pf['label']}")
    print(f"    {best_pf['n']}t, {best_pf['w']}W/{best_pf['l']}L, WR {best_pf['wr']}%, P&L ${best_pf['pnl']:.0f}, PF {best_pf['pf']}")

print(f"\n  Full comparison of recommendation candidates:")
print_summary_table(all_results)

print("\n" + "="*120)
print("ANALYSIS COMPLETE")
print("="*120)
