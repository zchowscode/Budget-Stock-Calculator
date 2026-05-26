# 📈 Budget Stock Calculator

A web app that recommends the best stocks to buy based on your budget.
Enter how much you have to invest and get scored stock picks instantly.

**Live Demo:** https://budget-stock-calculator.onrender.com

---

## What It Does

- Enter a budget (e.g. $50, $500, $5000)
- The app scores 12 real stocks using a custom algorithm:
  - **40% Momentum** — 30-day price change
  - **35% Safety** — inverse of price volatility
  - **25% Trend** — price vs 60-day moving average
- Returns the top picks you can actually afford, with share count and sparkline chart

---

## Stocks Covered

F · T · BAC · AMD · KO · WMT · AAPL · NVDA · MSFT · TSLA · JPM · NKE

---

## Tech Stack

- **Backend:** Python, Flask, Gunicorn
- **Data:** Yahoo Finance historical prices (hardcoded, May 2025 – May 2026)
- **Frontend:** Vanilla HTML/CSS/JS, Chart.js
- **Deployment:** Render, GitHub

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

3. Run the app:
```bash
python app.py
```

4. Open http://localhost:5000

No API key needed — data is built in.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main web interface |
| `GET /api/recommend?budget=50` | Stock picks for a given budget |
| `GET /api/health` | App status and data info |

---

## Project Structure
├── app.py              # Flask backend + scoring logic
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config
└── templates/
└── index.html      # Frontend UI

---

## Scoring Algorithm
score = 0.40 × momentum + 0.35 × safety + 0.25 × trend
momentum  = (current_price - price_30d_ago) / price_30d_ago
safety    = 1 / (1 + volatility × 100)
trend     = 1.0 if price ≥ MA60
0.5 if price ≥ MA60 × 0.98
0.0 otherwise

---

## Disclaimer

⚠️ Educational project built for ISYE coursework. Not financial advice.
Do not make real investment decisions based on this app.
