import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit.components.v1 as components

# --- IMPORTS BACKEND ---
from market_data.data_feed import get_mock_option_chain
from market_data.data_cleaner import MarketDataCleaner
from market_data.data_enricher import enrich_options_data
from pricing_engine.black_scholes import EuropeanOption
from pricing_engine.monte_carlo import AsianOptionMC
from market_making.pricer_mm import MarketMaker

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Quant Desk // Terminal", 
    page_icon="🕹️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- THÈME "TERMINAL MATRIX" (couleurs, typographie, effets) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&display=swap');

    :root {
        --bg-void: #05070a;
        --bg-panel: #0a0f0d;
        --bg-panel-alt: #0d1512;
        --border-dim: #163326;
        --matrix-green: #39ff88;
        --matrix-green-dim: #1f7a4d;
        --signal-red: #ff3b5c;
        --signal-amber: #ffb020;
        --text-primary: #d7ffe4;
        --text-secondary: #4f6e5c;
    }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background-color: var(--bg-void) !important;
        color: var(--text-primary) !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    [data-testid="stHeader"] { background-color: transparent !important; }

    /* fin voile de scanlines sur toute l'app */
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background: repeating-linear-gradient(
            180deg,
            rgba(57, 255, 136, 0.025) 0px,
            rgba(57, 255, 136, 0.025) 1px,
            transparent 1px,
            transparent 3px
        );
        z-index: 999;
    }

    [data-testid="stSidebar"] {
        background-color: var(--bg-panel) !important;
        border-right: 1px solid var(--border-dim);
    }

    h1, h2, h3 {
        font-family: 'JetBrains Mono', monospace !important;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--matrix-green) !important;
        text-shadow: 0 0 8px rgba(57,255,136,0.35);
    }

    p, span, label, div { font-family: 'JetBrains Mono', monospace; }

    hr { border-color: var(--border-dim) !important; }

    /* --- KPI / Grecques (st.metric) --- */
    [data-testid="stMetric"] {
        background: linear-gradient(180deg, var(--bg-panel-alt), var(--bg-panel));
        border: 1px solid var(--border-dim);
        border-radius: 4px;
        padding: 0.9rem 1rem;
    }
    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.72rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.9rem !important;
        color: var(--matrix-green) !important;
        text-shadow: 0 0 10px rgba(57,255,136,0.55);
        font-weight: 700 !important;
    }

    /* --- Boutons --- */
    .stButton button, [data-testid="stFormSubmitButton"] button {
        background: transparent !important;
        border: 1px solid var(--matrix-green-dim) !important;
        color: var(--matrix-green) !important;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton button:hover, [data-testid="stFormSubmitButton"] button:hover {
        background: rgba(57,255,136,0.08) !important;
        border-color: var(--matrix-green) !important;
        box-shadow: 0 0 14px rgba(57,255,136,0.4);
        color: var(--matrix-green) !important;
    }

    /* --- Champs de saisie --- */
    input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] {
        background-color: var(--bg-panel-alt) !important;
        border-color: var(--border-dim) !important;
        color: var(--text-primary) !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    [data-testid="stForm"] {
        border: 1px solid var(--border-dim);
        border-radius: 4px;
        background: var(--bg-panel-alt);
    }

    /* --- Tableau (book du desk) --- */
    [data-testid="stDataFrame"] { border: 1px solid var(--border-dim); }

    /* --- Alertes --- */
    [data-testid="stAlert"] {
        font-family: 'JetBrains Mono', monospace !important;
        border-radius: 2px;
    }

    /* --- Scrollbar --- */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg-void); }
    ::-webkit-scrollbar-thumb { background: var(--matrix-green-dim); border-radius: 4px; }

    /* --- Panneau OPERATOR --- */
    .operator-panel {
        background: var(--bg-panel);
        border: 1px solid var(--matrix-green-dim);
        border-radius: 4px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.6rem;
    }
    .operator-ascii {
        color: var(--matrix-green);
        font-size: 0.6rem;
        line-height: 1.05;
        white-space: pre;
        text-shadow: 0 0 6px rgba(57,255,136,0.5);
        margin: 0 0 0.5rem 0;
        text-align: center;
    }
    .operator-heading {
        color: var(--text-secondary);
        font-size: 0.68rem;
        letter-spacing: 0.15em;
        margin-bottom: 0.45rem;
    }
    .operator-cursor {
        display: inline-block;
        width: 7px;
        background: var(--matrix-green);
        animation: blink 1s steps(1) infinite;
    }
    .operator-log {
        max-height: 150px;
        overflow-y: auto;
        font-size: 0.7rem;
        line-height: 1.5;
    }
    .operator-log .log-line { color: var(--text-secondary); margin: 1px 0; }
    .operator-log .log-line.success { color: var(--matrix-green); }
    .operator-log .log-line.error { color: var(--signal-red); }
    @keyframes blink { 50% { opacity: 0; } }
    </style>
""", unsafe_allow_html=True)


# --- OPERATOR : avatar ASCII + journal d'actions du desk ---
#
# C'est le "personnage" qui exécute les trades : un panneau HUD affiché dans la
# sidebar, avec un journal des dernières actions du desk (exécutions, couvertures,
# erreurs), mis à jour à chaque interaction.

_OPERATOR_ASCII = """  ▄▄▄▄▄▄▄
 █ ● ● █
 █   ▽  █
 ▀▀▄▄▄▄▀▀
  ┌─┴─┐
  │MM1│
  └───┘"""


def log_operator(message, level="info"):
    """Ajoute une ligne au journal de l'OPERATOR (conserve les 8 dernières)."""
    st.session_state.operator_log.append({"text": message, "level": level})
    st.session_state.operator_log = st.session_state.operator_log[-8:]


def render_operator_panel():
    """Construit le HTML du panneau OPERATOR à partir du journal courant."""
    log_html = "".join(
        f'<div class="log-line {entry["level"]}">&gt; {entry["text"]}</div>'
        for entry in st.session_state.operator_log
    )
    st.markdown(
        f"""
        <div class="operator-panel">
            <pre class="operator-ascii">{_OPERATOR_ASCII}</pre>
            <div class="operator-heading">OPERATOR MM-01<span class="operator-cursor">&nbsp;</span></div>
            <div class="operator-log">{log_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero_banner():
    """Bannière d'en-tête : pluie de caractères façon Matrix (canvas JS) + titre incrusté."""
    components.html(
        """
        <div style="position:relative;width:100%;height:150px;overflow:hidden;
                    border:1px solid #1f7a4d;border-radius:4px;background:#05070a;">
          <canvas id="matrixCanvas" style="position:absolute;top:0;left:0;width:100%;height:100%;"></canvas>
          <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                      text-align:center;font-family:'JetBrains Mono',monospace;">
            <div style="font-size:2rem;font-weight:800;letter-spacing:0.3em;color:#d7ffe4;
                        text-shadow:0 0 14px rgba(57,255,136,0.8),0 0 28px rgba(57,255,136,0.4);">
              QUANT DESK
            </div>
            <div style="font-size:0.8rem;letter-spacing:0.28em;color:#39ff88;margin-top:6px;">
              MARKET MAKING TERMINAL // OPERATOR ACTIVE
            </div>
          </div>
        </div>
        <script>
        const canvas = document.getElementById('matrixCanvas');
        const ctx = canvas.getContext('2d');
        function resize() {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
        }
        resize();
        window.addEventListener('resize', resize);

        const chars = "アカサタナ01ΣΩΔ$€%+-";
        const fontSize = 14;
        let drops = new Array(Math.floor(canvas.width / fontSize)).fill(1);

        function draw() {
            ctx.fillStyle = "rgba(5,7,10,0.15)";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = "#39ff88";
            ctx.font = fontSize + "px monospace";
            for (let i = 0; i < drops.length; i++) {
                const text = chars.charAt(Math.floor(Math.random() * chars.length));
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);
                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        }
        setInterval(draw, 45);
        </script>
        """,
        height=155,
    )


# --- MOTEUR DE GRECQUES (BLACK-SCHOLES + MONTE CARLO) ---
#
# Ces fonctions centralisent le calcul du prix et des grecques pour une position,
# quel que soit le modèle de pricing utilisé. Elles sont appelées à la fois au
# moment de l'exécution d'un trade et à chaque rafraîchissement du dashboard,
# pour que les grecques du portefeuille restent à jour.

def compute_bs_greeks(spot, strike, T, r, sigma, option_type):
    """Prix et grecques analytiques (Black-Scholes)."""
    option = EuropeanOption(spot, strike, T, r, sigma, option_type)
    return {
        "price": option.price(),
        "delta": option.delta(),
        "gamma": option.gamma(),
        "vega": option.vega(),
        "theta": option.theta(),
        "rho": option.rho(),
    }


@st.cache_data(show_spinner=False)
def _mc_price(spot, strike, T, r, sigma, option_type, num_simulations, num_steps, averaging_type, seed):
    """Prix Monte Carlo mis en cache : ne re-simule que si un des paramètres change."""
    option = AsianOptionMC(
        spot, strike, T, r, sigma,
        int(num_simulations), int(num_steps),
        int(seed), averaging_type, option_type,
    )
    return option.price()


def compute_mc_greeks(spot, strike, T, r, sigma, option_type, num_simulations, num_steps, averaging_type, seed):
    """
    Prix et grecques Monte Carlo (option asiatique), obtenues par différences finies
    (bump-and-reprice). AsianOptionMC n'a pas de formule fermée pour les grecques,
    donc chaque grecque est estimée en repriçant l'option avec un paramètre légèrement
    perturbé. La même seed est réutilisée pour le prix central et les prix perturbés
    (nombres aléatoires communs) afin de réduire le bruit d'échantillonnage entre eux.
    """
    h_s = spot * 0.01
    h_sigma = min(0.01, sigma / 2)
    h_t = min(T * 0.01, 1 / 365)
    h_r = 0.0001

    price_mid = _mc_price(spot, strike, T, r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)

    price_up_s = _mc_price(spot + h_s, strike, T, r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)
    price_down_s = _mc_price(spot - h_s, strike, T, r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)

    price_up_sigma = _mc_price(spot, strike, T, r, sigma + h_sigma, option_type, num_simulations, num_steps, averaging_type, seed)
    price_down_sigma = _mc_price(spot, strike, T, r, sigma - h_sigma, option_type, num_simulations, num_steps, averaging_type, seed)

    price_up_t = _mc_price(spot, strike, T + h_t, r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)
    price_down_t = _mc_price(spot, strike, max(T - h_t, 1e-6), r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)

    price_up_r = _mc_price(spot, strike, T, r + h_r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)
    price_down_r = _mc_price(spot, strike, T, r - h_r, sigma, option_type, num_simulations, num_steps, averaging_type, seed)

    delta = (price_up_s - price_down_s) / (2 * h_s)
    gamma = (price_up_s - 2 * price_mid + price_down_s) / (h_s ** 2)
    vega = (price_up_sigma - price_down_sigma) / (2 * h_sigma)
    theta = (price_down_t - price_up_t) / (2 * h_t)  # convention identique à EuropeanOption.theta()
    rho = (price_up_r - price_down_r) / (2 * h_r)

    return {"price": price_mid, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def compute_position_greeks(details, spot, r):
    """Route vers le bon moteur de grecques selon le modèle utilisé à l'exécution du trade."""
    if details["model"] == "black_scholes":
        return compute_bs_greeks(spot, details["strike"], details["T"], r, details["sigma"], details["option_type"])
    else:
        return compute_mc_greeks(
            spot, details["strike"], details["T"], r, details["sigma"], details["option_type"],
            details["num_simulations"], details["num_steps"], details["averaging_type"], details["seed"],
        )


# --- INITIALISATION DE LA MÉMOIRE (SESSION STATE) ---
if 'mm_desk' not in st.session_state:
    st.session_state.mm_desk = MarketMaker()

if 'position_details' not in st.session_state:
    # Stocke, pour chaque option_id en portefeuille, les paramètres nécessaires pour
    # recalculer son prix et ses grecques à tout moment (modèle utilisé, strike, T, IV, ...)
    st.session_state.position_details = {}

if 'operator_log' not in st.session_state:
    st.session_state.operator_log = [{"text": "SYSTÈME INITIALISÉ. OPERATOR MM-01 EN LIGNE.", "level": "info"}]

if 'market_data' not in st.session_state:
    # On charge les données une seule fois au démarrage
    spot_price, expiration_date, raw_chain = get_mock_option_chain()
    clean_data = MarketDataCleaner(raw_chain, expiration_date).process()
    r = 0.04
    st.session_state.market_data = enrich_options_data(clean_data, spot_price, r)
    st.session_state.spot_price = spot_price
    st.session_state.r = r

# Raccourcis pour un code plus lisible
desk = st.session_state.mm_desk
data = st.session_state.market_data
spot = st.session_state.spot_price
r = st.session_state.r

# --- SIDEBAR : TERMINAL D'EXÉCUTION ---
operator_slot = st.sidebar.empty()  # rempli en bas de script, une fois le journal à jour

st.sidebar.title("⚡ Ordres d'Exécution")
st.sidebar.markdown("---")

# --- Choix du modèle de pricing (hors formulaire pour réagir immédiatement) ---
st.sidebar.subheader("Modèle de Pricing")
pricing_model = st.sidebar.selectbox("Méthode", ["Black-Scholes", "Monte Carlo (Asiatique)"])

if pricing_model == "Monte Carlo (Asiatique)":
    mc_col1, mc_col2 = st.sidebar.columns(2)
    num_simulations = mc_col1.number_input("Nb simulations", min_value=10000, value=20000, step=5000)
    num_steps = mc_col2.number_input("Nb pas", min_value=100, value=100, step=50)
    averaging_type = st.sidebar.selectbox("Type de moyenne", ["arithmetic", "geometric"])
    st.sidebar.caption("Grecques estimées par différences finies (bump-and-reprice).")

st.sidebar.markdown("---")

# Utilisation d'un formulaire pour ne pas recharger la page à chaque saisie
with st.sidebar.form("trade_form"):
    st.subheader("Paramètres du Trade")
    
    col1, col2 = st.columns(2)
    ticker = col1.text_input("Ticker", value="AAPL").upper()
    action_type = col2.selectbox("Action", ["Buy", "Sell"])
    
    col3, col4 = st.columns(2)
    strike = col3.number_input("Strike", value=540.0, step=10.0)
    option_type = col4.selectbox("Type", ["call", "put"])
    
    quantity = st.number_input("Quantité", value=100, step=10, min_value=1)
    
    # Le bouton qui déclenche la logique backend
    submitted = st.form_submit_button("Exécuter à la cotation")

# --- LOGIQUE BACKEND D'EXÉCUTION ---
if submitted:
    try:
        table_name = option_type + "s"
        row_order = data[table_name][data[table_name]["strike"] == strike].iloc[0]
        option_id = f"{ticker}_{option_type}_{int(strike)}"

        # 1. Pricing (selon le modèle choisi) + stockage des paramètres de la position
        if pricing_model == "Black-Scholes":
            greeks = compute_bs_greeks(spot, strike, row_order["T"], r, row_order["IV"], option_type)
            st.session_state.position_details[option_id] = {
                "model": "black_scholes",
                "strike": strike,
                "T": row_order["T"],
                "sigma": row_order["IV"],
                "option_type": option_type,
            }
        else:
            # Seed générée une fois à l'exécution puis réutilisée pour toutes les
            # futures recotations de cette position (prix/grecques stables entre deux rafraîchissements).
            seed = int(np.random.default_rng().integers(0, 1_000_000))
            greeks = compute_mc_greeks(
                spot, strike, row_order["T"], r, row_order["IV"], option_type,
                num_simulations, num_steps, averaging_type, seed,
            )
            st.session_state.position_details[option_id] = {
                "model": "monte_carlo",
                "strike": strike,
                "T": row_order["T"],
                "sigma": row_order["IV"],
                "option_type": option_type,
                "num_simulations": num_simulations,
                "num_steps": num_steps,
                "averaging_type": averaging_type,
                "seed": seed,
            }

        prix_theo = greeks["price"]
        delta_order = greeks["delta"]

        # 2. Cotation
        bid, ask = desk.quote_price(prix_theo, option_id)
        
        # 3. Exécution côté Trader
        if action_type.lower() == "buy":
            client_action = "sell"
            desk.execute_trade(quantity, bid, option_id, client_action)
        else:
            client_action = "buy"
            desk.execute_trade(quantity, ask, option_id, client_action)
            
        # 4. Delta Hedging
        risque_delta = desk.inventory[option_id] * delta_order
        desk.hedge_delta(ticker, risque_delta, spot)
        
        st.sidebar.success(f"Ordre rempli ({pricing_model}) ! Couverture Delta ajustée sur {ticker}.")
        log_operator(f"{action_type.upper()} {quantity} {option_id} [{pricing_model.split(' ')[0]}] EXÉCUTÉ", "success")
        log_operator(f"COUVERTURE DELTA AJUSTÉE SUR {ticker}", "success")
    except IndexError:
        st.sidebar.error("Ce strike n'existe pas dans le carnet actuel.")
        log_operator(f"ERREUR: STRIKE {strike} INTROUVABLE", "error")

# Le panneau OPERATOR est rendu ici, en dernier, pour refléter le journal à jour
# de cette exécution — mais grâce au placeholder réservé plus haut, il s'affiche
# bien tout en haut de la sidebar.
with operator_slot.container():
    render_operator_panel()

# --- MAIN DASHBOARD (AFFICHAGE) ---
render_hero_banner()
st.markdown("---")

# 1. Constantes Vitales (KPIs)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric(label="Trésorerie (Cash)", value=f"{desk.cash:,.2f} $")

# Calcul de l'exposition brute (nombre total de contrats ouverts)
exposition_brute = sum(abs(q) for q in desk.inventory.values())
kpi2.metric(label="Contrats Ouverts", value=exposition_brute)

# Formatage du dictionnaire d'actions pour l'affichage
stocks_str = " | ".join([f"{k}: {int(v)}" for k, v in desk.stocks_quantity.items()]) if desk.stocks_quantity else "Neutre"
kpi3.metric(label="Couverture Delta (Actions)", value=stocks_str)

kpi4.metric(label="Spot Price Référence", value=f"{spot} $")

st.markdown("---")

# 2. Grecques du Portefeuille (recalculées en direct à chaque rafraîchissement)
st.subheader("🧮 Grecques du Portefeuille")

portfolio_delta = portfolio_gamma = portfolio_vega = portfolio_theta = portfolio_rho = 0.0

# Grecques des positions optionnelles
for option_id, qty in desk.inventory.items():
    if qty == 0 or option_id not in st.session_state.position_details:
        continue
    details = st.session_state.position_details[option_id]
    greeks = compute_position_greeks(details, spot, r)
    portfolio_delta += qty * greeks["delta"]
    portfolio_gamma += qty * greeks["gamma"]
    portfolio_vega += qty * greeks["vega"]
    portfolio_theta += qty * greeks["theta"]
    portfolio_rho += qty * greeks["rho"]

# Grecques de la couverture en actions : une action a un delta de 1 par construction
# (et gamma/vega/theta/rho nuls dans ce modèle), donc elle contribue au delta du
# portefeuille quantité pour quantité. Sans ce bloc, le delta affiché ignorait
# la couverture déjà exécutée par le desk et ne pouvait jamais se rapprocher de zéro.
for ticker_hedge, qty_shares in desk.stocks_quantity.items():
    portfolio_delta += qty_shares

g1, g2, g3, g4, g5 = st.columns(5)
g1.metric(label="Delta", value=f"{portfolio_delta:,.2f}")
g2.metric(label="Gamma", value=f"{portfolio_gamma:,.4f}")
g3.metric(label="Vega", value=f"{portfolio_vega:,.2f}")
g4.metric(label="Theta", value=f"{portfolio_theta:,.2f}")
g5.metric(label="Rho", value=f"{portfolio_rho:,.2f}")

st.markdown("---")

# 3. Vues Détaillées
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("📋 Book du Desk")
    book_rows = []

    # Positions optionnelles
    for opt_id, qty in desk.inventory.items():
        book_rows.append({
            "Instrument": opt_id,
            "Type": "Option",
            "Position": qty,
            "Modèle": st.session_state.position_details.get(opt_id, {}).get("model", "?"),
        })

    # Positions de couverture en actions (issues du delta hedging)
    for ticker_hedge, qty_shares in desk.stocks_quantity.items():
        book_rows.append({
            "Instrument": ticker_hedge,
            "Type": "Action (Hedge)",
            "Position": qty_shares,
            "Modèle": "-",
        })

    if book_rows:
        inv_df = pd.DataFrame(book_rows)
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
    else:
        st.info("Carnet vide. En attente de liquidité...")

with col_right:
    st.subheader("📈 Volatility Skew")
    
    # Graphique Matplotlib adapté au thème Terminal Matrix
    fig, ax = plt.subplots(figsize=(6, 4))
    
    # Mêmes couleurs que le thème (vert Matrix / rouge signal)
    ax.plot(data['calls']["strike"], data['calls']["IV"], marker="o", linestyle="-", color="#39ff88", label="Calls")
    ax.plot(data['puts']["strike"], data['puts']["IV"], marker="x", linestyle="--", color="#ff3b5c", label="Puts")
    
    # Nettoyage du graphique
    ax.set_facecolor('#05070a')
    fig.patch.set_facecolor('#05070a')
    ax.tick_params(colors='#d7ffe4')
    ax.xaxis.label.set_color('#4f6e5c')
    ax.yaxis.label.set_color('#4f6e5c')
    for spine in ax.spines.values():
        spine.set_edgecolor('#163326')
        
    ax.legend(facecolor='#05070a', labelcolor='#d7ffe4', edgecolor='#163326')
    
    # Affichage dans Streamlit
    st.pyplot(fig)