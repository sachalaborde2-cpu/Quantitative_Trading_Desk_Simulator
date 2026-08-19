from visualisation.plots import plot_volatility_skew
from market_data.data_cleaner import MarketDataCleaner
from pricing_engine.black_scholes import EuropeanOption
from market_making.pricer_mm import MarketMaker
from market_data.data_feed import get_mock_option_chain
from market_data.data_enricher import enrich_options_data

r = 0.04

spot_price,expiration_date,raw_chain = get_mock_option_chain()

print("Nettoyage des données...")
clean_data = MarketDataCleaner(raw_chain, expiration_date).process()

clean_data = enrich_options_data(clean_data,spot_price, r)

#plot_volatility_skew(clean_data)

mm_desk=MarketMaker()

while True:
    choice = input("Nouveau Trade? (Yes/No, ou 'exit' pour quitter) : ")
    if choice.lower() == "no" or choice.lower() == "exit":
        break
    else:
        strike = float(input("Strike : "))
        option_type = input("Option Type ( Call or Put) : ")
        action_type = input ("Buy/Sell : ")
        ticker = input("Ticker de l'action (ex: AAPL) : ").upper()
        quantity = int(input ("Quantity : "))

    row_order = clean_data[option_type+"s"][clean_data[option_type+"s"]["strike"]== strike].iloc[0]

    option = EuropeanOption(spot_price,strike,row_order["T"],r,row_order["IV"],option_type)
    prix_theo = option.price()
    delta_order = option.delta()
    option_id = f"{ticker}_{option_type}_{int(strike)}"
    bid,ask = mm_desk.quote_price(prix_theo,option_id)
    if action_type.lower() == "buy" :
        client_action = "sell"
        mm_desk.execute_trade(quantity,bid,option_id,client_action)
    else:
        client_action = "buy"
        mm_desk.execute_trade(-quantity,ask,option_id,client_action)

    risque_delta = mm_desk.inventory[option_id] * delta_order

    mm_desk.hedge_delta(ticker,risque_delta,spot_price)

    print(f"--- ÉTAT DU DESK --- \nCash: {mm_desk.cash:.2f} | Actions {ticker}: {mm_desk.stocks_quantity[ticker]} | Inventaire: {mm_desk.inventory}")

