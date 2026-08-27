import numpy as np


class Option:

   def __init__(self, spot, strike, time_to_maturity, risk_free_rate, volatility, option_type='call'):
        self.S = spot
        self.K = strike
        self.T = time_to_maturity
        self.r = risk_free_rate
        self.sigma = volatility
        self.option_type = option_type.lower()

        if self.option_type not in ["call", "put"]:
            raise ValueError("It should be a call or a put") 

        if self.S<=0 :
            raise ValueError("The spot price should be greater than 0")

        if self.K<=0 :
            raise ValueError("The strike should be greater than 0")

        if self.T<=0 :
            raise ValueError("The time to maturity should be greater than 0")

        if self.sigma<=0 :
            raise ValueError("The volatilitye should be greater than 0")


   def _payoff(self,level):

        if self.option_type == "call":
            payoff = np.maximum(level-self.K,0)
        else:
            payoff = np.maximum(self.K-level,0)

        return payoff

        
           
           


       

        

           
