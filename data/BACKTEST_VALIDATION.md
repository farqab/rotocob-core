# 📊 RotoBot Core — Empirical Backtest & Model Validation Data

This document and the companion file [`data/benchmark_matches.json`](./benchmark_matches.json) provide **human and LLM-readable empirical data** exported directly from our internal Nesine ApiStats v3 cache.

Researchers, code auditors, and autonomous LLM agents can inspect this data **completely offline with zero network requests**.

---

## 🔬 Benchmark Dataset Overview

The dataset contains 8 verified matches spanning European basketball (BCL), NBA, Japanese B-League, and Korean KBL:

| Match Code | Matchup | League | Nesine Line | Model Proj | Actual Score | Error (pts) | Model Rec | Outcome |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `3225699` | **Derthona - Burgos** | BCL (40m) | 173.5 | **171.6** | **168** (158 reg) | -3.6 pts | `ALT 173.5` | **WON ✅** |
| `3225685` | **Frankfurt - Tenerife** | BCL (40m) | 165.5 | **164.0** | **176** | +12.0 pts | `PAS (Edge < %4.5)` | **PAS (Kupon dışı) 🛡️** |
| `3225758` | **Hapoel - Rigas Zelli** | BCL (40m) | 171.5 | **167.2** | **164** | -3.2 pts | `ALT 171.5` | **WON ✅** (Edge: +12.1%) |
| `3230176` | **New Orleans - Indiana** | NBA (48m) | 238.5 | **231.7** | **243** | +11.3 pts | `ALT 238.5` | **LOST ❌ (Trap analyzed below)** |
| `3230781` | **Memphis - Utah** | NBA (48m) | 242.5 | **233.2** | **226** | -7.2 pts | `ALT 242.5` | **WON ✅** (Edge: +22.5%) |
| `3230014` | **Mobis - LG Sakers** | KBL (40m) | 169.5 | **88.2 - 82.4** | *Live* | - | `MS 1 (1.68)` | *Active Slip* |
| `3230750` | **Sendai - Yokohama** | B-League | 165.5 | **85.7 - 78.3** | *Live* | - | `H2 (+12.5) (1.64)` | *Active Slip* |
| `3245928` | **Guandong - Zhejiang** | CBA | 180.5 | **175.9** | *Live* | - | `ALT 180.5 (1.58)` | *Active Slip* |

---

## 🛡️ Failure Mode Analysis & Engineering Mitigations

### 1. New Orleans vs Indiana (NBA Pre-Season Sample Contamination)
- **What happened:** Market line was 238.5, game finished 243. Model projected 231.7.
- **Root Cause:** Early-season NBA sample ($n < 8$) contained lower-scoring pre-season exhibition matches (bench rotations, 198-213 total points), creating an artificial deflation of empirical scoring averages.
- **Mitigation Implemented:** Added NBA early-season Bayes shrinkage anchoring the prior to league benchmark ($228.5$) when $n < 16$.

### 2. High-Tempo Shootout Trap (Tenerife Q3 Exploding 43 points)
- **What happened:** Frankfurt - Tenerife total reached 176 against line 165.5.
- **Root Cause:** Standard symmetric Gaussian noise cannot capture asymmetric offensive explosions (3-point shooting runs, transition pace).
- **Mitigation Implemented:** Added **Pace Guard** ($Pace \ge 102.0$ in NBA, $\ge 79.0$ in Europe) preventing blind UNDER recommendations on high-tempo shootouts, coupled with an asymmetric positive right-tail exponential skew.

---

## 📈 Metric Definitions

- **Edge (%):** Model win probability minus bookmaker's de-vigged fair market probability:
  $$\text{Edge} = (P_{\text{model}} - P_{\text{fair}}) \times 100\%$$
- **ROI / EV (%):** True expected dollar return per unit wagered against the bookmaker's price:
  $$\text{EV} = (P_{\text{model}} \times \text{Odds} - 1.0) \times 100\%$$

Full raw JSON data can be found in [`data/benchmark_matches.json`](./benchmark_matches.json).
