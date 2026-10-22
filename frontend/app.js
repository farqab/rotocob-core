document.addEventListener('DOMContentLoaded', () => {
  let currentMode = 'betting';
  let activeTab = 'chat';
  let allMatches = [];
  let allEvPicks = [];

  // Türkçe Menü Tanımları ve Orijinal RotoBot SVG İkonları
  const NAV_ITEMS = {
    betting: [
      {
        id: 'chat',
        label: 'Yapay Zeka Copilot',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`
      },
      {
        id: 'rankings',
        label: 'Değerli Bahisler (+EV)',
        badge: 'NESİNE',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M8.5 12.3l2-2.2 1.6 1.1 2.4-3"/><path d="m20 20-3.1-3.1"/></svg>`
      },
      {
        id: 'games',
        label: 'Basket Maçları (100+)',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/><path d="M8 15h3"/><path d="M13 15h3"/></svg>`
      },
      {
        id: 'sharp',
        label: 'Akıllı Para & Steam',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8"/><path d="M17 7h4v4"/></svg>`
      }
    ],
    fantasy: [
      {
        id: 'chat',
        label: 'Fantezi Sohbet',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`
      },
      {
        id: 'league',
        label: 'Lig Merkezi',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 5h11a2 2 0 0 1 2 2v10"/><rect x="3" y="8" width="14" height="12" rx="2"/><path d="M7 12.5h6"/><path d="M7 16h4"/></svg>`
      },
      {
        id: 'trade',
        label: 'Takas Analizörü',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M8.5 12h7"/><path d="M13 9l2.5 3-2.5 3"/></svg>`
      },
      {
        id: 'sitstart',
        label: 'İlk 5 / Kadro Simülatörü',
        icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m7 4 4 4"/><path d="M7 4 3 8"/><path d="M7 4v16"/><path d="m17 20-4-4"/><path d="m17 20 4-4"/><path d="M17 20V4"/></svg>`
      }
    ]
  };

  const navContainer = document.getElementById('nav-items-container');
  const modeBtn = document.getElementById('btn-mode-toggle');
  const modeLabel = document.getElementById('mode-label-text');
  const modeKnob = document.getElementById('mode-toggle-knob');
  const modeTrack = document.getElementById('mode-toggle-track');
  const titleDisplay = document.getElementById('header-page-title');

  function renderNav() {
    navContainer.innerHTML = '';
    const items = NAV_ITEMS[currentMode];

    items.forEach(item => {
      const a = document.createElement('a');
      a.href = `#${item.id}`;
      a.className = `sidebar-nav-link ${activeTab === item.id ? 'active' : ''}`;
      a.innerHTML = `
        <span class="flex-shrink-0">${item.icon}</span>
        <span class="truncate flex-1">${item.label}</span>
        ${item.badge ? `<span class="text-[9px] font-black uppercase px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">${item.badge}</span>` : ''}
      `;

      a.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab(item.id, item.label);
      });

      navContainer.appendChild(a);
    });
  }

  function switchTab(tabId, label) {
    activeTab = tabId;
    renderNav();

    document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));

    const targetView = document.getElementById(`view-${tabId}`);
    if (targetView) {
      targetView.classList.remove('hidden');
      targetView.classList.add('active');
    }

    if (titleDisplay && label) {
      titleDisplay.innerHTML = `<span>⚡</span> ${label}`;
    }
  }

  // Mod Değiştirme
  modeBtn.addEventListener('click', () => {
    if (currentMode === 'betting') {
      currentMode = 'fantasy';
      document.body.classList.add('mode-fantasy');
      modeLabel.textContent = 'FANTEZİ LİGİ';
      modeLabel.style.color = '#00e6a0';
      modeBtn.style.background = 'rgba(0,212,146,.09)';
      modeBtn.style.borderColor = 'rgba(0,212,146,.26)';
      modeTrack.style.background = '#00c88c';
      modeTrack.style.boxShadow = '0 0 14px rgba(0,212,146,.3)';
      modeKnob.style.left = '25px';
    } else {
      currentMode = 'betting';
      document.body.classList.remove('mode-fantasy');
      modeLabel.textContent = 'İDDAA / BAHİS';
      modeLabel.style.color = 'rgba(255,255,255,.7)';
      modeBtn.style.background = 'rgba(255,255,255,.05)';
      modeBtn.style.borderColor = 'rgba(255,255,255,.09)';
      modeTrack.style.background = 'rgba(255,255,255,.14)';
      modeTrack.style.boxShadow = 'none';
      modeKnob.style.left = '3px';
    }
    renderNav();
  });

  // Canlı Nesine Bültenini ve +EV Fırsatlarını Yükle
  async function loadNesineData(refresh = false) {
    try {
      const res = await fetch(`/api/nesine/bulletin${refresh ? '?refresh=true' : ''}`);
      const data = await res.json();
      allMatches = data.matches || [];
      allEvPicks = data.ev_picks || [];

      document.getElementById('bulletin-status-badge').textContent = `${allMatches.length} Canlı Maç`;
      document.getElementById('ev-count-badge').textContent = `${allEvPicks.length} Değerli Fırsat Bulundu`;

      renderPropsTable(allEvPicks);
      renderGamesGrid(allMatches);
      renderSharpSignals(allEvPicks);
    } catch (e) {
      console.error('Bülten yükleme hatası:', e);
    }
  }

  // +EV Tablosunu Doldur
  function renderPropsTable(picks) {
    const tbody = document.getElementById('props-table-body');
    tbody.innerHTML = '';

    if (picks.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="py-6 text-center text-[#64748b]">Şu an barem avantajı bulunan maç taranıyor...</td></tr>`;
      return;
    }

    picks.forEach(p => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-white/[0.02] transition-colors';
      const mbsClass = p.mbs === 1 ? 'text-emerald-400 font-semibold' : 'text-amber-400';

      tr.innerHTML = `
        <td class="py-3 px-4 font-mono text-[#94a3b8]">${p.game_date}</td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded bg-white/[0.05] border border-white/[0.08] text-[11px] font-semibold text-white/90">${p.league}</span></td>
        <td class="py-3 px-4">
          <div class="font-semibold text-white">${p.matchup}</div>
          <div class="text-[10px] font-mono text-[#64748b] mt-0.5">${p.recent_summary || ''}</div>
        </td>
        <td class="py-3 px-4 font-mono font-bold">${p.market}</td>
        <td class="py-3 px-4 font-mono text-[#00d3f2] font-bold">
          <div>${p.model_proj} Sayı</div>
          <div class="text-[10px] text-[#64748b]">Saf Ort: ${p.raw_emp_total || '-'}</div>
        </td>
        <td class="py-3 px-4 font-mono">${p.model_prob}</td>
        <td class="py-3 px-4 font-mono text-white font-bold">${p.odds}</td>
        <td class="py-3 px-4"><span class="ev-pos">+%${p.edge_pct || p.ev_pct} Edge <span class="text-xs text-slate-400 font-normal">(ROI: %${p.roi_pct || 0})</span></span></td>
        <td class="py-3 px-4"><span class="badge-over">${p.recommendation}</span></td>
        <td class="py-3 px-4 ${mbsClass}">${p.mbs_warning}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Maç Kartları Izgarasını Doldur
  window.filterByLeague = (leagueKeyword) => {
    document.querySelectorAll('#league-filter-buttons button').forEach(b => {
      b.className = 'px-2.5 py-1 rounded bg-white/[0.05] text-[#94a3b8] hover:text-white';
    });
    event.target.className = 'px-2.5 py-1 rounded bg-[#00d3f2] text-black font-bold';

    if (leagueKeyword === 'ALL') {
      renderGamesGrid(allMatches);
    } else {
      const filtered = allMatches.filter(m => m.league.toLowerCase().includes(leagueKeyword.toLowerCase()));
      renderGamesGrid(filtered);
    }
  };

  function renderGamesGrid(matches) {
    const grid = document.getElementById('games-grid-container');
    grid.innerHTML = '';

    matches.slice(0, 48).forEach(m => {
      const sim = m.simulation || {};
      const card = document.createElement('div');
      card.className = 'p-4 rounded-xl border border-[#1e293b] bg-[#0b0f19]/80 flex flex-col justify-between space-y-3 hover:border-cyan-500/30 transition-all';
      
      const mbsTag = m.mbs === 1 
        ? '<span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold">MBS 1 (TEK MAÇ)</span>'
        : `<span class="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 font-bold">MBS ${m.mbs} (KOMBİNE)</span>`;

      const meta = sim.empirical_meta || {};
      const hRec = (meta.home_recent || []).map(x => x.score).join(', ');
      const aRec = (meta.away_recent || []).map(x => x.score).join(', ');

      card.innerHTML = `
        <div class="flex justify-between items-center text-[11px] text-[#64748b]">
          <span class="font-semibold text-white/80">${m.league}</span>
          ${mbsTag}
        </div>
        <div class="space-y-1.5 text-sm font-bold">
          <div>
            <div class="flex justify-between text-[#94a3b8]"><span>${m.away_team}</span> <span class="font-mono text-xs text-[#64748b]">Ort: ${meta.away_pf || '-'}/${meta.away_pa || '-'}</span></div>
            ${aRec ? `<div class="text-[10px] font-mono text-[#64748b] font-normal">Son 3: ${aRec}</div>` : ''}
          </div>
          <div>
            <div class="flex justify-between text-white"><span>${m.home_team}</span> <span class="font-mono text-xs text-cyan-400">Ort: ${meta.home_pf || '-'}/${meta.home_pa || '-'}</span></div>
            ${hRec ? `<div class="text-[10px] font-mono text-[#64748b] font-normal">Son 3: ${hRec}</div>` : ''}
          </div>
        </div>
        <div class="text-[11px] text-[#94a3b8] flex justify-between border-t border-b border-white/[0.04] py-1.5 font-mono">
          <span>Nesine Baremi: <strong>${m.line_total} Sayı</strong></span>
          <span>Üst: ${m.odds_total_over} | Alt: ${m.odds_total_under}</span>
        </div>
        <div id="sim-status-${m.id}" class="p-2 rounded-lg bg-black/40 border border-white/[0.05] text-[11px] font-mono text-[#94a3b8]">
          ${sim.projected_total ? `<strong>Model Tahmini:</strong> ${sim.projected_total} Sayı (Saf Ort: ${sim.raw_empirical_total}) — <span class="text-emerald-400 font-bold">${sim.recommendation}</span>` : `<span class="text-amber-400">${sim.recommendation || 'Veri Bekleniyor'}</span>`}
        </div>
        <button class="w-full py-2 bg-white/[0.04] hover:bg-[#00d3f2]/10 border border-[#00d3f2]/30 hover:border-[#00d3f2] text-[#00d3f2] text-xs font-bold rounded-lg transition-all" onclick="runSimLive('${m.id}')">
          ⚡ 5.000 Pozisyon Simüle Et
        </button>
      `;
      grid.appendChild(card);
    });
  }

  window.runSimLive = async (matchId) => {
    const box = document.getElementById(`sim-status-${matchId}`);
    if (box) box.innerHTML = '<span class="text-cyan-400 animate-pulse">5.000 Markov pozisyonu koşturuluyor...</span>';

    try {
      const res = await fetch(`/api/simulate/${matchId}`, { method: 'POST' });
      const sim = await res.json();
      if (box) {
        box.innerHTML = `
          <div class="text-left space-y-1">
            <div class="flex justify-between"><span>Ev Sahibi (${sim.projected_home_score} sy):</span> <span class="text-cyan-300 font-bold">%${(sim.home_win_prob*100).toFixed(1)}</span></div>
            <div class="flex justify-between"><span>Deplasman (${sim.projected_away_score} sy):</span> <span class="text-amber-300 font-bold">%${(sim.away_win_prob*100).toFixed(1)}</span></div>
            <div class="text-[10px] text-emerald-400 font-bold pt-1">Model Tahmini: ${sim.projected_total} Sayı (${sim.recommendation})</div>
          </div>
        `;
      }
    } catch (e) {
      if (box) box.innerHTML = '<span class="text-red-400">Simülasyon hatası</span>';
    }
  };

  function renderSharpSignals(picks) {
    const container = document.getElementById('sharp-signals-container');
    container.innerHTML = '';

    picks.slice(0, 5).forEach(p => {
      const card = document.createElement('div');
      card.className = 'p-4 rounded-xl border border-amber-500/40 bg-gradient-to-r from-amber-500/[0.06] to-transparent';
      card.innerHTML = `
        <div class="text-[10px] font-black uppercase tracking-wider text-amber-400 mb-1">🔥 YÜKSEK DEĞER SİNYALİ (+EV)</div>
        <h3 class="text-base font-bold text-white">${p.matchup} (${p.league})</h3>
        <p class="text-xs text-[#94a3b8] mt-1">
          Nesine baremi <strong>${p.market}</strong> olarak açıldı. 5.000 simülasyon sonucu model <strong>${p.model_proj} Sayı</strong> bekliyor.
        </p>
        <div class="flex gap-4 mt-3 text-xs font-mono text-cyan-400">
          <span>Öneri: <strong class="text-emerald-400">${p.recommendation}</strong></span>
          <span>Nesine Oran: ${p.odds}</span>
          <span class="text-emerald-400 font-bold">Avantaj: +%${p.ev_pct} EV</span>
          <span class="text-white/60">${p.mbs_warning}</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  // Türkçe SSE Chat Akışı
  const chatForm = document.getElementById('chat-input-form');
  const chatInput = document.getElementById('chat-text-input');
  const messagesScroll = document.getElementById('chat-messages-scroll');
  let currentThreadId = 'th_' + Math.random().toString(36).substring(7);

  window.triggerQuery = (q) => {
    chatInput.value = q;
    chatForm.dispatchEvent(new Event('submit'));
  };

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;

    // Kullanıcı Baloncuğu
    const userDiv = document.createElement('div');
    userDiv.className = 'flex gap-3.5 max-w-[85%] ml-auto justify-end items-start';
    userDiv.innerHTML = `
      <div class="bg-blue-600/20 border border-blue-500/40 p-3.5 rounded-2xl text-[13.5px] text-white">
        <p>${query}</p>
      </div>
      <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
        👤
      </div>
    `;
    messagesScroll.appendChild(userDiv);
    chatInput.value = '';

    // Asistan Baloncuğu İskeleti
    const botDiv = document.createElement('div');
    botDiv.className = 'flex gap-3.5 max-w-[85%] items-start';
    botDiv.innerHTML = `
      <img src="assets/RotoBotLogo.png" class="w-8 h-8 rounded-lg mt-0.5 object-contain flex-shrink-0 border border-cyan-500/30">
      <div class="bg-[#0f172a]/90 border border-[#1e293b] p-4 rounded-2xl text-[13.5px] leading-relaxed shadow-lg flex-1 live-stream-text">
        <p class="text-[#64748b] italic">RotoBot Türkçe motoru Nesine bültenini tarıyor...</p>
      </div>
    `;
    messagesScroll.appendChild(botDiv);
    messagesScroll.scrollTop = messagesScroll.scrollHeight;

    const streamText = botDiv.querySelector('.live-stream-text');

    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: currentThreadId,
          content: query,
          mode: 'v3'
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let text = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (let l of lines) {
          if (l.startsWith('data: ')) {
            try {
              const data = JSON.parse(l.replace('data: ', ''));
              if (data.chunk) {
                text += data.chunk;
                let formatted = text
                  .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                  .replace(/\*(.*?)\*/g, '<em>$1</em>')
                  .replace(/\n/g, '<br>');
                streamText.innerHTML = formatted;
                messagesScroll.scrollTop = messagesScroll.scrollHeight;
              }
            } catch (err) {}
          }
        }
      }
    } catch (err) {
      streamText.innerHTML = '<span class="text-rose-400">Nesine simülasyon motoruna bağlanırken hata oluştu.</span>';
    }
  });

  document.getElementById('btn-refresh').addEventListener('click', () => {
    loadNesineData(true);
  });

  document.getElementById('btn-quick-mc').addEventListener('click', () => {
    triggerQuery('Günün en değerli basketbol maçlarını göster');
  });

  renderNav();
  loadNesineData();
});
