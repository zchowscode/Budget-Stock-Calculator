from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import json

app = Flask(__name__)
CORS(app)

# ── Load & cache data ──────────────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "stocks.csv")

def load_data():
    """Load the Kaggle S&P 500 dataset. Expects columns: Date, ticker (or Name), close (or Close)."""
    if not os.path.exists(DATA_PATH):
        return None
    df = pd.read_csv(DATA_PATH, parse_dates=["Date"])
    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    rename = {}
    for c in df.columns:
        if c in ("symbol", "name", "ticker"):
            rename[c] = "ticker"
        if c in ("close", "closing price", "adj close", "adj. close"):
            rename[c] = "close"
    df = df.rename(columns=rename)
    df = df.dropna(subset=["ticker", "close", "date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    return df


def score_stocks(df: pd.DataFrame, budget: float) -> list[dict]:
    """
    Score each stock and return top picks within budget.

    Scoring formula (each 0–1, weighted):
      momentum   (40%) – 30-day return
      safety     (35%) – inverse of 30-day volatility
      trend      (25%) – price above 60-day moving average
    """
    results = []

    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date")
        if len(grp) < 60:
            continue

        latest_price = grp["close"].iloc[-1]
        if latest_price > budget or latest_price <= 0:
            continue

        prices = grp["close"].values

        # Momentum: 30-day return
        momentum = (prices[-1] - prices[-30]) / prices[-30] if prices[-30] > 0 else 0

        # Safety: inverse volatility (daily % returns std over 30 days)
        daily_returns = np.diff(prices[-31:]) / prices[-31:-1]
        volatility = float(np.std(daily_returns)) if len(daily_returns) > 0 else 1
        safety = 1 / (1 + volatility * 100)

        # Trend: 1 if above 60-day MA, 0.5 if within 2%, 0 if below
        ma60 = float(np.mean(prices[-60:]))
        if latest_price >= ma60:
            trend = 1.0
        elif latest_price >= ma60 * 0.98:
            trend = 0.5
        else:
            trend = 0.0

        raw_score = 0.40 * momentum + 0.35 * safety + 0.25 * trend

        # Shares you can buy
        shares = int(budget // latest_price)

        # 30-day sparkline (last 30 closes, normalised 0-100 for the chart)
        spark = prices[-30:].tolist()

        results.append({
            "ticker": ticker,
            "price": round(float(latest_price), 2),
            "shares": shares,
            "momentum_30d": round(float(momentum) * 100, 2),   # as %
            "volatility_30d": round(float(volatility) * 100, 4),
            "above_ma60": trend == 1.0,
            "score": round(float(raw_score), 4),
            "sparkline": [round(p, 2) for p in spark],
        })

    # Sort descending by score, return top 10
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recommend")
def recommend():
    try:
        budget = float(request.args.get("budget", 50))
        budget = max(1, min(budget, 10_000))   # clamp
    except ValueError:
        return jsonify({"error": "Invalid budget"}), 400

    df = load_data()
    if df is None:
        # Return demo data so the UI works before the dataset is added
        return jsonify({"demo": True, "budget": budget, "stocks": demo_stocks(budget)})

    picks = score_stocks(df, budget)
    return jsonify({"demo": False, "budget": budget, "stocks": picks})


@app.route("/api/health")
def health():
    df = load_data()
    return jsonify({"status": "ok", "dataset_loaded": df is not None})


def demo_stocks(budget: float) -> list[dict]:
    """Fake data shown before the Kaggle CSV is added."""
    raw = [
        {"ticker": "F",    "price": 11.50, "momentum_30d":  6.2,  "volatility_30d": 1.8,  "above_ma60": True,  "score": 0.72},
        {"ticker": "SOFI", "price": 8.90,  "momentum_30d":  9.1,  "volatility_30d": 2.4,  "above_ma60": True,  "score": 0.68},
        {"ticker": "NOK",  "price": 4.20,  "momentum_30d":  2.8,  "volatility_30d": 1.1,  "above_ma60": False, "score": 0.61},
        {"ticker": "PLUG", "price": 3.70,  "momentum_30d": -1.4,  "volatility_30d": 3.2,  "above_ma60": False, "score": 0.52},
        {"ticker": "T",    "price": 18.40, "momentum_30d":  3.3,  "volatility_30d": 0.9,  "above_ma60": True,  "score": 0.65},
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
