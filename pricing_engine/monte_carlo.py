from pricing_engine.base import Option
import numpy as np

class AsianOptionMC(Option):

    def __init__(self, spot, strike, time_to_maturity, risk_free_rate, volatility,num_simulations,num_steps,seed = None ,averaging_type='arithmetic', option_type='call'):
        super().__init__(spot, strike, time_to_maturity, risk_free_rate, volatility, option_type) 
        self.NSI = num_simulations
        self.NST = num_steps
        self.AT = averaging_type
        self.rng = np.random.default_rng(seed)
        self._cached_payoffs = None

        if self.NSI<10000:
            raise ValueError(" There isn't enough simulations to get a relevant result ! ")

        if self.NST<100:
            raise ValueError(" There isn't enough steps to get a relevant result ! ")

        if self.AT not in ["arithmetic","geometric"]:
            raise ValueError(" The averaging type should be either arithmetic or geometric ! ")

    def _simulate_paths(self):

        delta_t= self.T/self.NST
        matrix= self.rng.standard_normal((self.NSI,self.NST))
        matrix = (self.r-((self.sigma**2)/2))*delta_t + self.sigma * np.sqrt(delta_t)*matrix
        log_price_matrix = np.cumulative_sum(matrix,axis=1)
        price_matrix = np.exp(log_price_matrix)*self.S
        price_matrix =np.insert(price_matrix,0,self.S,axis=1)

        return price_matrix

    def _discounted_payoffs(self):
        if self._cached_payoffs is None:


            if self.AT == "arithmetic":
                average_paths= np.mean(self._simulate_paths(),axis = 1)
            else:
                average_paths=np.exp(np.mean(np.log(self._simulate_paths()),axis=1))
        
            payoff=self._payoff(average_paths)
            payoff=np.exp(-self.r*self.T)*payoff
            self._cached_payoffs = payoff
        else:
            payoff = self._cached_payoffs

        return payoff


    def price(self):

        return np.mean(self._discounted_payoffs(),axis=0)

    def standard_error(self):

        return np.std(self._discounted_payoffs())/np.sqrt(self.NSI)


if __name__ == "__main__":
    AO=AsianOptionMC(100,100,1,0.04,0.2,10000,252)

    print(AO._simulate_paths())
    print(AO.price())
    print(AO.price())
    









              

        

