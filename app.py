import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- IMPORTS BACKEND ---
from market_data.data_feed import get_mock_option_chain
from market_data.data_cleaner import MarketDataCleaner
from market_data.data_enricher import enrich_options_data
from pricing_engine.black_scholes import EuropeanOption
from pricing_engine.monte_carlo import AsianOptionMC
from market_making.pricer_mm import MarketMaker

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Quantitative Trading Desk", 
    page_icon="📈", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Custom CSS pour peaufiner le style (couleurs des métriques)
st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #00FFAA;
    }
    </style>
""", unsafe_allow_html=True)


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
    except IndexError:
        st.sidebar.error("Ce strike n'existe pas dans le carnet actuel.")

# --- MAIN DASHBOARD (AFFICHAGE) ---
st.title("📊 Quantitative Market Making Desk")
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
    st.subheader("📋 Inventaire des Options")
    if desk.inventory:
        # Transformation du dictionnaire en DataFrame esthétique
        inv_df = pd.DataFrame([
            {
                "Option ID": opt_id,
                "Position": qty,
                "Modèle": st.session_state.position_details.get(opt_id, {}).get("model", "?"),
            }
            for opt_id, qty in desk.inventory.items()
        ])
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
    else:
        st.info("Carnet vide. En attente de liquidité...")

with col_right:
    st.subheader("📈 Volatility Skew")
    
    # Graphique Matplotlib adapté pour un thème sombre
    fig, ax = plt.subplots(figsize=(6, 4))
    
    # Couleurs néon pour le style trading
    ax.plot(data['calls']["strike"], data['calls']["IV"], marker="o", linestyle="-", color="#00FFAA", label="Calls")
    ax.plot(data['puts']["strike"], data['puts']["IV"], marker="x", linestyle="--", color="#FF4B4B", label="Puts")
    
    # Nettoyage du graphique
    ax.set_facecolor('#0E1117')
    fig.patch.set_facecolor('#0E1117')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('gray')
    ax.yaxis.label.set_color('gray')
    for spine in ax.spines.values():
        spine.set_edgecolor('#333333')
        
    ax.legend(facecolor='#0E1117', labelcolor='white', edgecolor='#333333')
    
    # Affichage dans Streamlit
    st.pyplot(fig)