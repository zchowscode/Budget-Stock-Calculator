from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
import os

app = Flask(__name__)
CORS(app)

# ── S&P 500 tickers to scan ───────────────────────────────────────────────────
TICKERS = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","JNJ",
    "V","UNH","XOM","PG","MA","HD","CVX","MRK","ABBV","PEP","KO","AVGO",
    "COST","MCD","WMT","BAC","LLY","TMO","ACN","CSCO","ABT","DHR","TXN",
    "NEE","PM","RTX","UPS","AMGN","QCOM","HON","LOW","MS","SPGI","GS",
    "CAT","BLK","INTU","ISRG","AXP","SYK","GILD","ADI","MDLZ","VRTX",
    "REGN","ZTS","MMC","CB","SO","DUK","CI","ELV","CVS","WBA","T","VZ",
    "CMCSA","NFLX","INTC","AMD","MU","F","GM","GE","BA","LMT","NOC",
    "WFC","USB","PNC","TFC","COF","AIG","MET","PRU","AFL","ALL",
    "NKE","SBUX","TGT","DIS","PYPL","SQ","UBER","LYFT","SNAP","PINS",
    "SOFI","NOK","PLTR","RIVN","LCID","AAL","DAL","UAL","CCL","RCL"
]

_cache = {}

def load_data(budget: float):
    """Fetch 3 months of daily closes for all tickers via yfinance."""
    global _cache
    import time
    now = time.time()
    # Cache for 1 hour
    if _cache.get("ts") and now - _cache["ts"] < 3600 and _cache.get("df") is not None:
        return _cache["df"]

    try:
        raw = yf.download(
            TICKERS,
            period="3mo",
            interval="1d",
            progress=False,
            threads=True
        )
        # yfinance returns MultiIndex columns (field, ticker)
        closes = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw["Adj Close"]
        _cache["df"] = closes
        _cache["ts"] = now
        return closes
    except Exception as e:
        print(f"yfinance error: {e}")
        return None


def score_stocks(closes: pd.DataFrame, budget: float) -> list[dict]:
    results = []

    for ticker in closes.columns:
        series = closes[ticker].dropna()
        if len(series) < 60:
            continue

        latest_price = float(series.iloc[-1])
        if latest_price > budget or latest_price <= 0:
            continue

        prices = series.values

        # Momentum: 30-day return
        momentum = (prices[-1] - prices[-30]) / prices[-30] if prices[-30] > 0 else 0

        # Safety: inverse volatility
        daily_returns = np.diff(prices[-31:]) / prices[-31:-1]
        volatility = float(np.std(daily_returns)) if len(daily_returns) > 0 else 1
        safety = 1 / (1 + volatility * 100)

        # Trend: vs 60-day MA
        ma60 = float(np.mean(prices[-60:]))
        if latest_price >= ma60:
            trend = 1.0
        elif latest_price >= ma60 * 0.98:
            trend = 0.5
        else:
            trend = 0.0

        raw_score = 0.40 * momentum + 0.35 * safety + 0.25 * trend
        shares = int(budget // latest_price)
        spark = [round(p, 2) for p in prices[-30:].tolist()]

        results.append({
            "ticker": ticker,
            "price": round(latest_price, 2),
            "shares": shares,
            "momentum_30d": round(float(momentum) * 100, 2),
            "volatility_30d": round(float(volatility) * 100, 4),
            "above_ma60": trend == 1.0,
            "score": round(float(raw_score), 4),
            "sparkline": spark,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recommend")
def recommend():
    try:
        budget = float(request.args.get("budget", 50))
        budget = max(1, min(budget, 10_000))
    except ValueError:
        return jsonify({"error": "Invalid budget"}), 400

    closes = load_data(budget)
    if closes is None:
        return jsonify({"demo": True, "budget": budget, "stocks": demo_stocks(budget)})

    picks = score_stocks(closes, budget)
    if not picks:
        return jsonify({"demo": True, "budget": budget, "stocks": demo_stocks(budget)})

    return jsonify({"demo": False, "budget": budget, "stocks": picks})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "data_source": "yfinance"})


def demo_stocks(budget: float) -> list[dict]:
    raw = [
        {"ticker": "F",    "price": 11.50, "momentum_30d":  6.2, "volatility_30d": 1.8, "above_ma60": True,  "score": 0.72},
        {"ticker": "SOFI", "price": 8.90,  "momentum_30d":  9.1, "volatility_30d": 2.4, "above_ma60": True,  "score": 0.68},
        {"ticker": "NOK",  "price": 4.20,  "momentum_30d":  2.8, "volatility_30d": 1.1, "above_ma60": False, "score": 0.61},
        {"ticker": "T",    "price": 18.40, "momentum_30d":  3.3, "volatility_30d": 0.9, "above_ma60": True,  "score": 0.65},
    ]
    picks = []
    for s in raw:
        if s["price"] <= budget:
            s["shares"] = int(budget // s["price"])
            s["sparkline"] = [s["price"] * (1 + np.random.uniform(-0.02, 0.02)) for _ in range(30)]
            picks.append(s)
    return sorted(picks, key=lambda x: x["score"], reverse=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
