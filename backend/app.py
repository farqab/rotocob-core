import os
import json
import uuid
import asyncio
import time
import threading
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .nesine_basket_scraper import fetch_live_nesine_basketball
from .simulation_engine import simulate_basketball_match
from .team_ratings import fetch_summaries_batch

app = FastAPI(title="RotoBot Core — Nesine Canlı Basketbol & Monte Carlo Motoru", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# In-memory cache for live Nesine bulletin
CACHE_DATA = {
    "last_fetched": 0,
    "matches": [],
    "simulations": {},
    "ev_picks": []
}

_REFRESH_LOCK = threading.Lock()

def get_or_refresh_nesine_bulletin(force=False):
    now = time.time()
    # Cache for 5 minutes unless forced
    if not force and CACHE_DATA["matches"] and (now - CACHE_DATA["last_fetched"] < 300):
        return CACHE_DATA["matches"], CACHE_DATA["ev_picks"]
    # Only one refresh at a time; later callers reuse the cache the first one fills
    with _REFRESH_LOCK:
        return _refresh_bulletin_locked(force)

def _refresh_bulletin_locked(force=False):
    now = time.time()
    if not force and CACHE_DATA["matches"] and (now - CACHE_DATA["last_fetched"] < 300):
        return CACHE_DATA["matches"], CACHE_DATA["ev_picks"]

    print("[*] Canlı Nesine Basketbol Bülteni ve Resmi İstatistik Veritabanı (ApiStats v3) taranıyor...")
    matches = fetch_live_nesine_basketball()
    codes = [int(m["code"]) for m in matches if m.get("code")]
    summaries = fetch_summaries_batch(codes)
    
    simulations = {}
    ev_picks = []

    for m in matches:
        code_int = int(m.get("code", 0))
        sim = simulate_basketball_match(m, summary_d=summaries.get(code_int), num_simulations=5000, fetch_missing=False)
        simulations[m["id"]] = sim
        m["simulation"] = sim

        grade = sim.get("coupon_grade", "PASS")
        if sim.get("verified") and grade in ("DIAMOND", "VALUE") and sim.get("rec_side") in ("OVER", "UNDER"):
            meta = sim.get("empirical_meta") or {}
            h_rec = ", ".join(x["score"] for x in meta.get("home_recent", []))
            a_rec = ", ".join(x["score"] for x in meta.get("away_recent", []))
            ev_picks.append({
                "match_id": m["id"],
                "code": m["code"],
                "game_date": m["game_date"],
                "league": m["league"],
                "matchup": f"{m['home_team']} - {m['away_team']}",
                "market": f"Toplam {sim['nesine_line']}",
                "recommendation": sim["recommendation"],
                "rec_side": sim["rec_side"],
                "coupon_grade": grade,
                "is_diamond": (grade == "DIAMOND"),
                "odds": sim["odds_over"] if sim["rec_side"] == "OVER" else sim["odds_under"],
                "model_proj": sim["projected_total"],
                "raw_emp_total": sim.get("raw_empirical_total"),
                "model_prob": f"{int((sim['prob_over'] if sim['rec_side'] == 'OVER' else sim['prob_under']) * 100)}%",
                "ev_pct": sim["best_ev"],
                "edge_pct": sim.get("best_edge", sim["best_ev"]),
                "roi_pct": sim.get("best_ev_roi", 0.0),
                "mbs": m["mbs"],
                "mbs_warning": m["mbs_warning"],
                "home_avg": f"{meta.get('home_pf', '-')}/{meta.get('home_pa', '-')}",
                "away_avg": f"{meta.get('away_pf', '-')}/{meta.get('away_pa', '-')}",
                "recent_summary": f"Ev Son 3: [{h_rec}] | Dep Son 3: [{a_rec}]"
            })

    # Sort EV picks: First DIAMOND picks, then by highest EV
    ev_picks.sort(key=lambda x: (x["is_diamond"], x["ev_pct"]), reverse=True)

    CACHE_DATA["last_fetched"] = now
    CACHE_DATA["matches"] = matches
    CACHE_DATA["simulations"] = simulations
    CACHE_DATA["ev_picks"] = ev_picks
    print(f"[+] {len(matches)} maç simüle edildi. {len(ev_picks)} adet +EV değerli bahis tespit edildi!")
    return matches, ev_picks

# -----------------
# API Endpoints
# -----------------

@app.get("/api/nesine/bulletin")
def get_nesine_bulletin(refresh: bool = False):
    matches, ev_picks = get_or_refresh_nesine_bulletin(force=refresh)
    return {
        "status": "success",
        "total_matches": len(matches),
        "total_ev_picks": len(ev_picks),
        "matches": matches,
        "ev_picks": ev_picks
    }

@app.get("/api/props")
def get_props_compat():
    """Compatibility endpoint for the Prop Explorer table, populated with real Nesine +EV picks."""
    _, ev_picks = get_or_refresh_nesine_bulletin()
    return ev_picks

@app.get("/api/games")
def get_games_compat():
    matches, _ = get_or_refresh_nesine_bulletin()
    return matches

@app.post("/api/simulate/{match_id}")
def simulate_on_demand(match_id: str):
    matches, _ = get_or_refresh_nesine_bulletin()
    target = next((m for m in matches if m["id"] == match_id), None)
    if not target:
        return JSONResponse({"error": "Maç bulunamadı"}, status_code=404)
    sim = simulate_basketball_match(target, num_simulations=5000)
    return sim

# -----------------
# Türkçe SSE Chat Copilot
# -----------------

@app.post("/api/chat/send")
async def send_chat_message(req: Request):
    body = await req.json()
    content = body.get("content", "")
    thread_id = body.get("thread_id", str(uuid.uuid4()))

    matches, ev_picks = await asyncio.to_thread(get_or_refresh_nesine_bulletin)

    async def sse_event_stream():
        yield f"event: checkpoint\ndata: {json.dumps({'checkpoint_id': f'chk_{uuid.uuid4().hex[:8]}'})}\n\n"
        await asyncio.sleep(0.05)

        yield f"event: message\ndata: {json.dumps({'chunk': '🏀 Nesine bülteni ve 5.000 pozisyon simülasyonları taranıyor...\\n\\n'})}\n\n"
        await asyncio.sleep(0.1)

        lower_q = content.lower()

        # Check for specific team
        # Ignore short words ("a", "ve", "vs") that would match almost every team name
        query_words = [w for w in lower_q.split() if len(w) >= 3]
        found_matches = [m for m in matches if any(w in m["home_team"].lower() or w in m["away_team"].lower() for w in query_words)]

        if found_matches and not found_matches[0]["simulation"].get("verified"):
            t = found_matches[0]
            msg = (
                f"📊 **{t['home_team']} vs {t['away_team']} ({t['league']} | Kod: {t['code']})**\n\n"
                f"Bu maç için yeterli resmi geçmiş veri yok; tahmin üretilmedi.\n"
            )
            yield f"event: message\ndata: {json.dumps({'chunk': msg})}\n\n"

        elif found_matches:
            target = found_matches[0]
            sim = target["simulation"]
            meta = sim.get("empirical_meta") or {}
            h_rec = ", ".join(f"{x['score']} ({x['opp']})" for x in meta.get("home_recent", [])) or "Veri Yok"
            a_rec = ", ".join(f"{x['score']} ({x['opp']})" for x in meta.get("away_recent", [])) or "Veri Yok"
            msg = (
                f"📊 **{target['home_team']} vs {target['away_team']} ({target['league']} | Kod: {target['code']})**\n\n"
                f"- **Tarih/Saat:** {target['game_date']} | **Kural:** {target['mbs_warning']}\n"
                f"- **Nesine Açılan Barem:** {target['line_total']} Sayı (Üst: {target['odds_total_over']} | Alt: {target['odds_total_under']})\n\n"
                f"📈 **Resmi Nesine İstatistik Geçmişi (Normal Süre 4 Periyot, Uzatmalar Hariç):**\n"
                f"- **{target['home_team']}** ({meta.get('home_n', 0)} Maç): Ort. Atılan **{meta.get('home_pf', '-')}** / Yenilen **{meta.get('home_pa', '-')}** | Son 3 Maç: `{h_rec}`\n"
                f"- **{target['away_team']}** ({meta.get('away_n', 0)} Maç): Ort. Atılan **{meta.get('away_pf', '-')}** / Yenilen **{meta.get('away_pa', '-')}** | Son 3 Maç: `{a_rec}`\n\n"
                f"⚡ **5.000 Pozisyon Monte Carlo Simülasyon Çıktısı ({sim['elapsed_seconds']} sn):**\n"
                f"- **Ev Sahibi Galibiyet:** %{round(sim['home_win_prob']*100, 1)} (Tahmin: {sim['projected_home_score']} sayı)\n"
                f"- **Deplasman Galibiyet:** %{round(sim['away_win_prob']*100, 1)} (Tahmin: {sim['projected_away_score']} sayı)\n"
                f"- **Saf İstatistik Toplamı:** {sim.get('raw_empirical_total', '-')} Sayı | **Dengelenmiş Model Toplamı:** {sim['projected_total']} Sayı\n\n"
            )
            if sim["best_ev"] >= 3.5:
                msg += f"🔥 **MODEL TAVSİYESİ (+EV):** **{sim['recommendation']}** (Avantaj: **+%{sim.get('best_edge', sim['best_ev'])} Edge** | Getiri: **+%{sim.get('best_ev_roi', 0.0)} ROI**)\n"
            else:
                msg += f"⚖️ **MODEL TAVSİYESİ:** `{sim['recommendation']}` — Oran avantajı eşiğin altında.\n"
                
            yield f"event: message\ndata: {json.dumps({'chunk': msg})}\n\n"

        else:
            # General summary of top +EV matches
            top_3 = ev_picks[:3]
            msg = (
                f"📋 **Nesine Güncel Basketbol Bülteni & Resmi İstatistik Analizi ({len(matches)} Maç Tarandı):**\n\n"
                f"Tüm maçlar `apistats.nesine.com` resmi geçmiş maç skorları (4 periyot normal süre, uzatma hariç) ile doğrulandı:\n\n"
            )
            for i, p in enumerate(top_3, 1):
                msg += (
                    f"{i}. **{p['matchup']}** ({p['league']})\n"
                    f"   • **Öneri:** `{p['recommendation']} ` | **Nesine Oran:** {p['odds']} | **Model Proj:** {p['model_proj']} Sayı (Saf Ort: {p.get('raw_emp_total')} Sayı)\n"
                    f"   • **Gerçek Maç Geçmişi:** {p.get('recent_summary', '')}\n"
                    f"   • **Avantaj:** **+%{p.get('edge_pct', p['ev_pct'])} Edge** | **ROI:** +%{p.get('roi_pct', 0.0)}% ({p['mbs_warning']})\n\n"
                )
            msg += "Dilediğiniz maçı (Örn: *'Napoli Tofaş maçını simüle et'* veya *'NBA maçlarını göster'*) sorabilirsiniz."
            yield f"event: message\ndata: {json.dumps({'chunk': msg})}\n\n"

        yield f"event: done\ndata: {json.dumps({'status': 'finished'})}\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

# Mount static frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
