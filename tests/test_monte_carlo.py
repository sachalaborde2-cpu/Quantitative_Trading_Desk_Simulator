import numpy as np 
from pricing_engine.black_scholes import EuropeanOption
from pricing_engine.monte_carlo import AsianOptionMC

def test_monte_carlo():
    Strike=100
    Spot=100
    Maturity=1
    Risk_free_rate=0.04
    Volatility=0.2

    AO1=AsianOptionMC(Spot,Strike,Maturity,Risk_free_rate,Volatility,500000,252,45,"geometric")
    price_AO1=AO1.price()
    sigma_geo= Volatility/np.sqrt(3)
    r_geo= 0.5*(Risk_free_rate - ((Volatility**2)/6))
    geo_price=np.exp(-(Risk_free_rate-r_geo)*Maturity) * EuropeanOption(Spot,Strike,Maturity,r_geo,sigma_geo).price()
    se=AO1.standard_error()
    spread=abs(price_AO1-geo_price)

    assert spread<3*se


                
