from pricing_engine.black_scholes import EuropeanOption

def enrich_options_data(clean_data, spot_price, risk_free_rate):

    

    def calculate_row_iv(row, spot, risk_free_rate, option_type):
        """
        Prend une ligne du DataFrame Pandas, crée une option et calcule son IV.
        """
    
        option = EuropeanOption(spot,row['strike'],row['T'],risk_free_rate,0.2,option_type)
    
        iv=option.implied_volatility(row['mid_price'])
    
        return iv

    clean_data["calls"]["IV"]= clean_data["calls"].apply(lambda row : calculate_row_iv(row,spot_price,risk_free_rate,"call"),axis=1)

    clean_data["puts"]["IV"]= clean_data["puts"].apply(lambda row : calculate_row_iv(row,spot_price,risk_free_rate,"put"),axis=1)

    return clean_data