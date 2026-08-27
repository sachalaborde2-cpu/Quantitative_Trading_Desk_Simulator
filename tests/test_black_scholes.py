from pricing_engine.black_scholes import EuropeanOption
import numpy as np


def test_call_put_parity():
    Strike=100
    Spot=100
    Maturity=1
    Risk_free_rate=0.04
    Volatility=0.2


    Call1=EuropeanOption(Spot,Strike,Maturity,Risk_free_rate,Volatility,"call")
    Put1=EuropeanOption(Spot,Strike,Maturity,Risk_free_rate,Volatility,"put")


    RP=Call1.price()-Put1.price()
    LP=Spot - Strike*np.exp(-Risk_free_rate*Maturity)

    np.testing.assert_almost_equal(RP, LP, decimal=5)


