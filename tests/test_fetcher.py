from market_data.data_fetcher import MarketDataFetcher

print("Tentative de connexion à Yahoo Finance...")

try:
    fetcher = MarketDataFetcher('SPY')
    
    spot_price = fetcher.get_current_spot()
    print(f"✅ Succès ! Prix actuel du SPY : {spot_price} $")
    
    expirations = fetcher.get_expirations()
    print(f"✅ Succès ! {len(expirations)} maturités disponibles. Les 3 premières : {expirations[:3]}")

except Exception as e:
    print(f"❌ Échec de la connexion. L'erreur est toujours là :")
    print(e)