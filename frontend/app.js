const lTeam = document.getElementById('left-team');
const rTeam = document.getElementById('right-team');
const hPanel = document.getElementById('history-panel');
const scanLoader = document.getElementById('scan-loader');
const searchIcon = document.getElementById('search-icon');
const themeToggle = document.getElementById('theme-toggle');
let patch = "14.8.1"; 

let isPanelOpen = false;
const historyCache = {};

// --- THEME TOGGLE LOGIC ---
themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light-mode');
    if (document.body.classList.contains('light-mode')) {
        themeToggle.innerText = '🌙';
    } else {
        themeToggle.innerText = '☀️';
    }
});

const CHAMP_ROLES = { 
    "Aatrox": "TOP", "Darius": "TOP", "Akali": "MIDDLE", "Azir": "MIDDLE", 
    "Lucian": "BOTTOM", "Draven": "BOTTOM", "Yuumi": "UTILITY", "Nautilus": "UTILITY" 
};

const TAG_LOGIC = {
    "On Fire": "Won 3 games in a row",
    "Winners Queue": "Won 5 games in a row",
    "Unlucky": "Lost 3 games in a row",
    "Losers Queue": "Lost 5 games in a row",
    "YOU'RE COOKED": "Winners Queue + over 200,000 Real Mastery"
};

const mockLobbyData = {
    allies: [
        { puuid: "a4", riotId: "ADC Main#EUW", spell1: 4, spell2: 7, is_streamer: false, champName: "Lucian", is_pro: false, pro_name: null, rank: "diamond", division: "II", lp: 45, current_mastery: 450000, total_mastery: 450000, tag: "Winners Queue", side: "ally", avatar: "https://i.imgur.com/8x8Mv7A.jpg", socials: { twitch: "Twitch", twitter: "Twitter" }, smurfs: ["ADC Alt 1", "EUW Smurf"] },
        { puuid: "a2", riotId: "Oner#T1", spell1: 4, spell2: 11, is_streamer: false, champName: "LeeSin", is_pro: true, pro_name: "Oner", rank: "challenger", division: null, lp: 850, current_mastery: 400000, total_mastery: 2100000, tag: "On Fire", side: "ally" },
        { puuid: "a5", riotId: "Autofilled Support", spell1: 4, spell2: 3, is_streamer: true, champName: "Yuumi", is_pro: false, pro_name: null, rank: "unranked", division: null, current_mastery: 0, total_mastery: 0, tag: null, side: "ally" },
        { puuid: "a1", riotId: "Zeus#T1", spell1: 4, spell2: 12, is_streamer: false, champName: "Aatrox", is_pro: true, pro_name: "Zeus", rank: "challenger", division: null, lp: 1120, current_mastery: 200000, total_mastery: 1500000, tag: "YOU'RE COOKED", side: "ally" },
        { puuid: "a3", riotId: "Faker#T1", spell1: 4, spell2: 14, is_streamer: false, champName: "Akali", is_pro: true, pro_name: "Faker", rank: "challenger", division: null, lp: 1420, current_mastery: 150000, total_mastery: 2500000, tag: "YOU'RE COOKED", side: "ally", avatar: "https://am-a.akamaihd.net/image?f=https://ddragon.leagueoflegends.com/cdn/14.8.1/img/profileicon/5424.png", socials: { twitch: "faker", youtube: "T1 Faker" }, smurfs: ["Hide on bush", "T1 Faker"] }
    ],
    enemies: [
        { puuid: "e5", riotId: "NoVision#GG", spell1: 4, spell2: 14, is_streamer: false, champName: "Nautilus", is_pro: false, pro_name: null, rank: "emerald", division: "IV", lp: 12, current_mastery: 50000, total_mastery: 50000, tag: "Unlucky", side: "enemy" },
        { puuid: "e1", riotId: "TopDiff", spell1: 4, spell2: 6, is_streamer: true, champName: "Darius", is_pro: false, pro_name: null, rank: "unranked", division: null, current_mastery: 0, total_mastery: 0, tag: null, side: "enemy" },
        { puuid: "e3", riotId: "Chovy#GENG", spell1: 4, spell2: 12, is_streamer: false, champName: "Azir", is_pro: true, pro_name: "Chovy", rank: "challenger", division: null, lp: 1600, current_mastery: 90000, total_mastery: 1900000, tag: "Winners Queue", side: "enemy" },
        { puuid: "e2", riotId: "Jgl Diff#NA", spell1: 11, spell2: 4, is_streamer: false, champName: "Nidalee", is_pro: false, pro_name: null, rank: "master", division: null, lp: 250, current_mastery: 800000, total_mastery: 800000, tag: "Winners Queue", side: "enemy" },
        { puuid: "e4", riotId: "ToxicGuy#123", spell1: 4, spell2: 1, is_streamer: false, champName: "Draven", is_pro: false, pro_name: null, rank: "platinum", division: "I", lp: 99, current_mastery: 1200000, total_mastery: 1200000, tag: "Losers Queue", side: "enemy" }
    ]
};

const mockMatchHistory = [
    { result: "VICTORY", champ: "Match 1", kda: "12 / 2 / 8", time: "28:45", color: "var(--blue)", items: [{id: 3152, name: "Hextech Rocketbelt"}] }
];

function assignAndSortRoles(teamArray) {
    let sorted = new Array(5).fill(null);
    let unassigned = [];
    teamArray.forEach(p => {
        if (p.spell1 === 11 || p.spell2 === 11) sorted[1] = p;
        else if (CHAMP_ROLES[p.champName] === "UTILITY" && !sorted[4]) sorted[4] = p;
        else if (CHAMP_ROLES[p.champName] === "BOTTOM" && !sorted[3]) sorted[3] = p;
        else if (CHAMP_ROLES[p.champName] === "MIDDLE" && !sorted[2]) sorted[2] = p;
        else if (CHAMP_ROLES[p.champName] === "TOP" && !sorted[0]) sorted[0] = p;
        else unassigned.push(p);
    });
    for (let i = 0; i < 5; i++) if (!sorted[i]) sorted[i] = unassigned.shift();
    return sorted.filter(p => p !== null && p !== undefined);
}

function render(p, index) {
    const splashImg = `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${p.champName}_0.jpg`;
    const rankImg = (p.rank && p.rank !== 'unranked') ? `url('ranks/${p.rank}.png')` : 'none';
    
    let rankDisplay = "";
    if (p.rank && p.rank !== 'unranked') {
        const div = p.division ? ` ${p.division}` : "";
        rankDisplay = `${p.rank}${div} ${p.lp || 0} LP`;
    }

    const clickAction = p.is_streamer ? "" : `onclick='openHistory(${JSON.stringify(p).replace(/'/g, "&#39;")})'`;
    const unclickableClass = p.is_streamer ? 'unclickable' : '';
    const searcherClass = p.is_searcher ? 'searcher-card' : '';

    let nameHtml = "";
    if (p.is_streamer) {
        nameHtml = `<div class="main-name">HIDDEN</div>`;
    } else if (p.is_pro) {
        nameHtml = `
            <div class="pro-container">
                <span class="pro-label">${p.pro_name}</span>
                <span class="smurf-tag">${p.riotId.split('#')[0]}</span>
            </div>`;
    } else {
        nameHtml = `<div class="main-name">${p.riotId ? p.riotId.split('#')[0] : 'Unknown'}</div>`;
    }

    let badgesHtml = '';
    if (p.is_pro) {
        badgesHtml += `<div class="badge badge-pro tooltip-box" data-tooltip="Verified Professional Player">PRO</div>`;
    }

    if (!p.is_streamer) {
        if (p.tag) {
            const cookedClass = p.tag.includes("COOKED") ? "badge-cooked" : "";
            const hoverText = TAG_LOGIC[p.tag] || "";
            badgesHtml += `<div class="badge ${cookedClass} tooltip-box" data-tooltip="${hoverText}">${p.tag}</div>`;
        }
        if (p.has_ff_angle) {
            badgesHtml += `<div class="badge badge-ff tooltip-box" data-tooltip="Enemy team has 2+ Winners Queue or 5+ On Fire">FF ANGLE</div>`;
        }
    }

    return `
        <div class="card ${p.side === 'ally' ? 'ally-card' : 'enemy-card'} ${p.is_pro ? 'pro-highlight' : ''} ${unclickableClass} ${searcherClass}" 
             style="animation-delay: ${index * 0.2}s;" 
             ${clickAction}>
            
            <div class="card-bg-wrapper">
                <div class="champ-splash" style="background-image: url('${splashImg}')"></div>
                <div class="rank-bg" style="background-image: ${rankImg}"></div>
            </div>

            <div class="details">
                ${nameHtml}
                
                ${!p.is_streamer ? `
                    <div class="mastery-info tooltip-box" data-tooltip="Total mastery points across all known public accounts">Real Mastery: <span style="color:#2ecc71; font-weight:bold;">${p.total_mastery.toLocaleString()}</span></div>
                    <div class="badge-container">${badgesHtml}</div>
                ` : `
                    <div style="color: var(--text-muted); font-weight: 800; font-size: 0.8rem; margin-top: 5px;">STREAMER MODE</div>
                    <div class="badge-container"><div class="badge badge-insecure tooltip-box" data-tooltip="Player is hiding their name in Streamer Mode">INSECURE</div></div>
                `}
            </div>
            ${!p.is_streamer ? `<div class="rank-lp-text">${rankDisplay}</div>` : ''}
        </div>`;
}

function fireLaser() {
    const searchBox = document.getElementById('search-container');
    const targetCard = document.querySelector('.searcher-card');
    const svgCanvas = document.getElementById('laser-canvas');
    const laser = document.getElementById('laser-beam');

    if (!searchBox || !targetCard || !laser) return;

    const delaySeconds = parseFloat(targetCard.style.animationDelay) || 0;
    const boxRect = searchBox.getBoundingClientRect();
    const cardRect = targetCard.getBoundingClientRect();
    const svgRect = svgCanvas.getBoundingClientRect();

    const isAlly = targetCard.classList.contains('ally-card');

    const boxCenterX = (boxRect.left + boxRect.width / 2) - svgRect.left;
    const boxCenterY = (boxRect.top + boxRect.height / 2) - svgRect.top;
    const cardCenterY = (cardRect.top + cardRect.height / 2) - svgRect.top;

    let startX, startY, endX, endY, pathString;

    endX = isAlly ? (cardRect.right - svgRect.left) : (cardRect.left - svgRect.left);
    endY = cardCenterY;

    if (Math.abs(boxCenterY - cardCenterY) < 30) {
        startX = isAlly ? (boxRect.left - svgRect.left) : (boxRect.right - svgRect.left);
        startY = boxCenterY;
        pathString = `M ${startX} ${startY} L ${endX} ${endY}`;
    } else {
        const isAbove = cardCenterY < boxCenterY;
        startX = boxCenterX;
        startY = isAbove ? (boxRect.top - svgRect.top) : (boxRect.bottom - svgRect.top);
        pathString = `M ${startX} ${startY} L ${startX} ${endY} L ${endX} ${endY}`;
    }

    const color = isAlly ? "var(--blue)" : "var(--red)";
    laser.style.stroke = color;
    laser.style.filter = `drop-shadow(0 0 3px ${color})`; 
    laser.setAttribute('d', pathString);
    
    laser.style.transition = 'none';
    const length = laser.getTotalLength();
    laser.style.strokeDasharray = length;
    laser.style.strokeDashoffset = length;
    laser.style.opacity = '0.35';

    void laser.offsetWidth; 

    laser.style.transition = `stroke-dashoffset 1.2s cubic-bezier(0.2, 0.8, 0.2, 1) ${delaySeconds}s`;
    laser.style.strokeDashoffset = '0';
}

window.addEventListener('resize', fireLaser);


async function executeScan() {
    const rawQuery = document.getElementById('target').value.trim();
    if(!rawQuery.includes('#')) return;
    const query = rawQuery.toLowerCase();

    searchIcon.style.display = 'none';
    scanLoader.style.display = 'block';
    
    lTeam.innerHTML = '';
    rTeam.innerHTML = '';
    const laser = document.getElementById('laser-beam');
    if(laser) {
        laser.style.transition = 'none';
        laser.style.opacity = '0';
        laser.setAttribute('d', '');
    }

    await new Promise(r => setTimeout(r, 1200));

    [...mockLobbyData.allies, ...mockLobbyData.enemies].forEach(p => {
        if (p.riotId && p.riotId.toLowerCase() === query) {
            p.is_searcher = true;
        } else {
            p.is_searcher = false;
        }
    });

    let wQueueCount = 0;
    let onFireCount = 0;
    mockLobbyData.enemies.forEach(e => {
        if (e.tag === "Winners Queue" || e.tag === "YOU'RE COOKED") wQueueCount++;
        if (e.tag === "On Fire") onFireCount++;
    });
    const ffConditionMet = (wQueueCount >= 2) || ((onFireCount + wQueueCount) >= 5);

    mockLobbyData.allies.forEach(p => { 
        if (p.is_searcher) p.has_ff_angle = ffConditionMet; 
    });

    const sortedAllies = assignAndSortRoles(mockLobbyData.allies);
    const sortedEnemies = assignAndSortRoles(mockLobbyData.enemies);

    lTeam.innerHTML = sortedAllies.map((p, index) => render(p, index)).join('');
    rTeam.innerHTML = sortedEnemies.map((p, index) => render(p, index)).join('');

    scanLoader.style.display = 'none';
    searchIcon.style.display = 'block';

    setTimeout(fireLaser, 50);
}

// Side Panel Logic
async function openHistory(p) {
    if (!p.puuid || p.is_streamer) return; 
    isPanelOpen = true;
    hPanel.classList.add('active');
    
    document.getElementById('panel-player-name').innerText = p.pro_name || p.riotId.split('#')[0];
    document.getElementById('panel-riot-id').innerText = p.riotId;
    
    let profileHtml = "";
    if (p.avatar || p.socials || p.smurfs) {
        const avatarImg = p.avatar ? `<img src="${p.avatar}" class="panel-avatar">` : '';
        
        let socialsHtml = "";
        if (p.socials) {
            for (const [platform, link] of Object.entries(p.socials)) {
                socialsHtml += `<a href="#" class="panel-social-link">${platform}</a>`;
            }
        }
        
        let smurfsHtml = "";
        if (p.smurfs && p.smurfs.length > 0) {
            smurfsHtml = `<div class="panel-smurfs">Known Accounts: ` + p.smurfs.map(s => `<span>${s}</span>`).join('') + `</div>`;
        }

        profileHtml = `
            <div class="panel-profile-container">
                ${avatarImg}
                <div>
                    <div class="panel-socials">${socialsHtml}</div>
                    ${smurfsHtml}
                </div>
            </div>`;
    }
    
    document.getElementById('panel-profile-section').innerHTML = profileHtml;
    
    const loadingDiv = document.getElementById('history-loading');

    if (historyCache[p.puuid]) { 
        loadingDiv.innerHTML = historyCache[p.puuid]; 
        return; 
    }

    loadingDiv.innerHTML = `<div style="color: var(--text-muted); font-style: italic; text-align: center; margin-top: 50px; animation: pulse 1s infinite;">Fetching Riot Match Database...</div>`;
    
    await new Promise(r => setTimeout(r, 800));
    
    // Notice inline styles swapped for variables here!
    const historyHtml = mockMatchHistory.map(match => {
        const itemsHtml = match.items.map(item => `<div class="item-slot" data-tooltip="${item.name}"><img src="https://ddragon.leagueoflegends.com/cdn/${patch}/img/item/${item.id}.png" alt="${item.name}"></div>`).join('');
        return `<div style="background: var(--card); border-left: 4px solid ${match.color}; padding: 15px; margin-bottom: 12px; border-radius: 4px; box-shadow: 0 4px 10px var(--shadow);">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: ${match.color}; font-weight: 900; font-size: 0.85rem; letter-spacing: 1px;">${match.result}</span>
                <span style="color: var(--text-muted); font-size: 0.8rem; font-family: monospace;">${match.time}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 800; font-size: 1.2rem;">${p.champName}</span>
                <span style="font-family: monospace; color: var(--text-muted); font-size: 1rem;">${match.kda}</span>
            </div>
            <div class="item-row">${itemsHtml}</div>
        </div>`;
    }).join('');

    historyCache[p.puuid] = historyHtml;
    loadingDiv.innerHTML = historyHtml;
}

document.getElementById('target').addEventListener('keypress', e => { 
    if (e.key === 'Enter') executeScan(); 
});

document.getElementById('close-panel-btn').addEventListener('click', () => { 
    isPanelOpen = false; 
    hPanel.classList.remove('active'); 
});

document.addEventListener('click', (event) => {
    if (isPanelOpen && !hPanel.contains(event.target) && !event.target.closest('.card')) { 
        isPanelOpen = false; 
        hPanel.classList.remove('active'); 
    }
});