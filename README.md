# 📈 Budget Stock Calculator

A web app that recommends the best stocks to buy based on your budget. Enter how much money you have to invest and get real-time stock picks scored by momentum, safety, and trend.

**Live Demo:** https://budget-stock-calculator.onrender.com

---

## What It Does

- Enter a budget (e.g. $50, $500, $5000)
- The app fetches real stock price data from the Polygon.io API
- Each stock is scored using a custom algorithm:
  - **40% Momentum** — 30-day price change
  - **35% Safety** — inverse of volatility
  - **25% Trend** — price vs 60-day moving average
- Returns the top picks you can actually afford, with how many shares you can buy

---

## Tech Stack

- **Backend:** Python, Flask, Gunicorn
- **Data:** Polygon.io API (real-time stock prices)
- **Frontend:** Vanilla HTML/CSS/JS, Chart.js
- **Deployment:** Render (free tier), GitHub

---

## How to Run Locally

1. Clone the repo:
```bash
git clone https://github.com/zchowscode/Budget-Stock-Calculator
cd Budget-Stock-Calculator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your Polygon.io API key:
```bash
export POLYGON_KEY=your_api_key_here
```

4. Run the app:
```bash
python app.py
```

5. Open http://localhost:5000

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main web interface |
| `GET /api/recommend?budget=50` | Get stock recommendations for a given budget |
| `GET /api/health` | Check if live data is loaded |

---

## Project Structure

```
├── app.py              # Flask backend + scoring logic
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config
└── templates/
    └── index.html      # Frontend UI
```

---

## Scoring Algorithm

```
score = 0.40 × momentum + 0.35 × safety + 0.25 × trend

momentum  = (current_price - price_30d_ago) / price_30d_ago
safety    = 1 / (1 + volatility × 100)
trend     = 1.0 if price ≥ MA60, else 0.5 if price ≥ MA60×0.98, else 0.0
```

---

## Disclaimer

⚠️ This is an educational project for ISYE class purposes only. Not financial advice. Do not make real investment decisions based on this app.
