class MarketMaker:
    def __init__(self, base_spread=0.10, risk_aversion=0.01):
        """
        Initialise un Market Maker pour une option spécifique.
        """

        self.base_spread = base_spread
        self.risk_aversion = risk_aversion
        
        self.inventory = {} 
        self.cash = 0.0 
        self.stocks_quantity = {}  


    def quote_price(self,theorical_price,option_id):

        if  option_id not in self.inventory:
            self.inventory[option_id] = 0


        price_shift = - (self.inventory[option_id] * self.risk_aversion)


        adjusted_price = theorical_price + price_shift

        bid= adjusted_price - (self.base_spread/2)
        ask = adjusted_price + (self.base_spread/2)

        return (bid , ask )

    def execute_trade(self, quantity , execution_price, option_id, action_client="buy" ):

        cash_flow = quantity * execution_price

        if  option_id not in self.inventory:
            self.inventory[option_id] = 0

        if action_client== "sell" :
            self.cash -= cash_flow
            self.inventory[option_id] += quantity
        else:
           self.cash += cash_flow
           self.inventory[option_id] -= quantity

        return f"Trade executed. New inventory:{self.inventory}, new cash:{self.cash}"

    def hedge_delta(self,ticker, portfolio_delta, current_spot_price):

        if  ticker not in self.stocks_quantity:
            self.stocks_quantity[ticker] = 0

        target_stocks_quantity= -portfolio_delta

        stocks_adjustment = target_stocks_quantity - self.stocks_quantity[ticker] 

        self.stocks_quantity[ticker] += stocks_adjustment

        self.cash += - (current_spot_price * stocks_adjustment)

    




    








