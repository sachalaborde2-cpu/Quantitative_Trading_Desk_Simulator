import numpy as np
from scipy.stats import norm
import math
from scipy.optimize import brentq
from pricing_engine.base import Option

class EuropeanOption(Option):
    def __init__(self, spot, strike, time_to_maturity, risk_free_rate, volatility, option_type='call'):
        super().__init__(spot, strike, time_to_maturity, risk_free_rate, volatility, option_type) 
       

    def d1(self):
        return (np.log(self.S/self.K)+(self.r+(self.sigma**2)/2)*self.T)/(self.sigma*np.sqrt(self.T))

       

    def d2(self):
        return self.d1()-(self.sigma*np.sqrt(self.T))

    def price(self):
        d1_val=self.d1()
        d2_val=self.d2()
        if self.option_type=="call":
            return norm.cdf(d1_val)*self.S - self.K*np.exp(-self.r*self.T)*norm.cdf(d2_val)
        else:
            return -norm.cdf(-d1_val)*self.S + self.K*np.exp(-self.r*self.T)*norm.cdf(-d2_val)

    def delta(self):
        if self.option_type=="call":
            return norm.cdf(self.d1())
        else:
            return norm.cdf(self.d1()) - 1

    def gamma(self):
        return norm.pdf(self.d1())/(self.S*self.sigma*np.sqrt(self.T))

    def vega(self):
        return self.S*norm.pdf(self.d1())*np.sqrt(self.T)

    def theta(self):
        if self.option_type=="call":
            return -(self.S*norm.pdf(self.d1())*self.sigma)/(2*np.sqrt(self.T)) - self.r*self.K*np.exp(-self.r*self.T)*norm.cdf(self.d2())
        else:
            return -(self.S*norm.pdf(self.d1())*self.sigma)/(2*np.sqrt(self.T)) + self.r*self.K*np.exp(-self.r*self.T)*norm.cdf(-self.d2())

    def rho(self):
        if self.option_type=="call":
            return self.K*self.T*np.exp(-self.r*self.T)*norm.cdf(self.d2())
        else:
            return -self.K*self.T*np.exp(-self.r*self.T)*norm.cdf(-self.d2())

    def implied_volatility(self, market_price):
        """
        Calcule la volatilité implicite en utilisant l'algorithme de Brent.
        """
        def objective_function(v):
            self.sigma = v
            
            theorical_price=self.price()
            
            return theorical_price- market_price
            
        try:
            return brentq(objective_function, 0.0001, 5.0)
        except ValueError:
            return float("nan")
