from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import numpy as np
import os
import time
import threading
import requests

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("POLYGON_KEY", "")

TICKERS = [
    "F", "T", "BAC", "AMD", "KO", "WMT",
    "AAPL", "NVDA", "MSFT", "TSLA", "JPM", "NKE"
]

_cache = {"data": None, "ts": 0, "ready": False}
_lock = threading.Lock()
_fetching = False


def fetch_ticker(ticker):
    try:
        from datetime import date, timedelta
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=100)).isoformat()
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
        params = {"adjusted": "true", "sort": "asc", "limit": 65, "apiKey": API_KEY}
        print(f"[fetch] requesting {ticker}...", flush=True)
        r = requests.get(url, params=params, timeout=15)
        print(f"[fetch] {ticker} status={r.status_code}", flush=True)
        j = r.json()
        results = j.get("results", [])
        if not results:
            print(f"[cache] no data for {ticker}: {j}", flush=True)
            return None
        return np.array([float(bar["c"]) for bar in results], dtype="float32")
    except Exception as e:
        print(f"[cache] error {ticker}: {e}", flush=True)
        return None


def fetch_all():
    global _fetching
    print("[cache] fetch_all started", flush=True)
    print(f"[cache] API_KEY set: {bool(API_KEY)}", flush=True)
    with _lock:
        if _fetching:
            print("[cache] already fetching, skipping", flush=True)
            return
        _fetching = True

    try:
        data = {}
        for ticker in TICKERS:
            closes = fetch_ticker(ticker)
            if closes is not None and len(closes) >= 20:
                data[ticker] = closes
                print(f"[cache] got {ticker} ({len(closes)} days)", flush=True)
            else:
                print(f"[cache] skipped {ticker}", flush=True)
            time.sleep(13)

        with _lock:
            if data:
                _cache["data"] = data
                _cache["ts"] = time.time()
                _cache["ready"] = True
                print(f"[cache] loaded {len(data)} tickers", flush=True)
            else:
                print("[cache] no data fetched", flush=True)
    except Exception as e:
        print(f"[cache] fetch_all crashed: {e}", flush=True)
    finally:
        with _lock:
            _fetching = False


def maybe_refresh():
    global _fetching
    with _lock:
        age = time.time() - _cache["ts"]
        ready = _cache["ready"]
        already = _fetching
    if not already and (not ready or age > 3600):
        threading.Thread(target=fetch_all, daemon=True).start()


print("[startup] launching background fetch thread", flush=True)
threading.Thread(target=fetch_all, daemon=True).start()


def score_stocks(data: dict, budget: float) -> list:
    results = []
    for ticker, prices in data.items():
        if len(prices) < 20:
            continue
        latest_price = float(prices[-1])
        if latest_price > budget or latest_price <= 0:
            continue

        lookback = min(30, len(prices))
        start_price = float(prices[-lookback])
        momentum = (latest_price - start_price) / start_price if start_price > 0 else 0

        daily_returns = np.diff(prices[-lookback:]) / prices[-lookback:-1]
        volatility = float(np.std(daily_returns)) if len(daily_returns) > 0 else 1
        safety = 1 / (1 + volatility * 100)

        ma_window = min(60, len(prices))
        ma = float(np.mean(prices[-ma_window:]))
        trend = 1.0 if latest_price >= ma else (0.5 if latest_price >= ma * 0.98 else 0.0)

        raw_score = 0.40 * momentum + 0.35 * safety + 0.25 * trend
        shares = int(budget // latest_price)
        spark = [round(float(p), 2) for p in prices[-30:]]

        results.append({
            "ticker": ticker,
            "price": round(latest_price, 2),
            "shares": shares,
            "momentum_30d": round(momentum * 100, 2),
            "volatility_30d": round(volatility * 100, 4),
            "above_ma60": trend == 1.0,
            "score": round(raw_score, 4),
            "sparkline": spark,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


def demo_stocks(budget: float) -> list:
    raw = [
        {"ticker": "F",   "price": 11.50, "momentum_30d":  6.2, "volatility_30d": 1.8, "above_ma60": True,  "score": 0.72},
        {"ticker": "T",   "price": 18.40, "momentum_30d":  3.3, "volatility_30d": 0.9, "above_ma60": True,  "score": 0.65},
        {"ticker": "BAC", "price": 38.00, "momentum_30d":  4.1, "volatility_30d": 1.2, "above_ma60": True,  "score": 0.63},
        {"ticker": "KO",  "price": 62.00, "momentum_30d":  2.8, "volatility_30d": 0.7, "above_ma60": False, "score": 0.61},
    ]
    picks = []
    for s in raw:
        if s["price"] <= budget:
            s["shares"] = int(budget // s["price"])
            s["sparkline"] = [round(s["price"] * (1 + np.random.uniform(-0.02, 0.02)), 2) for _ in range(30)]
            picks.append(s)
    return sorted(picks, key=lambda x: x["score"], reverse=True)


@app.route("/")
def index():
    maybe_refresh()
    return render_template("index.html")


@app.route("/api/recommend")
def recommend():
    try:
        budget = float(request.args.get("budget", 50))
        budget = max(1, min(budget, 10_000))
    except ValueError:
        return jsonify({"error": "Invalid budget"}), 400

    maybe_refresh()

    with _lock:
        ready = _cache["ready"]
        data = _cache["data"]

    if not ready or not data:
        return jsonify({"demo": True, "loading": True, "budget": budget, "stocks": demo_stocks(budget)})

    picks = score_stocks(data, budget)
    if not picks:
        return jsonify({"demo": True, "budget": budget, "stocks": demo_stocks(budget)})

    return jsonify({"demo": False, "budget": budget, "stocks": picks})


@app.route("/api/health")
def health():
    with _lock:
        ready = _cache["ready"]
        ts = _cache["ts"]
        count = len(_cache["data"]) if _cache["data"] else 0
    return jsonify({
        "status": "ok",
        "cache_ready": ready,
        "tickers_loaded": count,
        "cache_age_s": round(time.time() - ts) if ts else None
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
