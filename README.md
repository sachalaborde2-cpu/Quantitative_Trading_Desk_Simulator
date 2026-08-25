# Quantitative Trading Desk Simulator

Un pricer d'options sur actions et un simulateur de desk de market making, avec un dashboard interactif pour passer des ordres et suivre les positions en temps réel.

## Aperçu

- **Pricing Black-Scholes** — prix théorique des options européennes (calls et puts) et calcul des cinq grecques : delta, gamma, vega, theta, rho.
- **Volatilité implicite** — inversion numérique du modèle par la méthode de Brent (`scipy.optimize.brentq`) pour retrouver, à partir du prix coté de chaque option, la volatilité que le marché y intègre. Permet de reconstruire la courbe de skew sur toute la chaîne d'options.
- **Cotation bid/ask avec inventory skewing** — le desk affiche une fourchette autour du prix théorique et décale son prix en fonction du stock déjà détenu, pour décourager le flux qui aggraverait sa position.
- **Delta hedging dynamique** — après chaque ordre, la couverture en actions est recalculée sur le delta agrégé du portefeuille et ajustée de manière incrémentale.

## Capture d'écran

<!-- TODO: remplacer par une vraie capture du dashboard -->
![dashboard](screenshot.png)

## Installation et lancement

```bash
python -m venv venv
```

```bash
venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Lancer le dashboard :

```bash
streamlit run app.py
```

Ou la version en ligne de commande :

```bash
python main.py
```

Lancer les tests :

```bash
pytest tests/
```

## Architecture

Le projet sépare le moteur de calcul des interfaces. `app.py` et `main.py` sont deux façons de piloter exactement le même backend : aucune formule financière n'y est écrite.

```
Quantitative_Trading_Desk_Simulator/
│
├── app.py              Dashboard Streamlit : saisie d'ordres, KPI, inventaire, graphe du skew
├── main.py             Interface en ligne de commande, même logique métier
│
├── market_data/        Acquisition et préparation des données de marché
│                       (Yahoo Finance ou jeu simulé, nettoyage, mid-price,
│                        maturité, calcul de la volatilité implicite)
│
├── pricing_engine/     Le modèle Black-Scholes : prix, grecques, volatilité implicite.
│                       Ne dépend que de NumPy et SciPy, aucune I/O
│
├── market_making/      La logique du desk : cotation, exécution, gestion du cash
│                       et de l'inventaire, couverture en delta
│
├── visualisation/      Tracé de la courbe de volatilité implicite
│
└── tests/              Validation du pricer par la parité call-put
```

## Stack technique

Python, Streamlit, NumPy, SciPy, pandas, matplotlib, yfinance, pytest.

## Limites connues

Le modèle ne prend pas en compte les dividendes du sous-jacent : il n'intègre pas de rendement `q`, ce qui biaise légèrement les volatilités implicites, en particulier sur les puts.

Le multiplicateur de contrat n'est pas appliqué. Une option sur action américaine porte sur 100 titres, alors que le code raisonne sur un contrat unitaire : la couverture en delta est donc juste dans sa logique mais sous-dimensionnée d'un facteur 100 par rapport à un desk réel.

Enfin, le pricer ne traite que les options européennes, sans exercice anticipé.
