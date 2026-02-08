// ============================================
// FOC - SYSTÈME DE PARIS (FIX)
// ============================================

class BettingSystem {
    constructor() {
        this.selections = [];
        this.stake = 0;
        this.sidebar = null;
        this.floatBtn = null;
        this.handleOddClick = null;

        this.init();
    }

    init() {
        this.createSidebar();
        this.createFloatButton();
        this.loadSelections();
        this.attachOddsEvents();
        console.log('[Betting] OK');
    }

    createSidebar() {
        const sidebar = document.createElement('div');
        sidebar.className = 'bet-sidebar';
        sidebar.id = 'bet-sidebar';

        sidebar.innerHTML = `
            <div class="bet-sidebar-header">
                <h3>Mon Panier</h3>
                <button onclick="bettingSystem.closeSidebar()">×</button>
            </div>

            <div class="bet-selections" id="bet-selections">
                <div class="bet-empty" id="bet-empty">
                    <p>🎯 Aucune sélection</p>
                </div>
            </div>

            <div class="bet-summary" id="bet-summary" style="display:none;">
                <div>Sélections: <span id="bet-count">0</span></div>
                <div>Cote totale: <span id="bet-total-odd">1.00</span></div>

                <input id="bet-stake-input" type="number" value="10" min="1">

                <div>Gain: <span id="bet-potential-win">0.00 €</span></div>

                <button onclick="bettingSystem.placeBet()">VALIDER</button>
            </div>
        `;

        document.body.appendChild(sidebar);
        this.sidebar = sidebar;

        document.getElementById('bet-stake-input')
            .addEventListener('input', () => this.updatePotentialWin());
    }

    createFloatButton() {
        const btn = document.createElement('button');
        btn.id = 'bet-float-btn';
        btn.innerHTML = `🎯 <span id="bet-count-badge" style="display:none">0</span>`;
        btn.onclick = () => this.openSidebar();
        document.body.appendChild(btn);
        this.floatBtn = btn;
    }

    attachOddsEvents() {
        if (this.handleOddClick) {
            document.removeEventListener('click', this.handleOddClick);
        }

        this.handleOddClick = (e) => {
            const oddItem = e.target.closest('.odd-item');
            if (!oddItem) return;
            e.preventDefault();
            this.toggleSelection(oddItem);
        };

        document.addEventListener('click', this.handleOddClick);
    }

    toggleSelection(oddItem) {
        const matchCard = oddItem.closest('.match-card');
        if (!matchCard) return;

        const home = matchCard.querySelector('.team.home .team-name')?.textContent;
        const away = matchCard.querySelector('.team.away .team-name')?.textContent;
        const odd = parseFloat(oddItem.querySelector('.odd-value')?.textContent);
        let betType = oddItem.dataset.type?.toUpperCase(); // ✅ FIX MAJEUR

        if (!home || !away || !odd || !betType) return;

        const id = `${home}-${away}-${betType}`;
        const index = this.selections.findIndex(s => s.id === id);

        if (index !== -1) {
            this.selections.splice(index, 1);
            oddItem.classList.remove('selected');
        } else {
            this.selections.push({
                id,
                home_team: home,
                away_team: away,
                bet_type: betType,
                odd
            });
            oddItem.classList.add('selected');
        }

        this.updateUI();
        this.saveSelections();
    }

    updateUI() {
        const list = document.getElementById('bet-selections');
        const empty = document.getElementById('bet-empty');
        const summary = document.getElementById('bet-summary');
        const badge = document.getElementById('bet-count-badge');

        if (this.selections.length === 0) {
            empty.style.display = 'block';
            summary.style.display = 'none';
            badge.style.display = 'none';
            list.querySelectorAll('.bet-item').forEach(e => e.remove());
            return;
        }

        empty.style.display = 'none';
        summary.style.display = 'block';

        badge.textContent = this.selections.length;
        badge.style.display = 'inline-flex';

        list.querySelectorAll('.bet-item').forEach(e => e.remove());

        this.selections.forEach((s, i) => {
            list.insertAdjacentHTML('beforeend', `
                <div class="bet-item">
                    <button onclick="bettingSystem.removeSelection(${i})">×</button>
                    <div>${s.home_team} vs ${s.away_team}</div>
                    <div>${this.getBetLabel(s.bet_type)} @ ${s.odd.toFixed(2)}</div>
                </div>
            `);
        });

        const totalOdd = this.selections.reduce((a, s) => a * s.odd, 1);
        document.getElementById('bet-count').textContent = this.selections.length;
        document.getElementById('bet-total-odd').textContent = totalOdd.toFixed(2);

        this.updatePotentialWin();
    }

    updatePotentialWin() {
        const stake = parseFloat(document.getElementById('bet-stake-input').value) || 0;
        const totalOdd = this.selections.reduce((a, s) => a * s.odd, 1);
        document.getElementById('bet-potential-win').textContent =
            (stake * totalOdd).toFixed(2) + ' €';
        this.stake = stake;
    }

    getBetLabel(t) {
        return { '1': 'Victoire Domicile', 'X': 'Match Nul', '2': 'Victoire Extérieur' }[t];
    }

    removeSelection(i) {
        this.selections.splice(i, 1);
        document.querySelectorAll('.odd-item.selected').forEach(o => o.classList.remove('selected'));
        this.updateUI();
        this.saveSelections();
    }

    saveSelections() {
        localStorage.setItem('betting_selections', JSON.stringify(this.selections));
        localStorage.setItem('betting_stake', this.stake);
    }

    loadSelections() {
        const s = localStorage.getItem('betting_selections');
        if (s) this.selections = JSON.parse(s);
        setTimeout(() => this.updateUI(), 300);
    }

    openSidebar() { this.sidebar.classList.add('open'); }
    closeSidebar() { this.sidebar.classList.remove('open'); }
}

let bettingSystem;
document.addEventListener('DOMContentLoaded', () => bettingSystem = new BettingSystem());
