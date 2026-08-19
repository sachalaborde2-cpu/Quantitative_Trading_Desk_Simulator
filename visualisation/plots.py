import matplotlib.pyplot as plt

def plot_volatility_skew(clean_data):
    plt.plot(clean_data['calls']["strike"],clean_data['calls']["IV"], marker = "o", linestyle="-", color="b")
    plt.title("Equity Skew on calls")
    plt.xlabel("Strike")
    plt.ylabel("Volatility")
    plt.plot(clean_data['puts']["strike"], clean_data['puts']["IV"], marker="x", linestyle="--", color="r", label="Puts")
    plt.legend()
    plt.show()