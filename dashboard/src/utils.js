/** Shared computation utilities for the dashboard */

export function computeMetrics(trades) {
  if (!trades.length) return null
  const wins = trades.filter(t => t.pnlDollar > 0)
  const losses = trades.filter(t => t.pnlDollar <= 0)
  const totalPnl = trades.reduce((s, t) => s + t.pnlDollar, 0)
  const totalProfit = wins.reduce((s, t) => s + t.pnlDollar, 0)
  const totalLoss = losses.reduce((s, t) => s + t.pnlDollar, 0)
  const winRate = (wins.length / trades.length) * 100
  const avgWin = wins.length ? totalProfit / wins.length : 0
  const avgLoss = losses.length ? totalLoss / losses.length : 0
  const profitFactor = totalLoss !== 0 ? Math.abs(totalProfit / totalLoss) : Infinity
  const avgR = trades.reduce((s, t) => s + t.pnlR, 0) / trades.length
  const avgDuration = trades.reduce((s, t) => s + t.durationDays, 0) / trades.length
  const avgWinDuration = wins.length ? wins.reduce((s, t) => s + t.durationDays, 0) / wins.length : 0
  const avgLossDuration = losses.length ? losses.reduce((s, t) => s + t.durationDays, 0) / losses.length : 0
  const maxWin = wins.length ? Math.max(...wins.map(t => t.pnlDollar)) : 0
  const maxLoss = losses.length ? Math.min(...losses.map(t => t.pnlDollar)) : 0

  return {
    totalTrades: trades.length,
    wins: wins.length,
    losses: losses.length,
    winRate: +winRate.toFixed(1),
    totalPnl: +totalPnl.toFixed(2),
    totalProfit: +totalProfit.toFixed(2),
    totalLoss: +totalLoss.toFixed(2),
    avgWin: +avgWin.toFixed(2),
    avgLoss: +avgLoss.toFixed(2),
    profitFactor: profitFactor === Infinity ? '∞' : +profitFactor.toFixed(2),
    avgR: +avgR.toFixed(2),
    avgDuration: +avgDuration.toFixed(1),
    avgWinDuration: +avgWinDuration.toFixed(1),
    avgLossDuration: +avgLossDuration.toFixed(1),
    maxWin: +maxWin.toFixed(2),
    maxLoss: +maxLoss.toFixed(2),
  }
}

export function buildEquityCurve(trades) {
  let equity = 0
  return trades.map(t => {
    equity += t.pnlDollar
    return { date: t.exitDate, equity: +equity.toFixed(2), pnl: t.pnlDollar }
  })
}

export function buildDrawdownSeries(trades) {
  let equity = 0, peak = 0
  const series = []
  const phases = []
  let inDD = false, ddStart = null, ddStartEquity = 0

  trades.forEach(t => {
    equity += t.pnlDollar
    if (equity > peak) peak = equity
    const dd = peak - equity
    const ddPct = peak > 0 ? (dd / peak) * 100 : 0
    series.push({ date: t.exitDate, drawdown: +dd.toFixed(2), drawdownPct: +ddPct.toFixed(1) })

    if (dd > 0 && !inDD) {
      inDD = true; ddStart = t.exitDate; ddStartEquity = peak
    } else if (dd === 0 && inDD) {
      phases.push({ start: ddStart, end: t.exitDate, depth: +(ddStartEquity - Math.min(...series.filter(s => s.date >= ddStart && s.date <= t.exitDate).map(s => ddStartEquity - s.drawdown))).toFixed(2), peakEquity: +ddStartEquity.toFixed(2) })
      inDD = false
    }
  })

  // If still in drawdown
  if (inDD && trades.length) {
    const lastDate = trades[trades.length - 1].exitDate
    const minEquity = Math.min(...series.filter(s => s.date >= ddStart).map(s => ddStartEquity - s.drawdown))
    phases.push({ start: ddStart, end: lastDate + ' (ongoing)', depth: +(ddStartEquity - minEquity).toFixed(2), peakEquity: +ddStartEquity.toFixed(2) })
  }

  // Max drawdown
  const maxDD = series.length ? Math.max(...series.map(s => s.drawdown)) : 0
  const maxDDPct = series.length ? Math.max(...series.map(s => s.drawdownPct)) : 0

  return { series, phases, maxDD: +maxDD.toFixed(2), maxDDPct: +maxDDPct.toFixed(1) }
}

export function buildConsecutive(trades) {
  let maxConsecWin = 0, maxConsecLoss = 0, cw = 0, cl = 0
  trades.forEach(t => {
    if (t.pnlDollar > 0) { cw++; cl = 0 }
    else { cl++; cw = 0 }
    maxConsecWin = Math.max(maxConsecWin, cw)
    maxConsecLoss = Math.max(maxConsecLoss, cl)
  })
  return { maxConsecWin, maxConsecLoss }
}

export function buildMonthlyReturns(trades) {
  const monthly = {}
  trades.forEach(t => {
    const m = t.exitDate.slice(0, 7) // YYYY-MM
    monthly[m] = (monthly[m] || 0) + t.pnlDollar
  })
  return Object.entries(monthly).sort().map(([month, pnl]) => ({ month, pnl: +pnl.toFixed(2) }))
}

export function buildProfitWaveData(trades) {
  // For winning trades: how long were they held and how much profit
  return trades
    .filter(t => t.pnlDollar > 0)
    .map(t => ({
      date: t.exitDate,
      stock: t.stock,
      duration: t.durationDays,
      profit: t.pnlDollar,
      pnlR: t.pnlR,
    }))
    .sort((a, b) => a.date.localeCompare(b.date))
}

export function fmt$(v) {
  const sign = v < 0 ? '-' : v > 0 ? '+' : ''
  return sign + '$' + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}
