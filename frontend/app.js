const lTeam = document.getElementById('left-team');
const rTeam = document.getElementById('right-team');
const hPanel = document.getElementById('history-panel');
const scanLoader = document.getElementById('scan-loader');
const searchIcon = document.getElementById('search-icon');
let patch = "14.8.1"; 

let championMap = {};
let perksMap = {};

const historyCache = {};
const timelineCache = {};

const flagMap = {
    "Germany": "🇩🇪", "South Korea": "🇰🇷", "France": "🇫🇷", "Spain": "🇪🇸", 
    "Denmark": "🇩🇰", "Sweden": "🇸🇪", "Poland": "🇵🇱", "United Kingdom": "🇬🇧",
    "United States": "🇺🇸", "Canada": "🇨🇦", "China": "🇨🇳", "Turkey": "🇹🇷",
    "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Czechia": "🇨🇿", "Norway": "🇳🇴",
    "France, Morocco": "🇫🇷", "Brazil": "🇧🇷", "Mexico": "🇲🇽", "Argentina": "🇦🇷",
    "Chile": "🇨🇱", "Colombia": "🇨🇱", "Peru": "🇵🇪", "Japan": "🇯🇵",
    "Vietnam": "🇯🇵", "Taiwan": "🇹🇼", "Australia": "🇦🇺", "New Zealand": "🇦🇺",
    "Russia": "🇷🇺", "Ukraine": "🇷🇺", "Italy": "🇮🇹", "Portugal": "🇵🇹",
    "Greece": "🇮🇹", "Switzerland": "🇬🇷", "Austria": "🇨🇭", "Finland": "🇨🇭",
    "Ireland": "🇮🇪", "Romania": "🇷🇴", "Bulgaria": "🇧🇬", "Hungary": "🇭🇺",
    "Serbia": "🇷🇸", "Croatia": "🇭🇷", "Slovakia": "🇸🇰", "Slovenia": "🇸🇮",
    "Estonia": "🇪🇪", "Latvia": "🇪🇪", "Lithuania": "🇱🇹", "Iceland": "🇮🇸",
    "India": "🇮🇳", "Indonesia": "🇮🇳", "Philippines": "🇮🇩", "Malaysia": "🇵🇭",
    "Singapore": "🇲🇾", "Thailand": "🇹🇭", "Egypt": "🇪🇬", "Morocco": "🇲🇦",
    "South Africa": "🇿🇦", "Nigeria": "🇿🇦", "Saudi Arabia": "🇸🇦", "UAE": "🇸🇦"
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

function getBadgeClass(tag) {
    if (["Winners Queue", "On Fire", "STOMP ANGLE?"].includes(tag)) return "badge-positive";
    if (["Unlucky", "Losers Queue", "TILT SWAPPED", "YOU'RE COOKED", "FF ANGLE?", "INSECURE"].includes(tag)) return "badge-negative";
    if (tag === "SECRET WEAPON") return "badge-special";
    if (tag === "PRO" || tag === "CONTENT CREATOR") return "badge-pro";
    return "badge-neutral"; 
}

function renderTeamSummary(teamArray, side, teamTags) {
    let totalMastery = 0;
    teamArray.forEach(p => totalMastery += p.total_mastery || 0);
    const sideClass = side === 'ally' ? 'ally-card' : 'enemy-card';
    let tagHtml = teamTags.map(tag => `<div class="badge ${getBadgeClass(tag)}">${tag}</div>`).join('');
    return `<div class="card summary-card ${sideClass}"><div class="row-content"><div class="identity-group"></div><div class="mastery-group"><div class="mastery-label" style="color: var(--gold);">TEAM MASTERY</div><div class="mastery-score">${formatMastery(totalMastery)}</div></div><div class="stats-group"></div><div class="tags-group">${tagHtml}</div></div></div>`;
}

function render(p, index) {
    const champName = championMap[p.championId] || "Unknown";
    const splashImg = `https://ddragon.leagueoflegends.com/cdn/img/champion/centered/${champName}_0.jpg`;
    const clickAction = p.is_streamer ? "" : `onclick='openHistory(${JSON.stringify(p).replace(/'/g, "&#39;")})'`;
    
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

    let identityHtml = '';
    if (p.is_pro || p.is_creator) {
        identityHtml = `
            <div class="identity-group-pro">
                <div class="pro-name-gold">${p.known_name}</div>
                <div class="riot-id-subtext">${p.riotId}</div>
            </div>
        `;
    } else {
        identityHtml = `<div class="riot-id-wrapper"><span class="main-name truncate-text">${p.riotId}</span></div>`;
    }

    if (p.mantra && !p.is_pro && !p.is_creator) {
        identityHtml = identityHtml.replace('</div>', `<div class="mantra-text">"${p.mantra}"</div></div>`);
    } else if (p.mantra && (p.is_pro || p.is_creator)) {
         identityHtml = identityHtml.replace('</div>\n            </div>', `</div><div class="mantra-text" style="margin-top:2px;">"${p.mantra}"</div>\n            </div>`);
    }

    let statsHtml = '';
    if (p.rank.toLowerCase() === 'unranked') {
        statsHtml = `<div class="stat-line" style="color: #7b7a8e; font-weight: 800; font-size: 0.9rem; text-transform: uppercase;">Unranked</div>`;
    } else {
        const rankPngUrl = `https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-${p.rank.toLowerCase()}.png`;
        statsHtml = `
            <div class="stat-line stat-highlight">
                <img src="${rankPngUrl}" class="rank-icon" onerror="this.style.display='none'">
                ${p.rank.toUpperCase()} <span class="stat-highlight">${p.lp || 0} LP</span>
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
    if(!rawQuery.includes('#')) return;
    
    const [name, tag] = rawQuery.split('#').map(s => s.trim());

    searchIcon.style.display = 'none'; scanLoader.style.display = 'block';
    lTeam.innerHTML = ''; rTeam.innerHTML = ''; document.getElementById('intel-banner').style.display = 'none';

    try {
        const res = await fetch(`http://localhost:8000/api/player/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`);
        const liveData = await res.json();
        
        if (!res.ok) throw new Error(liveData.detail || "Player not found");
        if (liveData.status === "history") throw new Error("Player not currently in game.");

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
    isPanelOpen = true; hPanel.classList.add('active');
    currentHistoryOffset = 0; currentHistoryPuuid = p.puuid;
    
    document.getElementById('panel-player-name').innerText = p.known_name || p.riotId.split('#')[0];
    document.getElementById('panel-riot-id').innerText = p.riotId;

    const imgElem = document.getElementById('panel-pro-img');
    const heroContentElem = document.querySelector('.sidebar-hero-content');
    
    if (p.real_img) {
        imgElem.src = p.real_img;
        imgElem.style.display = 'block';
        if (heroContentElem) heroContentElem.classList.remove('no-image');
    } else {
        imgElem.style.display = 'none';
        imgElem.src = '';
        if (heroContentElem) heroContentElem.classList.add('no-image');
    }

    let bioDetails = [];
    
    if (p.nationality && flagMap[p.nationality]) {
        bioDetails.push(`<span class="flag-text">${flagMap[p.nationality]}</span>`);
    }

    if (p.role) {
        let roleCleaned = p.role.toLowerCase().trim();
        if (roleCleaned === 'adc') roleCleaned = 'bot';
        if (roleCleaned === 'jungler') roleCleaned = 'jungle';
        const roleHtml = `<img src="http://localhost:8000/images/roles/${roleCleaned}.png" class="role-icon-img" onerror="this.style.display='none'" title="${p.role}">`;
        bioDetails.push(roleHtml);
    }
    
    if (p.team) {
        const logoHtml = p.team_logo ? `<img src="${p.team_logo}" class="team-icon-img" onerror="this.style.display='none'">` : '';
        const safeTeam = p.team.replace(/'/g, "\\'");
        const safeLogo = p.team_logo ? p.team_logo.replace(/'/g, "\\'") : '';
        bioDetails.push(`<span class="clickable-team" onclick="openTeamRoster('${safeTeam}', '${safeLogo}')">${logoHtml}${p.team}</span>`);
    }

    let finalIdentityArr = [];
    if (p.real_name && p.real_name.trim() !== "") {
        finalIdentityArr.push(p.real_name.trim());
    }
    
    if (p.birthday && p.birthday.trim() !== "None") {
        const birthDate = new Date(p.birthday);
        if (!isNaN(birthDate.getTime())) {
            const diffMs = Date.now() - birthDate.getTime();
            const ageDt = new Date(diffMs);
            const age = Math.abs(ageDt.getUTCFullYear() - 1970);
            if (age > 0 && age < 100) {
                finalIdentityArr.push(`Age: ${age}`);
            }
        }
    }
    
    if (finalIdentityArr.length > 0) {
        bioDetails.push(`<span style="color:var(--text-main); font-weight: 900;">${finalIdentityArr.join(' | ')}</span>`);
    }

    if (bioDetails.length > 0) {
        document.getElementById('panel-bio-details').innerHTML = bioDetails.join('<span style="margin: 0 8px; color:var(--border);">|</span>');
    } else {
        document.getElementById('panel-bio-details').innerHTML = '';
    }

    let socialsHtml = '';
    const socialImgMap = {
        "Twitch": "twitch",
        "Twitter": "x",
        "YouTube": "youtube"
    };

    if (p.socials && Object.keys(p.socials).length > 0) {
        for (const [platform, handle] of Object.entries(p.socials)) {
            if (handle) {
                const url = handle.startsWith('http') ? handle : `https://${platform.toLowerCase()}.com/${handle.replace('@', '')}`;
                const imgName = socialImgMap[platform] || platform.toLowerCase();
                socialsHtml += `
                    <a href="${url}" target="_blank" class="panel-social-icon tooltip-box" data-tooltip="${platform}">
                        <img src="http://localhost:8000/images/socials/${imgName}.png" class="social-icon-img" onerror="this.style.display='none'">
                    </a>`;
            }
        }
    }
    
    if (p.leaguepedia) {
        socialsHtml += `
            <a href="${p.leaguepedia}" target="_blank" class="panel-social-icon tooltip-box" data-tooltip="Leaguepedia">
                <img src="http://localhost:8000/images/socials/leaguepedia.png" class="social-icon-img" onerror="this.style.display='none'">
            </a>`;
    }

    if (socialsHtml !== '') {
        document.getElementById('panel-socials').innerHTML = `
            <div style="margin-top: 15px;">
                <div style="font-size: 0.75rem; color: #7b7a8e; text-transform: uppercase; font-weight: 800; margin-bottom: 8px;">Socials</div>
                <div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center;">
                    ${socialsHtml}
                </div>
            </div>`;
    } else {
        document.getElementById('panel-socials').innerHTML = '';
    }

    let smurfsHtml = '';
    if (p.smurfs && p.smurfs.length > 0) {
        smurfsHtml = `
            <div style="margin-top: 15px;">
                <div style="font-size: 0.75rem; color: #7b7a8e; text-transform: uppercase; font-weight: 800; margin-bottom: 8px;">Known Accounts</div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                    ${p.smurfs.map(s => `<span style="background: #282830; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #3e3e4a; color: var(--text-main);">${s}</span>`).join('')}
                </div>
            </div>
        `;
    }
    document.getElementById('panel-smurfs').innerHTML = smurfsHtml;

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
            matchData = await response.json();
            historyCache[cacheKey] = matchData; 
        }
        
        const chevronSvg = `<svg class="expand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

        const historyHtml = matchData.map(m => {
            const color = m.isWin ? 'var(--blue)' : 'var(--red)';
            
            const oppImg = m.oppChamp !== "Unknown" ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/champion/${m.oppChamp}.png" class="match-champ-icon opp-champ" onerror="this.style.display='none'">` : '';
            const vsText = m.oppChamp !== "Unknown" ? `<span style="font-size:0.7rem; color:var(--text-muted); font-weight:bold; margin: 0 4px;">VS</span>` : '';
            
            const invItems = m.items.slice(0, 6).map(id => id > 0 
                ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${id}.png" style="width: 30px; height: 30px; border-radius: 4px;">` 
                : `<div style="width: 30px; height: 30px; border-radius: 4px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05);"></div>`
            ).join('');
            
            const trinket = m.items[6] > 0 
                ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${m.items[6]}.png" style="width: 30px; height: 30px; border-radius: 50%;">` 
                : `<div style="width: 30px; height: 30px; border-radius: 50%; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05);"></div>`;

            const finalItemsHtml = `<div style="display:flex; gap:2px; align-items:center;">${invItems} <div style="width:1px; height:24px; background:#3e3e4a; margin: 0 4px;"></div> ${trinket}</div>`;

            const runesJson = encodeURIComponent(JSON.stringify(m.runes));

            return `
            <div class="match-card" style="border-left-color: ${color}" onclick="toggleBuildPath(this, '${m.matchId}', '${m.puuid}', '${runesJson}')">
                <div style="display: flex; gap: 15px; align-items: center; width: 100%;">
                    
                    <div class="match-champs tooltip-box" data-tooltip="Laned against ${m.oppChamp}" style="flex-shrink: 0;">
                        <img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/champion/${m.myChamp}.png" class="match-champ-icon">
                        ${vsText}
                        ${oppImg}
                    </div>

                    <div style="display: flex; flex-direction: column; flex: 1; gap: 8px; min-width: 0;">
                        
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; width: 100%;">
                            <div class="match-details" style="display: flex; flex-direction: column; gap: 3px;">
                                <div style="display: flex; align-items: baseline; gap: 8px;">
                                    <span style="color: ${color}; font-weight: 900; font-size: 1rem; line-height: 1;">${m.result}</span>
                                    <span style="color: var(--text-muted); font-size: 0.75rem;">${m.time}</span>
                                </div>
                                <div style="font-family: monospace; color: var(--text-main); font-size: 1rem; font-weight: bold; line-height: 1;">
                                    ${m.kda} <span style="color: var(--red); font-size: 0.75rem; font-family: 'Roboto', sans-serif; font-weight: 800; margin-left: 4px;">(${m.kp} KP)</span>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; padding-top: 2px;">
                                ${chevronSvg}
                            </div>
                        </div>

                        <div style="display: flex; align-items: center;">
                            ${finalItemsHtml}
                        </div>

                    </div>
                </div>
                <div class="build-path-container"></div>
            </div>`;
        }).join('');

        const loadBtn = `<button onclick="loadMoreMatches()" style="width:100%; padding:12px; background:var(--search-bg); border:1px solid var(--border); color:var(--text-main); font-weight:bold; border-radius:6px; cursor:pointer; margin-top:10px;">Load 5 More Games</button>`;
        
        if (offset === 0) loadingDiv.innerHTML = `<div class="recent-games-header">Recent Games</div>` + historyHtml + loadBtn;
        else { loadingDiv.querySelector('button').remove(); loadingDiv.innerHTML += historyHtml + loadBtn; }
    } catch (error) { loadingDiv.innerHTML = `<div style="color: var(--red); text-align: center; margin-top: 50px;">Failed to load.</div>`; }
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
                    ${safeR(r.primaryPerks[0], 52)}
                    <div style="display:flex; gap:8px;">
                        ${r.primaryPerks.slice(1).map(p => safeR(p, 36, "opacity:0.9")).join('')}
                    </div>
                </div>
                <div class="rune-column">
                    <div style="display:flex; gap:8px; margin-top: 14px;">
                        ${r.subPerks.map(p => safeR(p, 36, "opacity:0.9")).join('')}
                    </div>
                </div>
                <div class="rune-column stat-column" style="gap:8px;">
                    ${r.statPerks.map(p => safeR(p, 28, "filter:brightness(1.2)")).join('')}
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
                    ${b.items.map(id => `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${id}.png" style="width:32px; height:32px; border-radius:3px;">`).join('')}
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
        container.innerHTML = '<div style="color:var(--red); text-align:center;">Failed to load match details.</div>';
    }
}

async function openTeamRoster(teamName, teamLogo) {
    const panel = document.getElementById('team-roster-panel');
    const content = document.getElementById('roster-content');
    
    const logoHtml = teamLogo ? `<img src="${teamLogo}" style="height: 22px; vertical-align: middle; margin-right: 8px; border-radius: 2px;" onerror="this.style.display='none'">` : '';
    document.getElementById('roster-team-name').innerHTML = `${logoHtml}${teamName}`;
    
    content.innerHTML = '<div class="loader-ring" style="margin: 30px auto; display: block;"></div>';
    panel.style.display = 'flex';
    setTimeout(() => panel.classList.add('active'), 10);

    try {
        const res = await fetch(`http://localhost:8000/api/team/${encodeURIComponent(teamName)}`);
        const data = await res.json();
        
        if (data.roster && data.roster.length > 0) {
            content.innerHTML = data.roster.map(player => {
                let roleCleaned = player.role ? player.role.toLowerCase().trim() : 'fill';
                if (roleCleaned === 'adc') roleCleaned = 'bot';
                if (roleCleaned === 'jungler') roleCleaned = 'jungle';
                
                const roleImg = `<img src="http://localhost:8000/images/roles/${roleCleaned}.png" style="height:14px; vertical-align:middle; margin-right:6px;" onerror="this.style.display='none'">`;
                const img = player.image ? `<img src="${player.image}" class="roster-player-img" onerror="this.style.display='none'">` : `<div class="roster-player-img"></div>`;
                const flag = (player.nationality && flagMap[player.nationality]) ? `<span style="font-size:1.1rem; margin-right:6px; vertical-align: middle;">${flagMap[player.nationality]}</span>` : '';
                
                return `
                    <div class="roster-player-card">
                        ${img}
                        <div class="roster-player-info">
                            <div class="roster-player-name">${flag}${player.name}</div>
                            <div class="roster-player-role">${roleImg}${player.role || 'Player'}</div>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            content.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding: 30px 0; font-weight: bold;">No other players found on this team.</div>';
        }
    } catch (e) {
        content.innerHTML = '<div style="color:var(--red); text-align:center; padding: 30px 0; font-weight: bold;">Failed to load roster.</div>';
    }
}

function closeTeamRoster() {
    const panel = document.getElementById('team-roster-panel');
    panel.classList.remove('active');
    setTimeout(() => panel.style.display = 'none', 300);
}

document.addEventListener('click', (e) => { 
    if (hPanel.classList.contains('active') && !hPanel.contains(e.target) && !e.target.closest('.card') && !e.target.closest('.team-roster-panel')) {
        hPanel.classList.remove('active');
        closeTeamRoster();
    }
    const rosterPanel = document.getElementById('team-roster-panel');
    if (rosterPanel.classList.contains('active') && !rosterPanel.contains(e.target) && !e.target.closest('.clickable-team')) {
        closeTeamRoster();
    }
});

document.getElementById('target').addEventListener('keypress', e => { if (e.key === 'Enter') executeScan(); });
document.getElementById('close-panel-btn').addEventListener('click', () => { isPanelOpen = false; hPanel.classList.remove('active'); closeTeamRoster(); });