# RotoBot AI — Complete REA Reverse-Engineered Technical Specification

> **Source Analysis:** Reverse-Engineered via Antigravity REA MCP & Static JavaScript AST Extraction  
> **Target:** `https://rotobot.ai`, `https://app.rotobot.ai`, Supabase `ardonyjjtwljfzszhcko`  
> **Timestamp:** 2026-10-21  

---

## 1. Product Architecture & Navigation Hierarchy

RotoBot operates as a dual-mode application with a single unified Next.js App Router front-end (`/app/*`):

### Mode A: Betting Intelligence (`mode: "betting"`)
1. `/app/chat` — **AI Sports Copilot**: Conversational interface streaming agent responses via Server-Sent Events (SSE).
2. `/app/insights` — **Insights**: Automated daily value bets, market volume anomalies, and model best-picks.
3. `/app/prop-analyzer` — **Prop Analyzer**: Single-player distribution analysis, over/under hit rates across last 5/10/20 games.
4. `/app/rankings` — **Prop Explorer**: Full sortable data grid of player props ranked by Expected Value (+EV) and Model Win Probability.
5. `/app/games` — **Games**: Game matchup simulation previews, projected scores, pace, spread, total lines.
6. `/app/sharp` — **Sharp Board**: Tracking smart money flow, reverse line movement, and syndicate steam.
7. `/app/highlights` — **Highlights**: Video & statistical game recaps.
8. `/app/parlay` — **Parlay Optimizer**: Multi-leg correlation matrix builder (same-game parlay joint probability calculations).
9. `/app/players` — **Player Directory**: In-depth player roster, minutes projections, injury status.
10. `/stats/qb/passing-yards` — **Stat Explorer**: Historical statistical trends and splits.

### Mode B: Fantasy Intelligence (`mode: "fantasy"`)
1. `/app/fantasy` — **League Hub**: Synchronizes rosters with Sleeper, ESPN, and Yahoo Fantasy.
2. `/app/fantasy/trade-finder` — **Trade Finder**: Identifies win-win trade proposals matching roster needs.
3. `/app/fantasy/trade` — **Trade Analyzer**: Value discrepancy evaluator between traded assets.
4. `/app/fantasy/sit-start` — **Sit / Start Analyzer**: Monte Carlo projected ceiling/floor comparison.
5. `/app/fantasy/matchup-insights` — **Matchup Insights**: Head-to-head weekly opponent projections.
6. `/app/fantasy/news` — **News & Injuries**: Live beat writer reports and depth chart changes.
7. `/app/draft` — **Draft Assistant**: Real-time pick recommendations during fantasy drafts.

---

## 2. API Contracts & Protocols

### Conversational Copilot & Simulation Stream (`/api/chat/send`)
- **Protocol:** Server-Sent Events (SSE) `Content-Type: text/event-stream`
- **Request Body:**
```json
{
  "thread_id": "uuid-v4",
  "content": "Simulate OKC vs SAS tonight and show SGA points prop",
  "mode": "v3",
  "quick_mode": false,
  "edit": false,
  "league_uid": null,
  "provider_type": null,
  "roster_source": null
}
```
- **Stream Event Handlers:**
  - `event: message` -> Streamed tokens / markdown content
  - `event: tool_call` -> Triggered simulation / prop lookup
  - `event: checkpoint` -> LangGraph/Agent state checkpoint (`checkpoint_id`)
  - `event: done` -> Finalized response payload

### Feedback & Checkpoints (`/api/chat/like`)
- **Method:** `PUT`
- **Payload:** `{"checkpoint_id": "...", "thread_id": "...", "liked": true|false}`

### Supabase Infrastructure
- **Project Ref:** `ardonyjjtwljfzszhcko`
- **Host:** `https://supa.rotobot.ai`
- **Auth:** Supabase Auth (`/auth/v1/`), Edge Functions (`/functions/v1/stripe-billing-*`)

---

## 3. Our Enhancement Architecture (RotoBot-Core Local)

We replace external subscription dependencies with a high-performance local stack:
1. **Simulation Engine:** 5,000 to 50,000 possession-level Markov simulations ([`nba_possession_sim.py`](file:///C:/Users/farqa/.gemini/antigravity/scratch/nba_possession_sim.py)) with local GTX 1660 Ti acceleration.
2. **Bookmaker Arbitrage Engine:** Live odds ingest from **Nesine / İddaa + Pinnacle**, calculating true Kelly Criterion +EV edge.
3. **Zero-Cost Free API Data Feed:** Official NBA API (`stats.nba.com`) ingestion for team lineups, USG%, TS%, and pace.
4. **Standalone Web Dashboard:** Zero-dependency FastAPI + Modern responsive dark-mode UI with live charts and real-time copilot.
