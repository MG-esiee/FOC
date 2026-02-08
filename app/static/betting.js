
class BettingSystem {
    constructor() {
        this.selections = [];
        this.stake = 10;
        this.sidebar = null;
        this.init();
    }

    init() {
        this.createSidebar();
        this.createFloatButton();
        this.loadSelections();
        this.attachOddsEvents();
        console.log('🚀 [FOC Betting] Système initialisé avec persistance');
    }

    createSidebar() {
        const sidebar = document.createElement('div');
        sidebar.className = 'bet-sidebar';
        sidebar.id = 'bet-sidebar';
        sidebar.innerHTML = `
            <div class="bet-sidebar-header">
                <h3>Mon Panier</h3>
                <button class="close-sidebar" onclick="bettingSystem.closeSidebar()">×</button>
            </div>
            <div class="bet-selections" id="bet-selections">
                <div class="bet-empty" id="bet-empty">
                    <p>🎯 Aucune sélection</p>
                </div>
            </div>
            <div class="bet-summary" id="bet-summary" style="display:none;">
                <div class="summary-row">Sélections: <span id="bet-count">0</span></div>
                <div class="summary-row">Cote totale: <span id="bet-total-odd" class="highlight">1.00</span></div>
                <div class="stake-container">
                    <label for="bet-stake-input">Mise (€)</label>
                    <input id="bet-stake-input" type="number" value="10" min="1">
                </div>
                <div class="win-row">Gain Potentiel: <span id="bet-potential-win">0.00 €</span></div>
                <button class="btn-validate" onclick="bettingSystem.placeBet()">VALIDER LE PARI</button>
            </div>
        `;
        document.body.appendChild(sidebar);
        this.sidebar = sidebar;

        document.getElementById('bet-stake-input').addEventListener('input', (e) => {
            this.stake = parseFloat(e.target.value) || 0;
            this.updatePotentialWin();
            this.saveSelections();
        });
    }

    createFloatButton() {
        const btn = document.createElement('button');
        btn.id = 'bet-float-btn';
        btn.innerHTML = `🎯 <span id="bet-count-badge" style="display:none">0</span>`;
        btn.onclick = () => this.openSidebar();
        document.body.appendChild(btn);
    }

    attachOddsEvents() {
        document.addEventListener('click', (e) => {
            const oddItem = e.target.closest('.odd-item');
            if (oddItem) this.toggleSelection(oddItem);
        });
    }

    toggleSelection(oddItem) {
        const matchCard = oddItem.closest('.match-card');
        const home = matchCard.querySelector('.team.home .team-name')?.textContent.trim();
        const away = matchCard.querySelector('.team.away .team-name')?.textContent.trim();
        const odd = parseFloat(oddItem.querySelector('.odd-value')?.textContent);
        const betType = oddItem.dataset.type;
        
        const pathParts = window.location.pathname.split('/');
        const leagueId = document.body.getAttribute('data-current-league') || pathParts[1] || 'ligue-1';

        const id = `${home}-${away}-${betType}`;
        const index = this.selections.findIndex(s => s.id === id);

        if (index !== -1) {
            this.selections.splice(index, 1);
        } else {
            // Un seul pari par match
            const sameMatchIndex = this.selections.findIndex(s => s.home_team === home && s.away_team === away);
            if (sameMatchIndex !== -1) this.selections.splice(sameMatchIndex, 1);

            this.selections.push({ id, league_id: leagueId, home_team: home, away_team: away, bet_type: betType, odd: odd });
        }

        this.saveSelections();
        this.updateUI();
    }

    updateUI() {
        const list = document.getElementById('bet-selections');
        const empty = document.getElementById('bet-empty');
        const summary = document.getElementById('bet-summary');
        const badge = document.getElementById('bet-count-badge');

        // 1. Reset visuel des boutons sur la page
        document.querySelectorAll('.odd-item').forEach(el => el.classList.remove('selected'));

        // 2. Re-colorier les boutons selon les sélections en mémoire
        this.selections.forEach(s => {
            document.querySelectorAll('.match-card').forEach(card => {
                const h = card.querySelector('.team.home .team-name')?.textContent.trim();
                const a = card.querySelector('.team.away .team-name')?.textContent.trim();
                if (h === s.home_team && a === s.away_team) {
                    const btn = card.querySelector(`.odd-item[data-type="${s.bet_type}"]`);
                    if (btn) btn.classList.add('selected');
                }
            });
        });

        // 3. Mise à jour Sidebar
        if (!list) return;
        list.querySelectorAll('.bet-item').forEach(el => el.remove());

        if (this.selections.length === 0) {
            empty.style.display = 'block';
            summary.style.display = 'none';
            badge.style.display = 'none';
            return;
        }

        empty.style.display = 'none';
        summary.style.display = 'block';
        badge.textContent = this.selections.length;
        badge.style.display = 'inline-flex';

        this.selections.forEach((s, i) => {
            list.insertAdjacentHTML('beforeend', `
                <div class="bet-item">
                    <div class="bet-item-info">
                        <span class="bet-item-match">${s.home_team} - ${s.away_team}</span>
                        <span class="bet-item-details">${this.getBetLabel(s.bet_type)} @ <strong>${s.odd.toFixed(2)}</strong></span>
                    </div>
                    <button class="remove-bet" onclick="bettingSystem.removeSelection(${i})">×</button>
                </div>
            `);
        });

        const totalOdd = this.selections.reduce((a, s) => a * s.odd, 1);
        document.getElementById('bet-count').textContent = this.selections.length;
        document.getElementById('bet-total-odd').textContent = totalOdd.toFixed(2);
        this.updatePotentialWin();
    }

    updatePotentialWin() {
        const totalOdd = this.selections.reduce((a, s) => a * s.odd, 1);
        document.getElementById('bet-potential-win').textContent = (this.stake * totalOdd).toFixed(2) + ' €';
    }

    getBetLabel(t) {
        return { '1': 'Victoire Domicile', 'X': 'Match Nul', '2': 'Victoire Extérieur' }[t] || t;
    }

    removeSelection(i) {
        this.selections.splice(i, 1);
        this.saveSelections();
        this.updateUI();
    }

    async placeBet() {
        if (this.selections.length === 0) return;
        const betData = { selections: this.selections, stake: this.stake };

        try {
            const response = await fetch('/api/place-bet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(betData)
            });
            if (response.ok) {
                alert("✅ Pari validé !");
                this.selections = [];
                this.saveSelections();
                window.location.href = '/my-bets';
            }
        } catch (e) { alert("Erreur de connexion"); }
    }

    saveSelections() {
        localStorage.setItem('betting_selections', JSON.stringify(this.selections));
        localStorage.setItem('betting_stake', this.stake);
    }

    loadSelections() {
        const s = localStorage.getItem('betting_selections');
        const st = localStorage.getItem('betting_stake');
        if (s) this.selections = JSON.parse(s);
        if (st) this.stake = parseFloat(st);
        setTimeout(() => this.updateUI(), 300);
    }

    openSidebar() { this.sidebar.classList.add('open'); }
    closeSidebar() { this.sidebar.classList.remove('open'); }
}

let bettingSystem;
document.addEventListener('DOMContentLoaded', () => { bettingSystem = new BettingSystem(); });