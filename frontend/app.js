const lTeam = document.getElementById('left-team');
const rTeam = document.getElementById('right-team');
const hPanel = document.getElementById('history-panel');
const scanLoader = document.getElementById('scan-loader');
const searchIcon = document.getElementById('search-icon');
let patch = "14.8.1"; 

let championMap = {};
let perksMap = {};
let isPanelOpen = false;

const historyCache = {};
const timelineCache = {};

// --- FLAG HELPER ---
const flagMap = {
    "Germany": "🇩🇪", "South Korea": "🇰🇷", "France": "🇫🇷", "Spain": "🇪🇸", 
    "Denmark": "🇩🇰", "Sweden": "🇸🇪", "Poland": "🇵🇱", "United Kingdom": "🇬🇧",
    "United States": "🇺🇸", "Canada": "🇨🇦", "China": "🇨🇳", "Turkey": "🇹🇷",
    "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Czechia": "🇨🇿", "Norway": "🇳🇴"
};

// --- SVG ICONS FOR SOCIALS ---
const svgIcons = {
    twitch: `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z"/></svg>`,
    twitter: `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`,
    youtube: `<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .501 6.186C0 8.07 0 12 0 12s0 3.93.501 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.377.505 9.377.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`,
    wiki: `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`
};

async function loadDictionaries() {
    try {
        const verRes = await fetch("https://ddragon.leagueoflegends.com/api/versions.json");
        const versions = await verRes.json();
        patch = versions[0]; 

        const champRes = await fetch(`https://ddragon.leagueoflegends.com/cdn/${patch}/data/en_US/champion.json`);
        const champData = await champRes.json();
        for (let champName in champData.data) { championMap[champData.data[champName].key] = champData.data[champName].id; }
        
        const perksRes = await fetch("https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/perks.json");
        const perksData = await perksRes.json();
        perksData.forEach(perk => {
            let path = perk.iconPath.toLowerCase();
            perksMap[perk.id] = path.replace('/lol-game-data/assets/v1/', 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/');
        });
    } catch (e) { console.error("Dictionary Load Failed", e); }
}
loadDictionaries();

let currentHistoryOffset = 0;
let currentHistoryPuuid = "";

function calculateAge(birthdayString) {
    if (!birthdayString) return null;
    const today = new Date();
    const birthDate = new Date(birthdayString);
    let age = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) age--;
    return age;
}

function copyLobbyLink(btn) {
    navigator.clipboard.writeText("protracker.gg/live/EUW/19238471");
    btn.innerHTML = "COPIED!"; btn.style.color = "var(--green)"; btn.style.borderColor = "var(--green)";
    setTimeout(() => { btn.innerHTML = "SHARE"; btn.style.color = ""; btn.style.borderColor = ""; }, 2000);
}

function formatMastery(points) {
    if (!points) return "0k";
    if (points >= 1000000) return (points / 1000000).toFixed(1) + "M";
    return Math.floor(points / 1000) + "k";
}

function formatRank(rank) {
    if (!rank) return "UNRANKED";
    return rank.toUpperCase();
}

function handleCardClick(el) {
    const p = JSON.parse(el.getAttribute('data-player'));
    openHistory(p);
}

function getBadgeClass(tag) {
    if (["Winners Queue", "On Fire", "STOMP ANGLE?"].includes(tag)) return "badge-positive";
    if (["Unlucky", "Losers Queue", "TILT SWAPPED", "YOU'RE COOKED", "FF ANGLE?", "INSECURE"].includes(tag)) return "badge-negative";
    if (tag === "SECRET WEAPON") return "badge-special";
    if (tag === "CONTENT CREATOR") return "badge-creator";
    if (tag === "PRO") return "badge-pro";
    return "badge-neutral"; 
}

function renderTeamSummary(teamArray, side, teamTags) {
    let totalMastery = 0;
    // REVERTED: Now calculates total mastery across all known smurfs again
    teamArray.forEach(p => totalMastery += p.total_mastery || 0);
    const sideClass = side === 'ally' ? 'ally-card' : 'enemy-card';
    let tagHtml = teamTags.map(tag => `<div class="badge ${getBadgeClass(tag)}">${tag}</div>`).join('');
    return `<div class="card summary-card ${sideClass}"><div class="row-content"><div class="identity-group"></div><div class="mastery-group"><div class="mastery-label" style="color: var(--gold);">TEAM MASTERY</div><div class="mastery-score">${formatMastery(totalMastery)}</div></div><div class="stats-group"></div><div class="tags-group">${tagHtml}</div></div></div>`;
}

function render(p, index) {
    const champName = championMap[p.championId] || "Unknown";
    const splashImg = `https://ddragon.leagueoflegends.com/cdn/img/champion/centered/${champName}_0.jpg`;
    
    const clickAction = p.is_streamer ? "" : `data-player='${JSON.stringify(p).replace(/'/g, "&apos;")}' onclick='handleCardClick(this)'`;    
    const isDev = p.tag === 'THE DEV';
    const cardEffectClass = isDev ? 'effect-the-dev' : '';

    if (p.is_streamer) {
        return `
        <div class="card ${p.side}-card unclickable" style="animation-delay: ${index * 0.15}s;">
            <div class="card-bg-wrapper"><div class="champ-splash streamer-splash" style="background-image: url('${splashImg}')"></div></div>
            <div class="row-content">
                <div class="identity-group">
                    <div class="main-name" style="color: #7b7a8e; font-style: italic;">Streamer mode</div>
                </div>
                <div class="mastery-group"></div>
                <div class="stats-group"></div>
                <div class="tags-group">
                    <div class="badge badge-negative">INSECURE</div>
                </div>
            </div>
        </div>`;
    }

    const displayName = p.known_name || p.riotId.split('#')[0];
    const rankPosHtml = p.ladder_rank ? `<span style="color: var(--gold); font-weight: 900; margin-right: 6px;">#${p.ladder_rank}</span>` : '';
    const nameClass = (p.is_pro || p.is_creator) ? 'pro-name-gold' : 'main-name truncate-text';
    const wrapperClass = (p.is_pro || p.is_creator) ? 'identity-group-pro' : 'riot-id-wrapper';

    const identityHtml = `
        <div class="${wrapperClass}">
            <div class="${nameClass}">${displayName}</div>
            <div class="riot-id-subtext">${rankPosHtml}${p.riotId}</div>
            ${p.mantra ? `<div class="mantra-text" style="margin-top:2px;">"${p.mantra}"</div>` : ''}
        </div>
    `;

    let statsHtml = '';
    if (!p.rank || p.rank.toLowerCase() === 'unranked') {
        statsHtml = `<div class="stat-line" style="color: #7b7a8e; font-weight: 800; font-size: 0.9rem; text-transform: uppercase;">Unranked</div>`;
    } else {
        const rankPngUrl = `https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-${p.rank.toLowerCase()}.png`;
        statsHtml = `
            <div class="stat-line stat-highlight">
                <img src="${rankPngUrl}" class="rank-icon" onerror="this.style.display='none'">
                ${formatRank(p.rank)} <span class="stat-highlight">${p.lp || 0} LP</span>
            </div>
            <div class="stat-line">WR: <span class="stat-highlight">N/A</span></div>
            <div class="stat-line">KDA: <span class="stat-highlight">N/A</span></div>
        `;
    }

    let tagsHtml = '';
    if (p.is_pro && !isDev) tagsHtml += `<div class="badge ${getBadgeClass('PRO')}">PRO</div>`;
    if (p.is_creator && !isDev) tagsHtml += `<div class="badge ${getBadgeClass('CONTENT CREATOR')}">CONTENT CREATOR</div>`;
    if (p.tag) tagsHtml += `<div class="badge ${getBadgeClass(p.tag)}">${p.tag}</div>`;

    return `
        <div class="card ${p.side}-card ${cardEffectClass}" style="animation-delay: ${index * 0.15}s;" ${clickAction}>
            <div class="card-bg-wrapper"><div class="champ-splash" style="background-image: url('${splashImg}')"></div></div>
            <div class="row-content">
                <div class="identity-group">${identityHtml}</div>
                <div class="mastery-group tooltip-box" data-tooltip="${formatMastery(p.current_mastery)} on this account, ${formatMastery(p.total_mastery)} total across all connected accounts.">
                    <div class="mastery-label">True Mastery</div>
                    <div class="mastery-score">${formatMastery(p.total_mastery)}</div>
                </div>
                <div class="stats-group">
                    ${statsHtml}
                </div>
                <div class="tags-group">${tagsHtml}</div>
            </div>
        </div>`;
}

async function executeScan() {
    const rawQuery = document.getElementById('target').value.trim();
    if(!rawQuery.includes('#')) {
        console.warn("Invalid Riot ID. Must include a # tag.");
        return;
    }
    const [name, tag] = rawQuery.split('#');
    if(!name || !tag) return;

    searchIcon.style.display = 'none'; scanLoader.style.display = 'block';
    lTeam.innerHTML = ''; rTeam.innerHTML = ''; document.getElementById('intel-banner').style.display = 'none';

    try {
        const res = await fetch(`http://localhost:8000/api/player/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`);
        
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Player not found");
        }
        
        const liveData = await res.json();
        if (liveData.status === "history") throw new Error("Player not in game.");

        document.getElementById('intel-text').innerHTML = `<span class='intel-accent'>GAME INFO:</span> Live data retrieved successfully.`;
        document.getElementById('intel-banner').style.display = 'flex';

        lTeam.innerHTML = renderTeamSummary(liveData.allies, 'ally', []) + liveData.allies.map((p, i) => render(p, i)).join('');
        rTeam.innerHTML = renderTeamSummary(liveData.enemies, 'enemy', liveData.ff_angle ? ["FF ANGLE?"] : []) + liveData.enemies.map((p, i) => render(p, i)).join('');
    } catch (e) {
        document.getElementById('intel-text').innerHTML = `<span class='intel-accent' style='color:var(--red);'>ERROR:</span> ${e.message}`;
        document.getElementById('intel-banner').style.display = 'flex';
    }
    scanLoader.style.display = 'none'; searchIcon.style.display = 'block';
}

async function openHistory(p) {
    if (!p.puuid || p.is_streamer) return; 
    isPanelOpen = true; 
    hPanel.classList.add('active');
    currentHistoryOffset = 0; 
    currentHistoryPuuid = p.puuid;
    
    // 1. Calculate Data for the Hero Sidebar
    let ageStr = "";
    if (p.birthday) {
        const age = calculateAge(p.birthday);
        if (age) ageStr = `${age} Y/O`;
    }
    
    const flag = (p.nationality && flagMap[p.nationality]) ? flagMap[p.nationality] : "";
    const teamName = p.team || ""; 
    const displayName = p.known_name || p.riotId.split('#')[0];
    const hasImage = !!p.profile_image_url;

    // 2. Build Accounts Section
    let allAccounts = new Set();
    if (p.riotId) allAccounts.add(p.riotId);
    if (p.smurfs && Array.isArray(p.smurfs)) p.smurfs.forEach(acc => allAccounts.add(acc));
    if (p.riot_accounts && Array.isArray(p.riot_accounts)) p.riot_accounts.forEach(acc => allAccounts.add(acc));
    
    let accountsSectionHtml = "";
    if (allAccounts.size > 0) {
        const badges = Array.from(allAccounts).map(acc => `<span class="hero-account-badge">${acc}</span>`).join('');
        accountsSectionHtml = `
            <div class="panel-section-header">Known Accounts</div>
            <div class="hero-accounts">
                ${badges}
            </div>
        `;
    }

    // 3. Build Socials Section
    let socialsHtml = '';
    if (p.socials) {
        for (const [platform, handle] of Object.entries(p.socials)) {
            if (handle) {
                const url = handle.startsWith('http') ? handle : `https://${platform.toLowerCase()}.com/${handle.replace('@', '')}`;
                const icon = svgIcons[platform.toLowerCase()] || platform;
                socialsHtml += `<a href="${url}" target="_blank" class="panel-social-link ${platform.toLowerCase()}" title="${platform}">${icon}</a>`;
            }
        }
    }
    if (p.leaguepedia_url) {
        socialsHtml += `<a href="${p.leaguepedia_url}" target="_blank" class="panel-social-link wiki" title="Leaguepedia">${svgIcons.wiki}</a>`;
    }

    let socialsSectionHtml = '';
    if (socialsHtml.length > 0) {
        socialsSectionHtml = `
            <div class="panel-section-header">Socials</div>
            <div class="panel-socials">
                ${socialsHtml}
            </div>
        `;
    }

    // 4. Inject the Cinematic Hero Section
    const oldHero = document.getElementById('dynamic-hero');
    if (oldHero) oldHero.remove();

    const heroClass = hasImage ? 'hero-container' : 'hero-container no-image';
    const bgHtml = hasImage ? `
        <div class="hero-bg" style="background-image: url('${p.profile_image_url}');"></div>
        <div class="hero-overlay"></div>
    ` : '';

    const heroHtml = `
        <div id="dynamic-hero">
            <div class="${heroClass}">
                ${bgHtml}
                <div class="hero-content">
                    <div class="hero-top-row">
                        <div>
                            <h2 class="hero-name" title="${displayName}">${displayName}</h2>
                            <div class="hero-meta">
                                ${p.is_pro ? `<span class="badge badge-pro" style="margin:0;">PRO</span>` : ''}
                                ${flag ? `<span>${flag}</span>` : ''}
                                ${ageStr ? `<span>${ageStr}</span>` : ''}
                                ${p.role ? `<span style="color:var(--border);">•</span><span>${p.role}</span>` : ''}
                                ${teamName ? `<span style="color:var(--border);">•</span><span style="color:var(--gold);">${teamName}</span>` : ''}
                            </div>
                        </div>
                        ${p.team_logo_url ? `<img src="${p.team_logo_url}" class="hero-logo" onerror="this.style.display='none'">` : ''}
                    </div>
                </div>
            </div>
            
            ${accountsSectionHtml}
            ${socialsSectionHtml}
        </div>
    `;

    const closeBtn = document.getElementById('close-panel-btn');
    closeBtn.insertAdjacentHTML('afterend', heroHtml);
    
    // 5. LOAD MATCH HISTORY
    document.getElementById('history-loading').innerHTML = `<div class="loader-ring" style="display:block; margin: 40px auto;"></div>`;
    await fetchAndRenderMatches(0);
}

async function fetchAndRenderMatches(offset) {
    const loadingDiv = document.getElementById('history-loading');
    try {
        const cacheKey = `${currentHistoryPuuid}_${offset}`;
        let matchData;
        
        if (historyCache[cacheKey]) {
            matchData = historyCache[cacheKey]; 
        } else {
            const response = await fetch(`http://localhost:8000/api/history/${currentHistoryPuuid}?start=${offset}&count=5`);
            
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to load matches.");
            }
            
            matchData = await response.json();
            historyCache[cacheKey] = matchData; 
        }
        
        const chevronSvg = `<svg class="expand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

        const historyHtml = matchData.map(m => {
            const color = m.isWin ? 'var(--blue)' : 'var(--red)';
            
            const oppImg = m.oppChamp !== "Unknown" ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/champion/${m.oppChamp}.png" class="match-champ-icon opp-champ" onerror="this.style.display='none'">` : '';
            const vsText = m.oppChamp !== "Unknown" ? `<span style="font-size:0.7rem; color:var(--text-muted); font-weight:bold; margin: 0 4px;">VS</span>` : '';
            
            const invItems = m.items.slice(0, 6).map(id => id > 0 
                ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${id}.png" style="width: 24px; height: 24px; border-radius: 4px;">` 
                : `<div style="width: 24px; height: 24px; border-radius: 4px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05);"></div>`
            ).join('');
            
            const trinket = m.items[6] > 0 
                ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${m.items[6]}.png" style="width: 24px; height: 24px; border-radius: 50%;">` 
                : `<div style="width: 24px; height: 24px; border-radius: 50%; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05);"></div>`;

            const finalItemsHtml = `<div style="display:flex; gap:2px; align-items:center;">${invItems} <div style="width:1px; height:20px; background:#3e3e4a; margin: 0 4px;"></div> ${trinket}</div>`;

            const runesJson = encodeURIComponent(JSON.stringify(m.runes));

            return `
            <div class="match-card" style="border-left-color: ${color}" onclick="toggleBuildPath(this, '${m.matchId}', '${m.puuid}', '${runesJson}')">
                <div class="match-row-main">
                    <div style="display: flex; gap: 15px; align-items: center;">
                        <div class="match-champs tooltip-box" data-tooltip="Laned against ${m.oppChamp}">
                            <img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/champion/${m.myChamp}.png" class="match-champ-icon">
                            ${vsText}
                            ${oppImg}
                        </div>
                        <div class="match-details">
                            <div style="color: ${color}; font-weight: 900; font-size: 1.1rem;">${m.result} <span style="color: var(--text-muted); font-size: 0.8rem; font-weight: normal; margin-left: 5px;">${m.time}</span></div>
                            <div style="font-family: monospace; color: var(--text-main); font-size: 1rem; font-weight:bold; margin: 3px 0;">
                                ${m.kda} <span style="color: var(--red); font-size: 0.75rem; font-family: 'Roboto', sans-serif; margin-left: 6px; font-weight: 800;">(${m.kp} KP)</span>
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; justify-content: flex-end; flex: 1;">
                        ${finalItemsHtml}
                        ${chevronSvg}
                    </div>
                </div>
                <div class="build-path-container"></div>
            </div>`;
        }).join('');

        const loadBtn = `<button onclick="loadMoreMatches()" style="width:100%; padding:12px; background:var(--search-bg); border:1px solid var(--border); color:var(--text-main); font-weight:bold; border-radius:6px; cursor:pointer; margin-top:10px;">Load 5 More Games</button>`;
        
        if (offset === 0) loadingDiv.innerHTML = `<div class="panel-section-header">Recent Games</div>` + historyHtml + loadBtn;
        else { loadingDiv.querySelector('button').remove(); loadingDiv.innerHTML += historyHtml + loadBtn; }
    } catch (error) { 
        loadingDiv.innerHTML = `<div style="color: var(--red); font-weight: bold; font-family: monospace; text-align: center; margin-top: 50px;">${error.message}</div>`; 
    }
}

function loadMoreMatches() {
    currentHistoryOffset += 5;
    document.getElementById('history-loading').querySelector('button').innerText = "Loading...";
    fetchAndRenderMatches(currentHistoryOffset);
}

async function toggleBuildPath(cardElem, matchId, puuid, runesEncoded) {
    const container = cardElem.querySelector('.build-path-container');
    if (container.style.display === 'block') {
        container.style.display = 'none';
        cardElem.classList.remove('expanded');
        return;
    }
    
    container.style.display = 'block';
    cardElem.classList.add('expanded');
    if (container.innerHTML !== '') return; 

    container.innerHTML = '<div class="loader-ring" style="width: 20px; height: 20px; margin: 10px auto; display: block;"></div>';
    
    try {
        let timeline;
        if (timelineCache[matchId]) {
            timeline = timelineCache[matchId];
        } else {
            const res = await fetch(`http://localhost:8000/api/timeline/${matchId}/${puuid}`);
            
            if (!res.ok) {
                 const errData = await res.json().catch(() => ({}));
                 throw new Error(errData.detail || "Failed to load timeline.");
            }
            timeline = await res.json();
            timelineCache[matchId] = timeline; 
        }
        
        const r = JSON.parse(decodeURIComponent(runesEncoded));

        const seqHtml = timeline.skills.slice(0, 18).map(s => {
            const label = {1:'Q', 2:'W', 3:'E', 4:'R'}[s];
            return `<div class="seq-badge is-${label.toLowerCase()}">${label}</div>`;
        }).join('');

        const safeR = (id, sz, cls="") => id ? `<img src="${perksMap[id]}" style="width:${sz}px; height:${sz}px; ${cls}">` : '';
        
        const runesHtml = `
            <div class="rune-box-full">
                <div class="rune-column">
                    ${safeR(r.primaryPerks[0], 42)}
                    <div style="display:flex; gap:6px;">
                        ${r.primaryPerks.slice(1).map(p => safeR(p, 28, "opacity:0.9")).join('')}
                    </div>
                </div>
                <div class="rune-column">
                    <div style="display:flex; gap:6px; margin-top: 10px;">
                        ${r.subPerks.map(p => safeR(p, 28, "opacity:0.9")).join('')}
                    </div>
                </div>
                <div class="rune-column stat-column" style="gap:6px;">
                    ${r.statPerks.map(p => safeR(p, 22, "filter:brightness(1.2)")).join('')}
                </div>
            </div>
        `;

        const ignored = new Set([2003, 2055, 2031, 2033, 3340, 3364, 3363, 2010]);
        const batches = [];
        timeline.purchases.forEach(e => {
            if (ignored.has(e.itemId)) return;
            const m = Math.floor(e.timestamp / 60000);
            if (!batches.length || batches[batches.length-1].m !== m) batches.push({m:m, items:[e.itemId]});
            else batches[batches.length-1].items.push(e.itemId);
        });

        const itemsHtml = batches.map(b => `
            <div style="display:flex; flex-direction:column; align-items:center; gap:4px; margin-bottom: 8px;">
                <div style="display:flex; gap:4px; background:#282830; padding:6px; border-radius:4px; border: 1px solid #3e3e4a;">
                    ${b.items.map(id => `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${id}.png" style="width:26px; height:26px; border-radius:3px;">`).join('')}
                </div>
                <span style="font-size:11px; color:#7b7a8e; font-weight:bold;">${b.m}m</span>
            </div>
        `).join('<div style="color:#666; font-size:20px; font-weight:bold; margin-top:8px; align-self: flex-start; padding-top: 2px;">›</div>');

        container.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:25px; margin-top:5px;">
                <div>
                    <div class="section-title">Recall Timeline</div>
                    <div style="display:flex; flex-wrap:wrap; gap:6px; align-items:flex-start;">
                        ${itemsHtml || '<span style="color:var(--text-muted); font-size:0.8rem;">No items purchased.</span>'}
                    </div>
                </div>
                <div>
                    <div class="section-title">Skill Sequence</div>
                    <div style="display:flex; gap:4px; flex-wrap:wrap;">
                        ${seqHtml}
                    </div>
                </div>
                <div>
                    <div class="section-title">Runes & Stats</div>
                        ${runesHtml}
                </div>
            </div>
        `;
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div style="color:var(--red); text-align:center;">${e.message}</div>`;
    }
}

// --- NEW SEARCH TRIGGER EVENT LISTENERS ---
document.getElementById('target').addEventListener('keydown', e => { 
    if (e.key === 'Enter') {
        e.preventDefault();
        executeScan(); 
    }
});

document.getElementById('search-icon').addEventListener('click', () => {
    executeScan();
});

document.getElementById('close-panel-btn').addEventListener('click', () => { 
    isPanelOpen = false; 
    hPanel.classList.remove('active'); 
});

document.addEventListener('click', (e) => { 
    if (hPanel.classList.contains('active') && !hPanel.contains(e.target) && !e.target.closest('.card')) {
        hPanel.classList.remove('active'); 
    }
});