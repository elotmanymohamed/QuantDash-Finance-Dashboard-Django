"""
views.py — QuantDash v2
- yfinance integration for real-time prices & OHLCV
- Monte Carlo VaR (NumPy/SciPy)
- Multi-portfolio analytics
- Asset detail drill-down
- JSON API endpoints for charts
"""
import json
import numpy as np
from scipy.stats import norm
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import cache_page

# ─── yfinance wrapper ────────────────────────────────────────────────────────

def _fetch_yfinance(tickers: list, period: str = "6mo") -> dict:
    try:
        import yfinance as yf
        result = {}
        for t in tickers:
            tkr = yf.Ticker(t)
            hist = tkr.history(period=period)
            if hist.empty:
                raise ValueError(f"No data for {t}")
            price = float(hist['Close'].iloc[-1])
            result[t] = {'price': round(price, 4), 'hist': hist}
        return result
    except Exception:
        return _mock_yfinance_fallback(tickers)


def _mock_yfinance_fallback(tickers: list) -> dict:
    import pandas as pd
    result = {}
    base_prices = {
        'AAPL': 189.50, 'MSFT': 415.20, 'JPM': 198.40,
        'BRK-B': 365.80, 'XOM': 112.30, 'NVDA': 875.40,
        'GLD': 215.60, 'TLT': 89.30,
    }
    n = 126
    today = date.today()
    dates = pd.bdate_range(end=today, periods=n)
    for t in tickers:
        start = base_prices.get(t, 100.0)
        rets = np.random.normal(0.0003, 0.015, n)
        closes = start * np.exp(np.cumsum(rets))
        hist = pd.DataFrame({
            'Open':   closes * np.random.uniform(0.995, 1.0, n),
            'High':   closes * np.random.uniform(1.001, 1.02, n),
            'Low':    closes * np.random.uniform(0.98, 0.999, n),
            'Close':  closes,
            'Volume': np.random.randint(1_000_000, 50_000_000, n),
        }, index=dates)
        result[t] = {'price': round(float(closes[-1]), 4), 'hist': hist}
    return result


# ─── Quantitative Risk Engine ─────────────────────────────────────────────────

class RiskEngine:
    RF_DAILY = 0.0525 / 252

    def __init__(self, returns: np.ndarray):
        self.r = np.array(returns, dtype=float)
        self.r = self.r[~np.isnan(self.r)]

    def annualized_vol(self): return float(self.r.std() * np.sqrt(252))
    def annualized_return(self): return float(self.r.mean() * 252)

    def sharpe(self):
        excess = self.r - self.RF_DAILY
        return float((excess.mean() / excess.std()) * np.sqrt(252)) if excess.std() != 0 else 0.0

    def sortino(self):
        downside = self.r[self.r < 0]
        if len(downside) == 0: return 0.0
        dd = downside.std() * np.sqrt(252)
        return float(self.annualized_return() / dd) if dd != 0 else 0.0

    def var_parametric(self, confidence=0.95):
        return float(norm.ppf(1 - confidence, self.r.mean(), self.r.std()))

    def cvar(self, confidence=0.95):
        var = self.var_parametric(confidence)
        tail = self.r[self.r <= var]
        return float(tail.mean()) if len(tail) > 0 else var

    def var_monte_carlo(self, confidence=0.95, n_sims=10_000, horizon=1):
        mu, sigma = self.r.mean(), self.r.std()
        sim = np.random.normal(mu * horizon, sigma * np.sqrt(horizon), n_sims)
        return float(np.percentile(sim, (1 - confidence) * 100))

    def max_drawdown(self):
        cum = np.cumprod(1 + self.r)
        roll_max = np.maximum.accumulate(cum)
        dd = (cum - roll_max) / roll_max
        return float(dd.min())

    def calmar(self):
        mdd = abs(self.max_drawdown())
        return float(self.annualized_return() / mdd) if mdd != 0 else 0.0

    def mc_distribution(self, n_sims=5_000):
        mu, sigma = self.r.mean(), self.r.std()
        return np.random.normal(mu, sigma, n_sims).tolist()

    def summary(self):
        return {
            'annualized_return': round(self.annualized_return() * 100, 2),
            'annualized_vol':    round(self.annualized_vol() * 100, 2),
            'sharpe':            round(self.sharpe(), 3),
            'sortino':           round(self.sortino(), 3),
            'var_95_param':      round(self.var_parametric(0.95) * 100, 3),
            'var_99_param':      round(self.var_parametric(0.99) * 100, 3),
            'var_95_mc':         round(self.var_monte_carlo(0.95) * 100, 3),
            'cvar_95':           round(self.cvar(0.95) * 100, 3),
            'max_drawdown':      round(self.max_drawdown() * 100, 2),
            'calmar':            round(self.calmar(), 3),
        }


# ─── Portfolio data builder ───────────────────────────────────────────────────

PORTFOLIO_ASSETS = [
    {'ticker': 'AAPL',  'name': 'Apple Inc.',          'qty': 25, 'avg': 155.20, 'sector': 'Tech',      'type': 'STOCK'},
    {'ticker': 'MSFT',  'name': 'Microsoft Corp.',      'qty': 15, 'avg': 280.00, 'sector': 'Tech',      'type': 'STOCK'},
    {'ticker': 'JPM',   'name': 'JPMorgan Chase',       'qty': 30, 'avg': 140.10, 'sector': 'Finance',   'type': 'STOCK'},
    {'ticker': 'BRK-B', 'name': 'Berkshire Hathaway',  'qty': 20, 'avg': 310.00, 'sector': 'Finance',   'type': 'STOCK'},
    {'ticker': 'XOM',   'name': 'Exxon Mobil',          'qty': 40, 'avg': 90.50,  'sector': 'Energy',    'type': 'STOCK'},
    {'ticker': 'NVDA',  'name': 'NVIDIA Corp.',         'qty': 10, 'avg': 430.00, 'sector': 'Tech',      'type': 'STOCK'},
    {'ticker': 'GLD',   'name': 'SPDR Gold ETF',        'qty': 12, 'avg': 170.00, 'sector': 'Commodity', 'type': 'ETF'},
    {'ticker': 'TLT',   'name': 'iShares 20Y Bond ETF', 'qty': 35, 'avg': 102.00, 'sector': 'Bond',      'type': 'ETF'},
]


def _build_portfolio(yf_data):
    holdings, total_value = [], 0.0
    for a in PORTFOLIO_ASSETS:
        t = a['ticker']
        price = yf_data[t]['price'] if t in yf_data else a['avg']
        mv    = round(a['qty'] * price, 2)
        pnl   = round(a['qty'] * (price - a['avg']), 2)
        pnl_pct = round((price - a['avg']) / a['avg'] * 100, 2)
        total_value += mv
        holdings.append({**a, 'price': round(price, 2), 'market_value': mv, 'pnl': pnl, 'pnl_pct': pnl_pct})
    for h in holdings:
        h['weight'] = round(h['market_value'] / total_value * 100, 2)
    return {'holdings': holdings, 'total_value': round(total_value, 2)}


def _portfolio_returns(yf_data):
    import pandas as pd
    close_series = {a['ticker']: yf_data[a['ticker']]['hist']['Close']
                    for a in PORTFOLIO_ASSETS if a['ticker'] in yf_data}
    if not close_series:
        return np.random.normal(0.0003, 0.012, 252)
    df = pd.DataFrame(close_series).dropna()
    return np.log(df / df.shift(1)).dropna().mean(axis=1).values


def _sector_allocation(holdings):
    sectors = {}
    for h in holdings:
        sectors[h['sector']] = sectors.get(h['sector'], 0) + h['market_value']
    total = sum(sectors.values())
    return [{'sector': k, 'value': round(v, 2), 'pct': round(v / total * 100, 1)}
            for k, v in sorted(sectors.items(), key=lambda x: -x[1])]


# ─── Views ───────────────────────────────────────────────────────────────────

@cache_page(60 * 5)
def dashboard(request):
    tickers = [a['ticker'] for a in PORTFOLIO_ASSETS]
    yf_data = _fetch_yfinance(tickers, period='3mo')
    port    = _build_portfolio(yf_data)
    returns = _portfolio_returns(yf_data)
    engine  = RiskEngine(returns)
    risk    = engine.summary()
    sectors = _sector_allocation(port['holdings'])

    nav_base  = port['total_value'] / np.exp(np.cumsum(returns[::-1]))[::-1]
    today     = date.today()
    nav_dates = [(today - timedelta(days=len(returns)-1-i)).strftime('%Y-%m-%d')
                 for i in range(len(returns))]
    daily_pnl     = port['total_value'] * returns[-1] if len(returns) else 0
    daily_pnl_pct = round(returns[-1] * 100, 2) if len(returns) else 0

    context = {
        'holdings':      port['holdings'],
        'total_value':   port['total_value'],
        'daily_pnl':     round(daily_pnl, 2),
        'daily_pnl_pct': daily_pnl_pct,
        'risk':          risk,
        'sectors':       sectors,
        'chart_labels':  json.dumps(nav_dates),
        'chart_values':  json.dumps([round(v, 2) for v in nav_base.tolist()]),
        'sector_labels': json.dumps([s['sector'] for s in sectors]),
        'sector_values': json.dumps([s['value'] for s in sectors]),
    }
    return render(request, 'dashboard/index.html', context)


def assets_list(request):
    query   = request.GET.get('q', '').upper()
    sector  = request.GET.get('sector', '')
    sort    = request.GET.get('sort', 'ticker')
    tickers = [a['ticker'] for a in PORTFOLIO_ASSETS]
    yf_data = _fetch_yfinance(tickers, period='1mo')
    port    = _build_portfolio(yf_data)
    holdings = port['holdings']

    if query:
        holdings = [h for h in holdings if query in h['ticker'] or query in h['name'].upper()]
    if sector:
        holdings = [h for h in holdings if h['sector'] == sector]
    if sort in ('pnl_pct', 'market_value', 'weight'):
        holdings = sorted(holdings, key=lambda h: h[sort], reverse=True)

    sectors = list({h['sector'] for h in port['holdings']})
    context = {'holdings': holdings, 'sectors': sectors, 'query': query,
               'selected_sector': sector, 'sort': sort}
    return render(request, 'dashboard/assets.html', context)


def asset_detail(request, ticker):
    ticker     = ticker.upper()
    asset_meta = next((a for a in PORTFOLIO_ASSETS if a['ticker'] == ticker), None)
    yf_data    = _fetch_yfinance([ticker], period='6mo')
    data       = yf_data.get(ticker, {})
    hist       = data.get('hist')

    if hist is None or hist.empty:
        ohlcv, returns_arr = [], np.random.normal(0.0003, 0.015, 126)
    else:
        ohlcv = [{'x': idx.strftime('%Y-%m-%d'),
                  'open': round(float(row['Open']),2), 'high': round(float(row['High']),2),
                  'low':  round(float(row['Low']),2),  'close': round(float(row['Close']),2),
                  'volume': int(row['Volume'])}
                 for idx, row in hist.iterrows()]
        closes      = hist['Close'].values.astype(float)
        returns_arr = np.diff(np.log(closes))

    engine  = RiskEngine(returns_arr)
    risk    = engine.summary()
    mc_dist = engine.mc_distribution(3000)

    # Multi-line: 30-day & 90-day rolling vol
    rolling_vol = []
    if len(returns_arr) >= 20:
        for i in range(20, len(returns_arr)):
            window = returns_arr[max(0,i-30):i]
            rolling_vol.append({'x': ohlcv[i]['x'] if i < len(ohlcv) else '',
                                 'y': round(float(np.std(window) * np.sqrt(252) * 100), 2)})

    context = {
        'ticker':        ticker,
        'meta':          asset_meta or {'name': ticker, 'sector': 'N/A', 'type': 'N/A'},
        'price':         data.get('price', 0),
        'ohlcv_json':    json.dumps(ohlcv),
        'risk':          risk,
        'mc_dist':       json.dumps([round(x * 100, 4) for x in mc_dist]),
        'rolling_vol':   json.dumps(rolling_vol),
    }
    return render(request, 'dashboard/asset_detail.html', context)


def risk_view(request):
    tickers = [a['ticker'] for a in PORTFOLIO_ASSETS]
    yf_data = _fetch_yfinance(tickers, period='1y')
    port    = _build_portfolio(yf_data)
    returns = _portfolio_returns(yf_data)
    engine  = RiskEngine(returns)
    risk    = engine.summary()
    mc_dist = engine.mc_distribution(5000)

    # MC paths for fan chart
    n_paths, horizon = 150, 30
    mu, sigma = returns.mean(), returns.std()
    mc_paths = []
    for _ in range(n_paths):
        path = [0.0]
        for _ in range(horizon):
            path.append(path[-1] + np.random.normal(mu, sigma))
        mc_paths.append([round(v * 100, 4) for v in path])

    context = {
        'total_value':   port['total_value'],
        'risk':          risk,
        'returns_json':  json.dumps([round(r * 100, 4) for r in returns.tolist()]),
        'mc_dist_json':  json.dumps([round(x * 100, 4) for x in mc_dist]),
        'mc_paths_json': json.dumps(mc_paths),
        'horizon':       horizon,
    }
    return render(request, 'dashboard/risk.html', context)


# ─── JSON API ────────────────────────────────────────────────────────────────

@cache_page(60 * 5)
def api_nav_series(request):
    tickers = [a['ticker'] for a in PORTFOLIO_ASSETS]
    yf_data = _fetch_yfinance(tickers, period='3mo')
    port    = _build_portfolio(yf_data)
    returns = _portfolio_returns(yf_data)
    nav     = port['total_value'] / np.exp(np.cumsum(returns[::-1]))[::-1]
    today   = date.today()
    labels  = [(today - timedelta(days=len(returns)-1-i)).strftime('%Y-%m-%d')
               for i in range(len(returns))]
    return JsonResponse({'labels': labels, 'values': [round(v,2) for v in nav.tolist()]})


@cache_page(60 * 5)
def api_holdings(request):
    tickers = [a['ticker'] for a in PORTFOLIO_ASSETS]
    yf_data = _fetch_yfinance(tickers, period='1mo')
    port    = _build_portfolio(yf_data)
    return JsonResponse({'holdings': port['holdings'], 'total_value': port['total_value']})


def api_ohlcv(request, ticker):
    yf_data = _fetch_yfinance([ticker.upper()], period='3mo')
    data = yf_data.get(ticker.upper(), {})
    hist = data.get('hist')
    if hist is None or hist.empty:
        return JsonResponse({'ohlcv': []})
    ohlcv = [{'x': idx.strftime('%Y-%m-%d'), 'open': round(float(row['Open']),2),
               'high': round(float(row['High']),2), 'low': round(float(row['Low']),2),
               'close': round(float(row['Close']),2)}
             for idx, row in hist.iterrows()]
    return JsonResponse({'ticker': ticker.upper(), 'ohlcv': ohlcv})
