# 🏀 RotoBot Core

> **High-Performance Empirical Basketball Monte Carlo Simulation & Expected Value Engine**  
> Reverse-engineered from RotoBot architecture with 100% official Nesine ApiStats v3 integration, zero-hallucination empirical ratings, and multi-layered risk guards.

---

## 🌟 Key Features

1. **100% Empirical Data Pipeline (Nesine ApiStats v3):**
   - Automatically parses official regular-time quarter scores (Q1..Q4, `TY: 201..204`).
   - Strictly strips Overtime (OT) inflation to preserve true 40-minute and 48-minute scoring baselines.
   - Applies Home/Away Venue Splits (35%), Same-League Tournament Form (25%), and Exponential Recency Decay ($\exp(-0.14 \times i)$).

2. **SIMD-Vectorized Monte Carlo Simulation Engine:**
   - Runs 5,000 to 100,000 deterministic simulations in **under 10 milliseconds** using C-level NumPy SIMD vectorization.
   - Correlated game tempo shocks coupled with independent team shooting variance.
   - Seeds deterministic RNG by match code and market line for 100% reproducible outcomes.

3. **Multi-Layer Safeguards & Risk Guards:**
   - 🛡️ **Pace Guard:** Automatically identifies high-tempo shootouts ($Pace \ge 102.0$) and suppresses blind UNDER bets.
   - 📈 **Right-Tail Positive Skew:** Models offensive explosion dynamics (3-point streaks, late-game intentional foul parades).
   - 🔬 **Early-Season Bayes Shrinkage:** Calibrates small-sample NBA games against regular-season benchmarks (228.5) to eliminate pre-season exhibition contamination.
   - 💎 **Diamond Filter:** Highlights picks with $\ge 58\%$ model probability and $\ge +7.5\%$ de-vigged market expected value (EV).

4. **Full-Stack Architecture:**
   - **Backend:** FastAPI with parallel CDN bulletin scraping and SQLite local caching.
   - **Frontend:** Responsive, modern Tailwind CSS dashboard with live bulletin odds, probability distributions, and MBS tags.

---

## 🚀 Quickstart

### 1. Requirements
- Python 3.10+
- Dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run Server
```bash
python run.py
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 📁 Project Structure

```
rotobot-core/
├── backend/
│   ├── app.py                     # FastAPI application & API endpoints
│   ├── nesine_basket_scraper.py   # Live Nesine bulletin parser & category detector
│   ├── simulation_engine.py       # Monte Carlo engine, Pace Guard & Diamond Filter
│   ├── team_ratings.py            # Nesine ApiStats v3 empirical parser & cache
│   └── database.py                # SQLite persistence
├── frontend/
│   └── index.html                 # Tailwind CSS live analytics dashboard
├── requirements.txt
├── run.py                         # Startup launcher (Uvicorn)
└── README.md
```

---

## ⚖️ License
MIT License. For research and quantitative sports modeling purposes only.
