import yfinance as yf
import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MarketDataFetcher:
    def __init__(self, ticker_symbol):
        """
        Initialise le récupérateur de données pour un sous-jacent précis.
        :param ticker_symbol: Le symbole boursier (ex: 'SPY', 'AAPL')
        """
        self.ticker_symbol = ticker_symbol
        
        self.session = requests.Session()
        
        self.session.verify = False
        
        self.ticker = yf.Ticker(ticker_symbol, session=self.session)

    def get_expirations(self):
        """
        Récupère toutes les dates d'expiration disponibles pour les options de ce ticker.
        :return: Une liste ou un tuple de chaînes de caractères (dates).
        """
        return self.ticker.options

    def get_option_chain(self, expiration_date):
        """
        Récupère la chaîne d'options complète (Calls et Puts) pour une maturité donnée.
        
        :param expiration_date: La date d'expiration sous format 'YYYY-MM-DD'
        :return: Un dictionnaire contenant deux DataFrames Pandas ('calls' et 'puts')
        """
        chain = self.ticker.option_chain(expiration_date)
        return {'calls': chain.calls, 'puts': chain.puts}
    
    def get_current_spot(self):
        """
        Récupère le dernier prix coté du sous-jacent.
        On utilise history() au lieu de fast_info pour minimiser les erreurs de Rate Limit.
        """
        hist = self.ticker.history(period="1d")
        
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        else:
            raise ValueError(f"Impossible de récupérer le prix pour {self.ticker_symbol}")