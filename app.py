from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import glob

app = Flask(__name__)
CORS(app)

# ── Load & cache data ──────────────────────────────────────────────────────────
_df_cache = None

def load_data():
    global _df_cache
    if _df_cache is not None:
        return _df_cache

    try:
        import kagglehub
        path = kagglehub.dataset_download("camnugent/sandp500")
        # find the combined CSV
        csvs = glob.glob(os.path.join(path, "**", "all_stocks_5yr.csv"), recursive=True)
        if not csvs:
            csvs = glob.glob(os.path.join(path, "**", "*.csv"), recursive=True)
            # pick the biggest one (the combined file)
            csvs = sorted(csvs, key=os.path.getsize, reverse=True)
        if not csvs:
            return None
        df = pd.read_csv(csvs[0], parse_dates=["date"])
    except Exception as e:
        print(f"kagglehub failed: {e}")
        return None

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

    _df_cache = df
    return df


def score_stocks(df: pd.DataFrame, budget: float) -> list[dict]:
    results = []

    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date")
        if len(grp) < 60:
            continue

        latest_price = grp["close"].iloc[-1]
        if latest_price > budget or latest_price <= 0:
            continue

        prices = grp["close"].values

        momentum = (prices[-1] - prices[-30]) / prices[-30] if prices[-30] > 0 else 0

        daily_returns = np.diff(prices[-31:]) / prices[-31:-1]
        volatility = float(np.std(daily_returns)) if len(daily_returns) > 0 else 1
        safety = 1 / (1 + volatility * 100)

        ma60 = float(np.mean(prices[-60:]))
        if latest_price >= ma60:
            trend = 1.0
        elif latest_price >= ma60 * 0.98:
            trend = 0.5
        else:
            trend = 0.0

        raw_score = 0.40 * momentum + 0.35 * safety + 0.25 * trend
        shares = int(budget // latest_price)
        spark = prices[-30:].tolist()

        results.append({
            "ticker": ticker,
            "price": round(float(latest_price), 2),
            "shares": shares,
            "momentum_30d": round(float(momentum) * 100, 2),
            "volatility_30d": round(float(volatility) * 100, 4),
            "above_ma60": trend == 1.0,
            "score": round(float(raw_score), 4),
            "sparkline": [round(p, 2) for p in spark],
        })

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
        budget = max(1, min(budget, 10_000))
    except ValueError:
        return jsonify({"error": "Invalid budget"}), 400

    df = load_data()
    if df is None:
        return jsonify({"demo": True, "budget": budget, "stocks": demo_stocks(budget)})

    picks = score_stocks(df, budget)
    return jsonify({"demo": False, "budget": budget, "stocks": picks})


@app.route("/api/health")
def health():
    df = load_data()
    return jsonify({"status": "ok", "dataset_loaded": df is not None})


def demo_stocks(budget: float) -> list[dict]:
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
