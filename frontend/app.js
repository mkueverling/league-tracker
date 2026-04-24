const lTeam = document.getElementById('left-team');
const rTeam = document.getElementById('right-team');
const hPanel = document.getElementById('history-panel');
const scanLoader = document.getElementById('scan-loader');
const searchIcon = document.getElementById('search-icon');
let patch = "14.8.1"; 

let championMap = {};
let perksMap = {};
let summonerMap = {};
let liveTimerInterval = null; 

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
        
        const sumRes = await fetch(`https://ddragon.leagueoflegends.com/cdn/${patch}/data/en_US/summoner.json`);
        const sumData = await sumRes.json();
        for (let sumName in sumData.data) { summonerMap[sumData.data[sumName].key] = sumData.data[sumName].id; }
        
        const perksRes = await fetch("https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/perks.json");
        const perksData = await perksRes.json();
        perksData.forEach(perk => {
            let path = perk.iconPath.toLowerCase();
            perksMap[perk.id] = path.replace('/lol-game-data/assets/v1/', 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/');
        });

        const stylesRes = await fetch("https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/perkstyles.json");
        const stylesData = await stylesRes.json();
        stylesData.styles.forEach(style => {
            let path = style.iconPath.toLowerCase();
            perksMap[style.id] = path.replace('/lol-game-data/assets/v1/', 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/');
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
    if (["Winners Queue", "On Fire", "STOMP ANGLE?", "Winning", "HIGH SYNERGY"].includes(tag)) return "badge-positive";
    if (["Unlucky", "Losers Queue", "TILT SWAPPED", "YOU'RE COOKED", "FF ANGLE?", "Tilted", "SKILL ISSUE"].includes(tag)) return "badge-negative";
    if (tag === "OBSESSED")       return "badge-obsessed";
    if (tag === "CREATURE")       return "badge-creature";
    if (tag === "THREAT")         return "badge-threat";
    if (tag === "SECRET WEAPON")  return "badge-secret-weapon";
    if (tag === "THE DEV")        return "badge-dev";
    if (tag === "VIP")            return "badge-vip";
    if (tag === "PRO PLAYER")     return "badge-pro";
    if (["STREAMER", "CONTENT CREATOR"].includes(tag)) return "badge-creator";
    return "badge-neutral"; 
}

function getTagTooltip(tag) {
    const tips = {
        'PRO PLAYER':       'Active professional player on a roster',
        'STREAMER':         'Streams live on Twitch',
        'CONTENT CREATOR':  'YouTube content creator',
        'OBSESSED':         '3M+ mastery — Needs to touch grass immediately',
        'CREATURE':         '5M+ mastery — Absolute monster on this champion',
        'THREAT':           '1.5M+ mastery — OTP territory on this champion',
        'SECRET WEAPON':    'Low mastery on this account, but enormous across their other accounts',
        'THE DEV':          '👨‍💻 The guy who built this',
        'VIP':              '⭐ Personal friend',
        'Winners Queue':    '7+ game win streak',
        'On Fire':          '5+ game win streak',
        'Winning':          '3+ game win streak',
        'Losers Queue':     '7+ game loss streak',
        'Tilted':           '5+ game loss streak',
        'Unlucky':          '3+ game loss streak',
        "YOU'RE COOKED":    'Enemy on a hot streak with heavy mastery — pray',
        'FF ANGLE?':        'Enemy team mastery and win momentum strongly favored',
        'INSECURE':         'Streamer mode active — identity hidden by Riot',
        'HIGH SYNERGY':     'At least two players on this team play for the same pro team.',
        'SKILL ISSUE':      'This team has 50% or less total mastery compared to the enemy.'
    };
    return tips[tag] || null;
}

function computeTags(p) {
    if (p.tag === 'THE DEV') return ['THE DEV'];
    if (p.tag === 'VIP')     return ['VIP'];

    const tags = [];
    const hasTwitch  = p.socials && p.socials.Twitch;
    const hasYouTube = p.socials && p.socials.YouTube;

    if (p.team) tags.push('PRO PLAYER');

    if (hasTwitch && !hasYouTube) tags.push('STREAMER');
    if (hasYouTube) tags.push('CONTENT CREATOR');

    const tot_mast = p.total_mastery || 0;
    if (tot_mast >= 5_000_000) {
        tags.push('CREATURE');
    } else if (tot_mast >= 3_000_000) {
        tags.push('OBSESSED');
    } else if (tot_mast >= 1_500_000) {
        tags.push('THREAT');
    } else if (tot_mast >= 300000 && (p.current_mastery || 0) <= tot_mast * 0.3) {
        tags.push('SECRET WEAPON');
    }

    const computedTagSet = new Set(['THE DEV', 'VIP', 'OBSESSED', 'CREATURE', 'THREAT', 'SECRET WEAPON']);
    if (p.tag && !computedTagSet.has(p.tag)) tags.push(p.tag);

    return tags;
}

function renderTeamSummary(teamArray, side, teamTags) {
    let totalMastery = 0;
    teamArray.forEach(p => totalMastery += p.total_mastery || 0);
    const sideClass = side === 'ally' ? 'ally-card' : 'enemy-card';
    let tagHtml = teamTags.map(tag => {
        const tip = getTagTooltip(tag);
        const cls = `badge ${getBadgeClass(tag)}${tip ? ' tooltip-box' : ''}`;
        const tipAttr = tip ? ` data-tooltip="${tip}"` : '';
        return `<div class="${cls}"${tipAttr}>${tag}</div>`;
    }).join('');
    
    // --- NEW: Box-Model Flex Track Wrapper ---
    // Injecting summary-box-* classes directly onto the flex tracks forces the dashed 
    // box to permanently align with the player card columns, ignoring scaling issues.
    return `<div class="card summary-card ${sideClass}">
        <div class="row-content">
            <div class="identity-group"></div>
            <div class="mastery-group summary-box-left">
                <div class="mastery-label" style="color: var(--gold);">TEAM MASTERY</div>
                <div class="mastery-score">${formatMastery(totalMastery)}</div>
            </div>
            <div class="stats-group summary-box-mid"></div>
            <div class="tags-group summary-box-right">${tagHtml}</div>
        </div>
    </div>`;
}

function render(p, index) {
    const champName = championMap[p.championId] || "Unknown";
    const splashImg = `https://ddragon.leagueoflegends.com/cdn/img/champion/centered/${champName}_0.jpg`;
    const clickAction = p.is_streamer ? "" : `onclick='openHistory(${JSON.stringify(p).replace(/'/g, "&#39;")})'`;
    const searchInput = document.getElementById('target').value.trim().toLowerCase();
    const isTarget = p.riotId.toLowerCase() === searchInput;

    const isDev = p.tag === 'THE DEV';
    let cardEffectClass = '';
    
    if (isDev) {
        cardEffectClass = 'effect-the-dev';
    } else if (p.is_pro || p.is_creator) {
        cardEffectClass = 'effect-pro';
    }

    const roleCleaned = p.guessed_role || "fill";
    const isAlly = p.side === "ally";
    
    const roleBadgeHtml = isAlly ? `
        <div class="tooltip-box" data-tooltip="${roleCleaned.toUpperCase()}" style="position: absolute; top: 50%; right: calc(-0.5 * clamp(4vw, 8vw, 10vw)); transform: translate(50%, -50%); z-index: 20;">
            <img src="http://localhost:8000/images/roles/${roleCleaned}.png" style="width: 2.5rem; height: 2.5rem; opacity: 0.9; filter: drop-shadow(0 0.15rem 0.3rem rgba(0,0,0,0.7));" onerror="this.style.opacity='0'">
        </div>
    ` : '';

    const spell1 = summonerMap[p.spell1Id] || "SummonerFlash";
    const spell2 = summonerMap[p.spell2Id] || "SummonerFlash";
    const spell1Url = `https://ddragon.leagueoflegends.com/cdn/${patch}/img/spell/${spell1}.png`;
    const spell2Url = `https://ddragon.leagueoflegends.com/cdn/${patch}/img/spell/${spell2}.png`;
    const keystoneUrl = perksMap[p.primary_perk] || "";
    const subStyleUrl = perksMap[p.sub_style] || "";

    const loadoutsHtml = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; margin-right: 0.75rem; z-index: 2; align-items: center;">
            <img src="${spell1Url}" style="width: 1.4rem; height: 1.4rem; border-radius: 0.25rem; border: 0.06rem solid rgba(255,255,255,0.15); box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.5);" onerror="this.style.opacity='0'">
            <img src="${spell2Url}" style="width: 1.4rem; height: 1.4rem; border-radius: 0.25rem; border: 0.06rem solid rgba(255,255,255,0.15); box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.5);" onerror="this.style.opacity='0'">
            <img src="${keystoneUrl}" style="width: 1.4rem; height: 1.4rem; border-radius: 50%; border: 0.06rem solid rgba(255,255,255,0.15); box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.5); background: rgba(0,0,0,0.5);" onerror="this.style.opacity='0'">
            <img src="${subStyleUrl}" style="width: 1.4rem; height: 1.4rem; border-radius: 50%; border: 0.06rem solid rgba(255,255,255,0.15); box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.5); background: rgba(0,0,0,0.5);" onerror="this.style.opacity='0'">
        </div>
    `;

    if (p.is_streamer && !isTarget) {
        return `
        <div class="card ${p.side}-card unclickable streamer-mode-card" style="position: relative; animation-delay: ${index * 0.15}s;">
            ${roleBadgeHtml}
            <div class="card-bg-wrapper"><div class="champ-splash streamer-splash" style="background-image: url('${splashImg}')"></div></div>
            <div class="row-content">
                <div class="identity-group">
                    <div class="main-name" style="color: #55555e; font-style: italic;">Streamer mode</div>
                </div>
                <div class="mastery-group"></div>
                <div class="stats-group"></div>
                <div class="tags-group">
                    <div class="badge badge-neutral tooltip-box" data-tooltip="Streamer mode active — identity hidden by Riot">INSECURE</div>
                </div>
            </div>
        </div>`;
    }

    const rankHtml = p.ladder_rank ? `<div style="color: var(--text-muted); font-weight: 900; font-size: 0.8rem; margin-top: 0.15rem; letter-spacing: 0.06rem;">Rank: <span style="color: var(--gold);">#${p.ladder_rank}</span></div>` : '';
    const mantraHtml = p.mantra ? `<div class="mantra-text" style="margin-top: 0.2rem; color: var(--text-muted); font-size: 0.85rem;">— "${p.mantra}"</div>` : '';

    let identityHtml = '';
    if (isDev) {
        identityHtml = `
            <div class="identity-group-dev">
                <div class="dev-name-animated">${p.known_name || p.riotId.split('#')[0]}</div>
                <div class="riot-id-subtext">${p.riotId}</div>
                ${rankHtml}
                ${mantraHtml}
            </div>
        `;
    } else if (p.is_pro || p.is_creator) {
        identityHtml = `
            <div class="identity-group-pro">
                <div class="pro-name-gold">${p.known_name || p.riotId.split('#')[0]}</div>
                <div class="riot-id-subtext">${p.riotId}</div>
                ${rankHtml}
                ${mantraHtml}
            </div>
        `;
    } else {
        identityHtml = `
            <div class="riot-id-wrapper">
                <span class="main-name truncate-text">${p.known_name || p.riotId.split('#')[0]}</span>
                ${rankHtml}
                ${mantraHtml}
            </div>
        `;
    }

    let statsHtml = '';
    if (p.rank.toLowerCase() === 'unranked') {
        statsHtml = `<div class="stat-line" style="color: #7b7a8e; font-weight: 800; font-size: 0.9rem; text-transform: uppercase;">Unranked</div>`;
    } else {
        const rankPngUrl = `http://localhost:8000/images/ranks/${p.rank.toLowerCase()}.png`;
        statsHtml = `
            <div style="position: relative; display: flex; flex-direction: column; justify-content: center; height: 100%; width: 100%;">
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0.15; filter: grayscale(100%) brightness(0.1); transform: scale(1.5); background-image: url('${rankPngUrl}'); background-size: contain; background-position: center; background-repeat: no-repeat; pointer-events: none; z-index: 0;"></div>
                <div style="position: relative; z-index: 1;">
                    <div class="stat-line stat-highlight" style="margin-bottom: 0.25rem; font-size: 0.95rem;">
                        ${p.rank.toUpperCase()} <span class="stat-highlight">${p.lp || 0} LP</span>
                    </div>
                    <div class="stat-line">WR: <span class="stat-highlight">N/A</span></div>
                    <div class="stat-line">KDA: <span class="stat-highlight">N/A</span></div>
                </div>
            </div>
        `;
    }

    const computedTagList = computeTags(p);
    
    let masteryScoreClass = 'mastery-score';
    if (computedTagList.includes('OBSESSED') || p.tag === 'OBSESSED') {
        masteryScoreClass += ' obsessed-text';
    } else if (computedTagList.includes('CREATURE') || p.tag === 'CREATURE') {
        masteryScoreClass += ' creature-text';
    } else if (computedTagList.includes('THREAT') || p.tag === 'THREAT') {
        masteryScoreClass += ' threat-text';
    } else if (computedTagList.includes('SECRET WEAPON') || p.tag === 'SECRET WEAPON') {
        masteryScoreClass += ' secret-weapon-text';
    }

    const hasHiddenMastery = (p.total_mastery || 0) > (p.current_mastery || 0);
    const masteryLabelStyle = hasHiddenMastery ? 'color: var(--gold); text-shadow: 0 0 8px rgba(241, 196, 15, 0.4);' : '';

    let tagsHtml = computedTagList.map(tag => {
        const tip = getTagTooltip(tag);
        const cls = `badge ${getBadgeClass(tag)}${tip ? ' tooltip-box' : ''}`;
        const tipAttr = tip ? ` data-tooltip="${tip}"` : '';
        return `<div class="${cls}"${tipAttr}>${tag}</div>`;
    }).join('');

    let familiarTabHtml = '';
    if (p.familiar_stats && (p.familiar_stats.wins_with > 0 || p.familiar_stats.losses_with > 0 || p.familiar_stats.wins_against > 0 || p.familiar_stats.losses_against > 0)) {
        const f = p.familiar_stats;
        const totalWith = parseInt(f.wins_with) + parseInt(f.losses_with);
        const totalAgainst = parseInt(f.wins_against) + parseInt(f.losses_against);
        
        let textArr = [];
        if (totalWith > 0) {
            const wrWith = Math.round((parseInt(f.wins_with) / totalWith) * 100);
            textArr.push(`<span style="color:var(--blue);">W/ ${totalWith} <span style="opacity:0.6; font-size:0.65rem;">(${wrWith}%)</span></span>`);
        }
        if (totalAgainst > 0) {
            const wrAgainst = Math.round((parseInt(f.wins_against) / totalAgainst) * 100);
            textArr.push(`<span style="color:var(--red);">VS ${totalAgainst} <span style="opacity:0.6; font-size:0.65rem;">(${wrAgainst}%)</span></span>`);
        }
        
        const tip = "Based on matches stored in the database across all known accounts. W/ = Matches played on same team. VS = Matches against each other.";
        familiarTabHtml = `
            <div class="familiar-tab tooltip-box" data-tooltip="${tip}">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2.5" style="margin-right: 6px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                ${textArr.join(' <span style="color:#404048; margin: 0 6px;">|</span> ')}
            </div>
        `;
    }

    return `
        <div class="card ${p.side}-card ${cardEffectClass}" style="position: relative; animation-delay: ${index * 0.15}s;" ${clickAction}>
            ${familiarTabHtml}
            ${roleBadgeHtml}
            <div class="card-bg-wrapper"><div class="champ-splash" style="background-image: url('${splashImg}')"></div></div>
            <div class="row-content">
                ${loadoutsHtml}
                <div class="identity-group">${identityHtml}</div>
                <div class="mastery-group tooltip-box" style="border-left: 0.06rem solid rgba(255, 255, 255, 0.08); border-right: 0.06rem solid rgba(255, 255, 255, 0.08);" data-tooltip="${formatMastery(p.current_mastery)} on this account, ${formatMastery(p.total_mastery)} total across all connected accounts.">
                    <div class="mastery-label" style="${masteryLabelStyle}">True Mastery</div>
                    <div class="${masteryScoreClass}">${formatMastery(p.total_mastery)}</div>
                </div>
                <div class="stats-group">${statsHtml}</div>
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

        if (liveTimerInterval) clearInterval(liveTimerInterval);

        let currentSeconds = Math.max(0, liveData.game_length || 0);

        const updateBanner = (seconds) => {
            const liveMinutes = Math.floor(seconds / 60);
            const liveSeconds = seconds % 60;
            const liveDurationStr = `${liveMinutes}:${liveSeconds.toString().padStart(2, '0')}`;

            document.getElementById('intel-text').innerHTML = `
                <span class='intel-accent'>LIVE GAME:</span> 
                Match in progress — <span style="color: var(--blue); font-weight: 800;">${liveDurationStr}</span>
            `;
        };

        updateBanner(currentSeconds);
        document.getElementById('intel-banner').style.display = 'flex';

        liveTimerInterval = setInterval(() => {
            currentSeconds++;
            updateBanner(currentSeconds);
        }, 1000);

        let allySummaryTags = [];
        let enemySummaryTags = [];

        if (liveData.ally_synergy) allySummaryTags.push("HIGH SYNERGY");
        if (liveData.enemy_synergy) enemySummaryTags.push("HIGH SYNERGY");

        const getNormMast = (team) => {
            let t = 0, k = 0;
            team.forEach(p => { if(!p.is_streamer) { t += (p.total_mastery || 0); k++; } });
            return k > 0 ? (t / k) * 5 : 0;
        };
        const aNorm = getNormMast(liveData.allies);
        const eNorm = getNormMast(liveData.enemies);

        if (aNorm > 0 && eNorm > 0) {
            if (aNorm <= eNorm / 2) allySummaryTags.push("SKILL ISSUE");
            if (eNorm <= aNorm / 2) enemySummaryTags.push("SKILL ISSUE");
        }

        if (liveData.ff_angle) enemySummaryTags.push("FF ANGLE?");

        lTeam.innerHTML = renderTeamSummary(liveData.allies, 'ally', allySummaryTags) + liveData.allies.map((p, i) => render(p, i)).join('');
        rTeam.innerHTML = renderTeamSummary(liveData.enemies, 'enemy', enemySummaryTags) + liveData.enemies.map((p, i) => render(p, i)).join('');
    }catch (e) {
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
    
    let idHtml = p.riotId;
    if (p.ladder_rank) {
        idHtml += `<div style="color: var(--text-muted); font-weight: 900; margin-top: 4px; letter-spacing: 1px; font-size: 1.1rem;">Rank: <span style="color: var(--gold);">#${p.ladder_rank}</span></div>`;
    }
    document.getElementById('panel-riot-id').innerHTML = idHtml;

    const imgElem = document.getElementById('panel-pro-img');
    const heroContentElem = document.querySelector('.sidebar-hero-content');
    if (p.real_img) {
        imgElem.src = p.real_img; imgElem.style.display = 'block';
        if (heroContentElem) heroContentElem.classList.remove('no-image');
    } else {
        imgElem.style.display = 'none'; imgElem.src = '';
        if (heroContentElem) heroContentElem.classList.add('no-image');
    }

    let bioDetails = [];
    if (p.nationality && flagMap[p.nationality]) bioDetails.push(`<span class="flag-text">${flagMap[p.nationality]}</span>`);
    if (p.role) {
        let roleCleaned = p.role.toLowerCase().trim();
        if (roleCleaned === 'adc') roleCleaned = 'bot';
        if (roleCleaned === 'jungler') roleCleaned = 'jungle';
        bioDetails.push(`<img src="http://localhost:8000/images/roles/${roleCleaned}.png" class="role-icon-img" onerror="this.style.display='none'" title="${p.role}">`);
    }
    if (p.team) {
        const safeTeam = p.team.replace(/'/g, "\\'");
        const safeLogo = p.team_logo ? p.team_logo.replace(/'/g, "\\'") : '';
        bioDetails.push(`<span class="clickable-team" onclick="openTeamRoster('${safeTeam}', '${safeLogo}')">${p.team_logo ? `<img src="${p.team_logo}" class="team-icon-img">` : ''}${p.team}</span>`);
    }

    let finalIdentityArr = [];
    if (p.real_name) finalIdentityArr.push(p.real_name.trim());
    if (p.birthday && p.birthday !== "None") {
        const age = Math.abs(new Date(Date.now() - new Date(p.birthday).getTime()).getUTCFullYear() - 1970);
        if (age > 0 && age < 100) finalIdentityArr.push(`Age: ${age}`);
    }
    if (finalIdentityArr.length > 0) bioDetails.push(`<span style="color:var(--text-main); font-weight: 900;">${finalIdentityArr.join(' | ')}</span>`);
    document.getElementById('panel-bio-details').innerHTML = bioDetails.join('<span style="margin: 0 8px; color:var(--border);">|</span>');

    let socialsHtml = '';
    const socialImgMap = {"Twitch": "twitch", "Twitter": "x", "YouTube": "youtube"};
    if (p.socials) {
        for (const [platform, handle] of Object.entries(p.socials)) {
            const url = handle.startsWith('http') ? handle : `https://${platform.toLowerCase()}.com/${handle.replace('@', '')}`;
            socialsHtml += `<a href="${url}" target="_blank" class="panel-social-icon tooltip-box" data-tooltip="${platform}"><img src="http://localhost:8000/images/socials/${socialImgMap[platform] || platform.toLowerCase()}.png" class="social-icon-img"></a>`;
        }
    }
    if (p.leaguepedia) socialsHtml += `<a href="${p.leaguepedia}" target="_blank" class="panel-social-icon tooltip-box" data-tooltip="Leaguepedia"><img src="http://localhost:8000/images/socials/leaguepedia.png" class="social-icon-img"></a>`;
    document.getElementById('panel-socials').innerHTML = socialsHtml ? `<div style="margin-top: 15px;"><div style="font-size: 0.75rem; color: #7b7a8e; text-transform: uppercase; font-weight: 800; margin-bottom: 8px;">Socials</div><div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center;">${socialsHtml}</div></div>` : '';

    let smurfsHtml = '';
    if (p.smurfs && p.smurfs.length > 0) {
        smurfsHtml = `<div style="margin-top: 15px;"><div style="font-size: 0.75rem; color: #7b7a8e; text-transform: uppercase; font-weight: 800; margin-bottom: 8px;">Known Accounts</div><div style="display: flex; flex-wrap: wrap; gap: 6px;">${p.smurfs.map(s => `<span style="background: #282830; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #3e3e4a; color: var(--text-main);">${s}</span>`).join('')}</div></div>`;
    }

    let familiarHtml = '';
    if (p.familiar_stats && (p.familiar_stats.wins_with > 0 || p.familiar_stats.losses_with > 0 || p.familiar_stats.wins_against > 0 || p.familiar_stats.losses_against > 0)) {
        const f = p.familiar_stats;
        const totalWith = parseInt(f.wins_with) + parseInt(f.losses_with);
        const totalAgainst = parseInt(f.wins_against) + parseInt(f.losses_against);
        
        let statBadges = [];
        if (totalWith > 0) {
            const wrWith = Math.round((parseInt(f.wins_with) / totalWith) * 100);
            statBadges.push(`<span style="background: #282830; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #3e3e4a; color: var(--text-main);">Played With: ${totalWith} (${wrWith}% WR)</span>`);
        }
        if (totalAgainst > 0) {
            const wrAgainst = Math.round((parseInt(f.wins_against) / totalAgainst) * 100);
            statBadges.push(`<span style="background: #282830; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #3e3e4a; color: var(--text-main);">Played Against: ${totalAgainst} (${wrAgainst}% WR)</span>`);
        }
        
        familiarHtml = `<div style="margin-top: 15px;"><div style="font-size: 0.75rem; color: #7b7a8e; text-transform: uppercase; font-weight: 800; margin-bottom: 8px;">Personal Match History</div><div style="display: flex; flex-wrap: wrap; gap: 6px;">${statBadges.join('')}</div></div>`;
    }

    document.getElementById('panel-smurfs').innerHTML = smurfsHtml + familiarHtml;
    document.getElementById('history-loading').innerHTML = `<div class="loader-ring" style="display:block; margin: 40px auto;"></div>`;
    await fetchAndRenderMatches(0);
}

async function fetchAndRenderMatches(offset) {
    const loadingDiv = document.getElementById('history-loading');
    try {
        const cacheKey = `${currentHistoryPuuid}_${offset}`;
        let matchData = historyCache[cacheKey] || await (await fetch(`http://localhost:8000/api/history/${currentHistoryPuuid}?start=${offset}&count=5`)).json();
        historyCache[cacheKey] = matchData;
        
        const historyHtml = matchData.map(m => {
            const color = m.isWin ? 'var(--blue)' : 'var(--red)';
            const minutes = Math.floor(m.duration / 60);
            const seconds = m.duration % 60;
            const durationStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;

            const finalItemsHtml = `<div style="display:flex; gap:2px; align-items:center;">${m.items.slice(0, 6).map(id => id > 0 ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${id}.png" style="width: 30px; height: 30px; border-radius: 4px;">` : `<div style="width: 30px; height: 30px; border-radius: 4px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05);"></div>`).join('')} <div style="width:1px; height:24px; background:#3e3e4a; margin: 0 4px;"></div> ${m.items[6] > 0 ? `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${m.items[6]}.png" style="width: 30px; height: 30px; border-radius: 50%;">` : `<div style="width: 30px; height: 30px; border-radius: 50%; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05);"></div>`}</div>`;

            return `
            <div class="match-card" style="border-left-color: ${color}" onclick="toggleBuildPath(this, '${m.matchId}', '${m.puuid}', '${encodeURIComponent(JSON.stringify(m.runes))}')">
                <div style="display: flex; gap: 15px; align-items: center; width: 100%;">
                    <div class="match-champs tooltip-box" data-tooltip="Laned against ${m.oppChamp}" style="flex-shrink: 0;">
                        <img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/champion/${m.myChamp}.png" class="match-champ-icon">
                        ${m.oppChamp !== "Unknown" ? `<span style="font-size:0.7rem; color:var(--text-muted); font-weight:bold; margin: 0 4px;">VS</span><img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/champion/${m.oppChamp}.png" class="match-champ-icon opp-champ">` : ''}
                    </div>
                    <div style="display: flex; flex-direction: column; flex: 1; gap: 8px; min-width: 0;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; width: 100%;">
                            <div class="match-details" style="display: flex; flex-direction: column; gap: 3px;">
                                <div style="display: flex; align-items: baseline; gap: 8px;">
                                    <span style="color: ${color}; font-weight: 900; font-size: 1rem; line-height: 1;">${m.result}</span>
                                    <span style="color: var(--text-muted); font-size: 0.75rem;">${m.time} • ${durationStr}</span>
                                </div>
                                <div style="font-family: monospace; color: var(--text-main); font-size: 1rem; font-weight: bold; line-height: 1;">
                                    ${m.kda} <span style="color: var(--red); font-size: 0.75rem; font-family: 'Roboto', sans-serif; font-weight: 800; margin-left: 4px;">(${m.kp} KP)</span>
                                </div>
                            </div>
                            <svg class="expand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </div>
                        ${finalItemsHtml}
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
        container.style.display = 'none'; cardElem.classList.remove('expanded'); return;
    }
    container.style.display = 'block'; cardElem.classList.add('expanded');
    if (container.innerHTML !== '') return; 
    container.innerHTML = '<div class="loader-ring" style="width: 20px; height: 20px; margin: 10px auto; display: block;"></div>';
    
    try {
        const timeline = timelineCache[matchId] || await (await fetch(`http://localhost:8000/api/timeline/${matchId}/${puuid}`)).json();
        timelineCache[matchId] = timeline; 
        const r = JSON.parse(decodeURIComponent(runesEncoded));
        const safeR = (id, sz, cls="") => id ? `<img src="${perksMap[id]}" style="width:${sz}px; height:${sz}px; ${cls}">` : '';
        const ignored = new Set([2003, 2055, 2031, 2033, 3340, 3364, 3363, 2010]);
        const batches = [];
        timeline.purchases.forEach(e => {
            if (ignored.has(e.itemId)) return;
            const m = Math.floor(e.timestamp / 60000);
            if (!batches.length || batches[batches.length-1].m !== m) batches.push({m:m, items:[e.itemId]});
            else batches[batches.length-1].items.push(e.itemId);
        });

        container.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:25px; margin-top:5px;">
                <div><div class="section-title">Recall Timeline</div><div style="display:flex; flex-wrap:wrap; gap:6px;">${batches.map(b => `<div style="display:flex; flex-direction:column; align-items:center; gap:4px;"><div style="display:flex; gap:4px; background:#282830; padding:6px; border-radius:4px; border: 1px solid #3e3e4a;">${b.items.map(id => `<img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${id}.png" style="width:32px; height:32px; border-radius:3px;">`).join('')}</div><span style="font-size:11px; color:#7b7a8e; font-weight:bold;">${b.m}m</span></div>`).join('<div style="color:#666; font-size:20px; font-weight:bold; margin-top:8px;">›</div>') || 'No items.'}</div></div>
                <div><div class="section-title">Skill Sequence</div><div style="display:flex; gap:4px; flex-wrap:wrap;">${timeline.skills.slice(0, 18).map(s => `<div class="seq-badge is-${{1:'q', 2:'w', 3:'e', 4:'r'}[s]}">${{1:'Q', 2:'W', 3:'E', 4:'R'}[s]}</div>`).join('')}</div></div>
                <div><div class="section-title">Runes & Stats</div><div class="rune-box-full"><div class="rune-column">${safeR(r.primaryPerks[0], 52)}<div style="display:flex; gap:8px;">${r.primaryPerks.slice(1).map(p => safeR(p, 36, "opacity:0.9")).join('')}</div></div><div class="rune-column"><div style="display:flex; gap:8px; margin-top: 14px;">${r.subPerks.map(p => safeR(p, 36, "opacity:0.9")).join('')}</div></div><div class="rune-column stat-column">${r.statPerks.map(p => safeR(p, 28, "filter:brightness(1.2)")).join('')}</div></div></div>
            </div>`;
    } catch (e) { container.innerHTML = '<div style="color:var(--red); text-align:center;">Failed.</div>'; }
}

async function openTeamRoster(teamName, teamLogo) {
    const panel = document.getElementById('team-roster-panel');
    const content = document.getElementById('roster-content');
    document.getElementById('roster-team-name').innerHTML = `${teamLogo ? `<img src="${teamLogo}" style="height: 22px; vertical-align: middle; margin-right: 8px;">` : ''}${teamName}`;
    content.innerHTML = '<div class="loader-ring" style="margin: 30px auto; display: block;"></div>';
    panel.style.display = 'flex'; setTimeout(() => panel.classList.add('active'), 10);
    try {
        const data = await (await fetch(`http://localhost:8000/api/team/${encodeURIComponent(teamName)}`)).json();
        content.innerHTML = data.roster.map(player => `<div class="roster-player-card">${player.image ? `<img src="${player.image}" class="roster-player-img">` : '<div class="roster-player-img"></div>'}<div class="roster-player-info"><div class="roster-player-name">${(player.nationality && flagMap[player.nationality]) ? `<span style="font-size:1.1rem; margin-right:6px;">${flagMap[player.nationality]}</span>` : ''}${player.name}</div><div class="roster-player-role">${player.role ? `<img src="http://localhost:8000/images/roles/${player.role.toLowerCase().replace('adc','bot').replace('jungler','jungle')}.png" style="height:14px; margin-right:6px;">` : ''}${player.role || 'Player'}</div></div></div>`).join('');
    } catch (e) { content.innerHTML = '<div style="color:var(--red); text-align:center;">Failed.</div>'; }
}

function closeTeamRoster() {
    const panel = document.getElementById('team-roster-panel');
    panel.classList.remove('active'); setTimeout(() => panel.style.display = 'none', 300);
}

document.addEventListener('click', (e) => { 
    if (hPanel.classList.contains('active') && !hPanel.contains(e.target) && !e.target.closest('.card') && !e.target.closest('.team-roster-panel')) hPanel.classList.remove('active');
    if (document.getElementById('team-roster-panel').classList.contains('active') && !document.getElementById('team-roster-panel').contains(e.target) && !e.target.closest('.clickable-team')) closeTeamRoster();
});

document.getElementById('target').addEventListener('keypress', e => { if (e.key === 'Enter') executeScan(); });
document.getElementById('close-panel-btn').addEventListener('click', () => { hPanel.classList.remove('active'); closeTeamRoster(); });