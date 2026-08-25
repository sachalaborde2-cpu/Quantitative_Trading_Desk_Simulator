import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# --- IMPORTS BACKEND ---
from market_data.data_feed import get_mock_option_chain
from market_data.data_cleaner import MarketDataCleaner
from market_data.data_enricher import enrich_options_data
from pricing_engine.black_scholes import EuropeanOption
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

# --- INITIALISATION DE LA MÉMOIRE (SESSION STATE) ---
if 'mm_desk' not in st.session_state:
    st.session_state.mm_desk = MarketMaker()
    
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
        
        # 1. Pricing
        option = EuropeanOption(spot, strike, row_order["T"], r, row_order["IV"], option_type)
        prix_theo = option.price()
        delta_order = option.delta()
        
        # 2. Cotation
        option_id = f"{ticker}_{option_type}_{int(strike)}"
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
        
        st.sidebar.success(f"Ordre rempli ! Couverture Delta ajustée sur {ticker}.")
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

# 2. Vues Détaillées
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("📋 Inventaire des Options")
    if desk.inventory:
        # Transformation du dictionnaire en DataFrame esthétique
        inv_df = pd.DataFrame([
            {"Option ID": opt_id, "Position": qty} 
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