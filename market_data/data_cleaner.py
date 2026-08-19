import pandas as pd
import numpy as np
from datetime import datetime


class MarketDataCleaner:
    def __init__(self, raw_chain, expiration_date):
        """
        Initialise le nettoyeur avec la chaîne brute récupérée par le DataFetcher.
        :param raw_chain: Dictionnaire contenant {'calls': df_calls, 'puts': df_puts}
        :param expiration_date: La date d'expiration sous format 'YYYY-MM-DD'
        """
        self.calls = raw_chain['calls'].copy()
        self.puts = raw_chain['puts'].copy()
        self.expiration_date = expiration_date

    def calculate_time_to_maturity(self):
        """
        Calcule le temps restant jusqu'à l'expiration en années (T).
        """
        Today=datetime.today()
        Expiration_date=datetime.strptime(self.expiration_date,"%Y-%m-%d")
        return (Expiration_date-Today).days/365.25

    def clean_dataframe(self, df):
        """
        Nettoie un DataFrame d'options (Calls ou Puts).
        """
        df["mid_price"]= (df["ask"]+ df["bid"])/2
        df=df[(df["volume"]>0)&(df["bid"]>0)]
        return df

    def process(self):
        """
        Méthode principale qui exécute tout le nettoyage.
        """
        T = self.calculate_time_to_maturity()
        
        clean_calls = self.clean_dataframe(self.calls)
        clean_puts = self.clean_dataframe(self.puts)
        
        if clean_calls is not None:
            clean_calls['T'] = T
        if clean_puts is not None:
            clean_puts['T'] = T
            
        return {'calls': clean_calls, 'puts': clean_puts}
    