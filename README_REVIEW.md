# README_REVIEW — Analyse technique du projet `equity_derivatives_pricer`

> Document d'analyse généré par revue de code exhaustive du dépôt.
> Objectif : documenter précisément le fonctionnement du projet, fichier par fichier,
> et identifier les points valorisables sur un CV en finance quantitative.
>
> **Mise à jour** — prise en compte de la version finale du code : `main.py` refactoré,
> `visualisation/plots.py` complété, et ajout de `app.py` (dashboard Streamlit).

---

## 1. Vue d'ensemble du projet

`equity_derivatives_pricer` est un **moteur de valorisation d'options sur actions (equity derivatives) écrit en Python**, doublé d'un **simulateur de desk de market making**, accessible au choix par une **interface web (Streamlit)** ou par un **terminal en ligne de commande**.

Ce que le projet permet de faire, concrètement :

1. **Récupérer des données de marché** sur les options d'un sous-jacent (ex : `SPY`, `AAPL`) via l'API Yahoo Finance — prix spot, dates d'échéance, chaîne d'options complète — ou travailler sur un jeu de données simulé réaliste.
2. **Nettoyer et normaliser ces données** : prix mid (moyenne bid/ask), filtrage des lignes illiquides, conversion de la date d'échéance en maturité exprimée en années.
3. **Valoriser des options européennes** avec le modèle **Black-Scholes** : prix théorique + les cinq grecques principales (delta, gamma, vega, theta, rho).
4. **Extraire la volatilité implicite (IV)** de chaque option cotée, par inversion numérique du modèle Black-Scholes (algorithme de Brent).
5. **Visualiser le « skew » de volatilité** : la courbe IV en fonction du strike, qui révèle empiriquement que le marché ne croit pas à l'hypothèse de volatilité constante de Black-Scholes.
6. **Tenir un desk de market making en session** : coter une fourchette bid/ask autour du prix théorique, décaler ce prix selon l'inventaire détenu (*skewing*), exécuter des trades, se couvrir en delta sur le sous-jacent, et suivre en continu la trésorerie et les positions.

**Le point marquant de l'architecture :** le projet expose **deux interfaces interchangeables** sur exactement le même moteur — `app.py` (dashboard web) et `main.py` (terminal). Aucune des deux ne contient de logique financière : elles se contentent d'orchestrer les mêmes appels. C'est la meilleure preuve que la séparation en couches tient réellement.

**Statut de maturité :** projet fonctionnel et complet dans sa portée. Le pipeline tourne de bout en bout dans les deux interfaces. Une erreur de signe subsiste dans le sens « vente » de l'exécution (voir §7.1), qui empêche le desk de se mettre en position vendeuse.

---

## 2. Architecture globale

### 2.1 Arborescence

```
equity_derivatives_pricer/
│
├── app.py                      ← INTERFACE WEB — dashboard Streamlit (158 l.)
├── main.py                     ← INTERFACE CLI — terminal de trading (51 l.)
├── requirements.txt            ← Dépendances figées (pip freeze)
├── .gitignore                  ← Exclut venv/, __pycache__/, .pytest_cache/
│
├── market_data/                ← COUCHE DONNÉES (acquisition & préparation)
│   ├── __init__.py
│   ├── data_fetcher.py         ← Connexion Yahoo Finance (I/O réseau)
│   ├── data_feed.py            ← Générateur de données simulées (mock)
│   ├── data_cleaner.py         ← Nettoyage, mid-price, maturité T
│   └── data_enricher.py        ← Ajout de la colonne IV à la chaîne
│
├── pricing_engine/             ← COUCHE MODÈLE (mathématiques financières)
│   ├── __init__.py
│   └── black_scholes.py        ← Classe EuropeanOption : prix, grecques, IV
│
├── market_making/              ← COUCHE TRADING (simulation de desk)
│   └── pricer_mm.py            ← Classe MarketMaker : quote, trade, hedge
│
├── visualisation/              ← COUCHE PRÉSENTATION
│   └── plots.py                ← Tracé du skew (matplotlib)
│
└── tests/                      ← TESTS
    ├── __init__.py
    ├── test_black_scholes.py   ← Test de parité call-put (pytest)
    └── test_fetcher.py         ← Script de vérification de connexion Yahoo
```

**Volumétrie :** 569 lignes de Python au total, dont 146 pour le moteur quantitatif
(`black_scholes.py` + `pricer_mm.py`) et 209 pour les deux interfaces.

### 2.2 Schéma de flux de données

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                        SOURCES DE DONNÉES                         │
 │                                                                   │
 │   data_fetcher.py                    data_feed.py                 │
 │   (Yahoo Finance, réel)              (mock, hors-ligne)           │
 │   • get_current_spot()               • get_mock_option_chain()    │
 │   • get_expirations()                                             │
 │   • get_option_chain()                                            │
 └───────────────────────┬──────────────────────┬────────────────────┘
                         │                      │
                         │  {'calls': DataFrame, 'puts': DataFrame}
                         ▼                      ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │                        data_cleaner.py                            │
 │                    MarketDataCleaner.process()                    │
 │   • mid_price = (bid + ask) / 2                                   │
 │   • filtre : volume > 0 ET bid > 0   (retire les options mortes)  │
 │   • T = (expiration − aujourd'hui)/365.25  → maturité en années   │
 └───────────────────────────────┬──────────────────────────────────┘
                                 │  DataFrames enrichis (mid_price, T)
                                 ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │                        data_enricher.py                           │
 │                      enrich_options_data()                        │
 │   Pour chaque ligne : instancie EuropeanOption                    │
 │                    → appelle implied_volatility(mid_price)        │
 │   Ajoute la colonne 'IV'                                          │
 └───────────────────────────────┬──────────────────────────────────┘
                                 │ (appelle)
                                 ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │              pricing_engine/black_scholes.py                      │
 │                     class EuropeanOption                          │
 │   ┌────────────────────────────────────────────────────────────┐  │
 │   │ SENS DIRECT   : (S,K,T,r,σ)  ──Black-Scholes──▶  Prix      │  │
 │   │ SENS INVERSE  : (S,K,T,r,Prix) ──Brent──▶  σ implicite     │  │
 │   │ SENSIBILITÉS  : delta, gamma, vega, theta, rho             │  │
 │   └────────────────────────────────────────────────────────────┘  │
 └────────┬────────────────────────────────────────┬────────────────┘
          │ prix théorique + delta                 │ IV par strike
          ▼                                        ▼
 ┌──────────────────────────┐        ┌──────────────────────────────┐
 │ market_making/pricer_mm  │        │  visualisation/plots.py      │
 │     class MarketMaker    │        │  plot_volatility_skew()      │
 │  • quote_price()  bid/ask│        │  Courbe IV = f(strike)       │
 │  • execute_trade() cash  │        │  calls (bleu) / puts (rouge) │
 │  • hedge_delta()  actions│        └──────────────────────────────┘
 └────────────┬─────────────┘
              │
              │  Le même backend, deux façons de le piloter :
              ▼
 ┌───────────────────────────────┐   ┌───────────────────────────────┐
 │           app.py              │   │           main.py             │
 │      Dashboard Streamlit      │   │      Terminal interactif      │
 │  • formulaire d'ordre         │   │  • boucle input() en console  │
 │  • 4 KPI temps réel           │   │  • état du desk après chaque  │
 │  • table d'inventaire         │   │    trade                      │
 │  • graphe du skew (thème dark)│   │                               │
 │  • état persistant en session │   │                               │
 └───────────────────────────────┘   └───────────────────────────────┘
```

### 2.3 Principe architectural

Le projet suit une **séparation en couches (layered architecture)** classique en finance quantitative :

| Couche | Responsabilité | Ne connaît pas |
|---|---|---|
| `market_data` | D'où viennent les données, comment les nettoyer | Comment on price |
| `pricing_engine` | Les mathématiques pures. Aucune I/O, aucun pandas | D'où viennent les données |
| `market_making` | La logique métier de trading | Le modèle de pricing (reçoit un prix déjà calculé) |
| `visualisation` | L'affichage des graphes | Tout le reste |
| `app.py` / `main.py` | L'orchestration et l'interaction utilisateur | Aucune formule financière |

**L'intérêt de ce découpage :** `pricing_engine/black_scholes.py` est totalement indépendant — il ne dépend que de `numpy` et `scipy`. On peut le tester unitairement sans réseau, le réutiliser ailleurs, ou remplacer Yahoo Finance par Bloomberg sans toucher une ligne de math. De même, `MarketMaker` reçoit un prix théorique en entrée : on pourrait brancher un modèle Heston ou un arbre binomial à la place de Black-Scholes sans le modifier.

**La preuve que le découpage tient :** `app.py` et `main.py` exécutent exactement la même séquence métier (pricing → cotation → exécution → hedge) avec des appels identiques, et diffèrent uniquement par la manière de collecter les saisies et d'afficher les résultats. Ajouter une troisième interface (API REST, notebook) ne demanderait aucune modification du backend.

---

## 3. Analyse détaillée fichier par fichier

---

### 3.1 `pricing_engine/black_scholes.py` — **le cœur du projet**

**Rôle :** implémente le modèle de Black-Scholes-Merton pour les options européennes. C'est le fichier le plus dense mathématiquement et le plus valorisable du projet.

**Dépendances :** `numpy` (calcul vectoriel), `scipy.stats.norm` (loi normale — fonction de répartition `cdf` et densité `pdf`), `scipy.optimize.brentq` (recherche de racine).

**Importé par :** `market_data/data_enricher.py`, `app.py`, `main.py`, `tests/test_black_scholes.py`.
**Importe :** rien du projet — c'est une feuille de l'arbre de dépendances (bonne pratique).

#### Classe `EuropeanOption`

Représente une option européenne, c'est-à-dire un contrat exerçable **uniquement à l'échéance** (par opposition aux options américaines, exerçables à tout moment).

**`__init__(spot, strike, time_to_maturity, risk_free_rate, volatility, option_type='call')`**

Stocke les cinq paramètres du modèle, avec la notation standard de la littérature :

| Attribut | Symbole | Signification |
|---|---|---|
| `self.S` | S | Prix actuel du sous-jacent (ex : action SPY à 540 $) |
| `self.K` | K | Strike = prix d'exercice convenu dans le contrat |
| `self.T` | T | Maturité **en années** (0.25 = 3 mois) |
| `self.r` | r | Taux sans risque annualisé |
| `self.sigma` | σ | Volatilité annualisée du sous-jacent |
| `self.option_type` | — | `'call'` (droit d'acheter) ou `'put'` (droit de vendre) |

**`d1()` et `d2()` — les deux variables intermédiaires du modèle**

```
d1 = [ ln(S/K) + (r + σ²/2)·T ] / (σ·√T)
d2 = d1 − σ·√T
```

*Vulgarisation :* ce sont des **distances normalisées** entre le cours actuel et le strike, exprimées en nombre d'écarts-types. Plus `d1` est grand, plus l'option a de chances de finir « dans la monnaie ». Le terme `ln(S/K)` mesure de combien l'option est déjà gagnante ; `σ√T` mesure l'incertitude accumulée d'ici l'échéance.

**`price()` — la formule de Black-Scholes**

```
Call = S·N(d1) − K·e^(−rT)·N(d2)
Put  = K·e^(−rT)·N(−d2) − S·N(−d1)
```

*Vulgarisation :* `N(d2)` est la probabilité (en univers risque-neutre) que l'option soit exercée. `K·e^(−rT)` est le strike actualisé à aujourd'hui — on paiera K plus tard, donc il « coûte » moins cher en valeur d'aujourd'hui. Le prix d'un call est donc *« ce qu'on espère recevoir »* moins *« ce qu'on s'attend à payer »*.

**Les grecques — les sensibilités du prix**

Une grecque est une **dérivée partielle** du prix par rapport à un paramètre. C'est l'outil quotidien d'un trader d'options : ça lui dit comment son portefeuille va bouger si le marché bouge.

| Méthode | Dérivée | Ce que ça mesure | Formule implémentée |
|---|---|---|---|
| `delta()` | ∂Prix/∂S | De combien le prix bouge si le sous-jacent monte de 1 $. Un delta de 0.5 = l'option se comporte comme 0.5 action. **C'est la grecque du hedge.** | Call : `N(d1)` — Put : `N(d1) − 1` |
| `gamma()` | ∂²Prix/∂S² | À quelle vitesse le delta lui-même change. Un gamma élevé = il faut rehedger souvent. | `φ(d1) / (S·σ·√T)` |
| `vega()` | ∂Prix/∂σ | Sensibilité à la volatilité. C'est ce qu'un desk d'options achète et vend réellement. | `S·φ(d1)·√T` |
| `theta()` | ∂Prix/∂T | L'érosion du temps : combien l'option perd par an juste en vieillissant. Défavorable à l'acheteur. | terme `−S·φ(d1)·σ/(2√T)` ± `r·K·e^(−rT)·N(±d2)` |
| `rho()` | ∂Prix/∂r | Sensibilité aux taux d'intérêt. Faible impact sur les maturités courtes. | Call : `K·T·e^(−rT)·N(d2)` — Put : `−K·T·e^(−rT)·N(−d2)` |

(`N` = `norm.cdf`, fonction de répartition de la loi normale ; `φ` = `norm.pdf`, sa densité.)

**`implied_volatility(market_price)` — l'inversion du modèle**

C'est la méthode la plus intéressante intellectuellement du projet.

*Le problème :* Black-Scholes prend σ en entrée et sort un prix. Mais sur le marché, **on observe le prix, pas σ**. On veut donc résoudre le problème inverse : *quelle volatilité faudrait-il injecter dans Black-Scholes pour retrouver exactement le prix coté ?* Cette valeur s'appelle la **volatilité implicite**.

*La difficulté :* la formule de Black-Scholes n'est **pas inversible analytiquement** en σ. Il faut passer par une méthode numérique.

*L'implémentation :*
```python
def objective_function(v):
    self.sigma = v
    return self.price() - market_price      # on cherche le zéro de cette fonction

return brentq(objective_function, 0.0001, 5.0)
```

Une fonction objectif locale (closure) mesure l'écart entre le prix du modèle et le prix de marché ; `scipy.optimize.brentq` cherche la valeur de σ qui annule cet écart, sur l'intervalle [0.01 %, 500 %].

**L'algorithme de Brent** combine la robustesse de la dichotomie (bissection) avec la vitesse de la méthode de la sécante et de l'interpolation quadratique inverse. Il garantit la convergence dès lors que la fonction change de signe aux bornes — ce qui est le cas ici car le prix Black-Scholes est **strictement croissant en σ** (le vega est toujours positif).

Le `try/except ValueError` renvoie `NaN` quand `brentq` échoue — typiquement quand le prix de marché est hors des bornes atteignables par le modèle (option cotée sous sa valeur intrinsèque, données aberrantes). **C'est une gestion d'erreur pertinente** : sur une chaîne d'options réelle, quelques lignes sont toujours incohérentes, et on ne veut pas que tout le pipeline plante pour autant.

---

### 3.2 `app.py` — **dashboard Streamlit (nouveau, 158 lignes)**

**Rôle :** interface web du desk de market making. C'est le fichier le plus long du projet et sa vitrine : il transforme un pipeline de calcul en un outil qu'on peut réellement manipuler.

**Dépendances :** `streamlit`, `pandas`, `matplotlib`, plus les cinq modules du backend (`data_feed`, `data_cleaner`, `data_enricher`, `black_scholes`, `pricer_mm`).

**Importe :** tout le backend.
**Importé par :** rien (point d'entrée).

**Lancement :**
```bash
streamlit run app.py
```

#### Structure du fichier

**1. Configuration de la page**
`st.set_page_config()` fixe le titre, l'icône, la mise en page pleine largeur (`layout="wide"`) et la sidebar dépliée. Un bloc CSS injecté via `st.markdown(..., unsafe_allow_html=True)` cible `[data-testid="stMetricValue"]` pour agrandir les KPI et les colorer en vert néon — un détail cosmétique, mais qui montre qu'on sait sortir du style par défaut de Streamlit.

**2. Gestion de l'état — le point technique central**

```python
if 'mm_desk' not in st.session_state:
    st.session_state.mm_desk = MarketMaker()

if 'market_data' not in st.session_state:
    ...  # chargement + nettoyage + calcul d'IV
    st.session_state.market_data = enrich_options_data(clean_data, spot_price, r)
```

*Pourquoi c'est le passage obligé de Streamlit :* le framework **réexécute le script entier** à chaque interaction de l'utilisateur (clic, saisie, sélection). Sans précaution, le `MarketMaker` serait recréé à zéro à chaque ordre — le desk oublierait sa position et sa trésorerie — et toute la chaîne d'options serait re-nettoyée et ré-inversée par Brent à chaque clic.

Le `st.session_state` est le mécanisme qui **survit aux reruns**. Le pattern `if 'clé' not in st.session_state:` garantit une initialisation **unique** par session. Il porte ici deux choses distinctes :
- l'**état mutable** du desk (`mm_desk`) — qui doit s'accumuler trade après trade ;
- le **cache de calcul** (`market_data`, `spot_price`, `r`) — coûteux à produire, constant ensuite.

C'est exactement le bon usage, et c'est l'erreur numéro un des débutants sur Streamlit.

Trois raccourcis locaux (`desk`, `data`, `spot`, `r`) sont ensuite extraits du session state pour alléger la suite du code.

**3. Sidebar — le terminal d'exécution**

Le formulaire est encapsulé dans `with st.sidebar.form("trade_form"):`. *Pourquoi un formulaire :* sans lui, **chaque frappe au clavier déclencherait un rerun complet** du script. Le `st.form` met les saisies en tampon et ne déclenche qu'une seule exécution, au clic sur `st.form_submit_button`. C'est le bon réflexe de performance.

Les champs sont disposés en paires via `st.columns(2)` : ticker / sens (Buy-Sell), strike / type (call-put), puis la quantité. Les types sont contraints à la source — `selectbox` pour les valeurs fermées, `number_input` pour les numériques — ce qui élimine par construction toute une classe d'erreurs de saisie.

**4. Logique d'exécution (déclenchée sur `if submitted:`)**

C'est la séquence métier complète, en cinq temps :

```python
row_order = data[option_type + "s"][data[option_type + "s"]["strike"] == strike].iloc[0]

option      = EuropeanOption(spot, strike, row_order["T"], r, row_order["IV"], option_type)
prix_theo   = option.price()          # 1. pricing à l'IV de marché
delta_order = option.delta()

option_id   = f"{ticker}_{option_type}_{int(strike)}"
bid, ask    = desk.quote_price(prix_theo, option_id)   # 2. cotation

if action_type.lower() == "buy":                       # 3. exécution
    desk.execute_trade(quantity, bid, option_id, "sell")
else:
    desk.execute_trade(-quantity, ask, option_id, "buy")

risque_delta = desk.inventory[option_id] * delta_order # 4. risque agrégé
desk.hedge_delta(ticker, risque_delta, spot)           # 5. couverture
```

**Le point financièrement juste :** l'option n'est pas repricée avec une volatilité arbitraire mais avec **sa propre IV de marché** (`row_order["IV"]`), issue de l'étape d'enrichissement. Le prix théorique retombe donc sur le mid observé, et la cotation du desk s'articule autour de ce prix. C'est la logique correcte d'un desk : on cote autour du marché, pas autour d'un modèle déconnecté.

**Le second point juste :** `risque_delta = inventory × delta` — le hedge est calculé sur le **delta agrégé de la position**, pas sur le delta unitaire d'une option. Détenir 100 calls de delta 0.53 expose à 53 actions équivalentes, et c'est bien ce montant qui est couvert. Le `hedge_delta` étant incrémental, chaque nouvel ordre **ajuste** la couverture existante au lieu de la recréer — c'est du rehedging dynamique correct.

Un `try/except IndexError` intercepte proprement le cas où l'utilisateur demande un strike absent du carnet, et affiche `st.sidebar.error` au lieu de faire tomber l'application.

**5. Dashboard principal**

Quatre KPI en ligne via `st.columns(4)` et `st.metric` :

| KPI | Calcul |
|---|---|
| Trésorerie (Cash) | `desk.cash`, formaté avec séparateur de milliers |
| Contrats Ouverts | `sum(abs(q) for q in desk.inventory.values())` — l'**exposition brute**, qui compte les positions longues et courtes en valeur absolue (une position +100 / −100 n'est pas « plate » en risque opérationnel) |
| Couverture Delta | le dictionnaire `stocks_quantity` aplati en chaîne lisible, ou « Neutre » si vide |
| Spot Price Référence | le spot de la session |

Puis deux panneaux en `st.columns([1.2, 1])` :
- **à gauche**, l'inventaire converti en `DataFrame` par compréhension de liste et affiché via `st.dataframe(..., hide_index=True)`, avec un `st.info` de repli quand le carnet est vide ;
- **à droite**, le **skew de volatilité** tracé en matplotlib avec une palette néon sur fond sombre (`#0E1117`, la couleur de fond native de Streamlit), calls en vert `#00FFAA` et puts en rouge `#FF4B4B`. Le thème est appliqué explicitement — `set_facecolor`, `tick_params`, couleur des `spines` et de la légende — car matplotlib produit par défaut un graphe blanc qui jurerait sur un dashboard sombre.

---

### 3.3 `main.py` — **terminal de trading interactif (refactoré, 51 lignes)**

**Rôle :** la même application, en ligne de commande. Boucle interactive qui enchaîne les ordres jusqu'à ce que l'utilisateur sorte.

**Importe :** les six modules du projet — `plot_volatility_skew`, `MarketDataCleaner`, `EuropeanOption`, `MarketMaker`, `get_mock_option_chain`, `enrich_options_data`.

**Ce qui a changé par rapport à la version précédente :** le fichier est passé de 77 à 51 lignes tout en faisant davantage.

| Avant | Maintenant |
|---|---|
| Données mock recopiées en dur (25 lignes) | `get_mock_option_chain()` |
| `calculate_row_iv` redéfini localement | `enrich_options_data()` |
| Tracé matplotlib inline | `plot_volatility_skew()` |
| Appels `MarketMaker` sur l'ancienne signature → `TypeError` | Signatures correctes (`option_id`, `ticker`) |
| Un seul trade codé en dur | Boucle interactive multi-trades |
| Delta unitaire passé au hedge | `inventory × delta` — delta agrégé |

**Les trois modules qui étaient orphelins sont désormais branchés**, et toute la duplication de code a disparu.

**Déroulé :**

1. **Setup** — `get_mock_option_chain()` → `MarketDataCleaner(...).process()` → `enrich_options_data(...)` avec `r = 0.04`. Trois lignes pour tout le pipeline de données.
2. **Boucle `while True`** — demande `Nouveau Trade? (Yes/No, ou 'exit' pour quitter)`, sort sur `no` ou `exit`.
3. **Saisie** — strike, type d'option, sens (Buy/Sell), ticker, quantité.
4. **Exécution** — séquence identique à `app.py` : lecture de la ligne du carnet, pricing à l'IV de marché, construction de l'`option_id`, cotation, exécution, calcul du delta agrégé, hedge.
5. **Reporting** — état du desk après chaque trade : cash formaté à 2 décimales, position en actions sur le ticker, inventaire complet.

**Vérifié à l'exécution** — un achat de 100 calls ATM (strike 540) sur AAPL donne :
```
--- ÉTAT DU DESK ---
Cash: 27682.58 | Actions AAPL: -53.477 | Inventaire: {'AAPL_call_540': 100}
```
La lecture est cohérente : le desk achète 100 calls à son bid (sortie de trésorerie), puis se couvre en **vendant à découvert 53,48 actions** — parce qu'être long 100 calls de delta 0,535 équivaut à être long 53,5 actions, exposition qu'on annule en vendant le même montant. La vente rapporte plus que l'achat des options n'a coûté, d'où le cash positif.

**Note :** l'appel `plot_volatility_skew(clean_data)` est présent mais **commenté**. C'est un choix défendable en mode terminal : `plt.show()` est bloquant et gèlerait la boucle de saisie tant que la fenêtre du graphe reste ouverte. Le graphe reste disponible dans `app.py`, où Streamlit le rend sans bloquer.

---

### 3.4 `market_data/data_fetcher.py` — acquisition de données réelles

**Rôle :** encapsuler tous les appels réseau vers Yahoo Finance. C'est la seule classe du projet qui fait de l'I/O externe.

**Dépendances :** `yfinance` (wrapper de l'API Yahoo Finance), `pandas`, `requests`, `urllib3`.

**Importé par :** `tests/test_fetcher.py`.
**Importe :** rien du projet.

#### Classe `MarketDataFetcher`

**`__init__(ticker_symbol)`** — crée une session `requests` persistante et instancie un objet `yf.Ticker`. La session est réutilisée entre les appels, ce qui évite de rouvrir une connexion TCP à chaque requête et limite les problèmes de *rate limiting* de Yahoo.

**`get_expirations()`** — renvoie le tuple de toutes les dates d'échéance cotées pour ce sous-jacent (ex : `('2026-08-21', '2026-08-28', '2026-09-18', ...)`).

**`get_option_chain(expiration_date)`** — renvoie la **chaîne d'options** pour une maturité : un dictionnaire `{'calls': DataFrame, 'puts': DataFrame}`. Chaque DataFrame contient une ligne par strike coté, avec bid, ask, volume, open interest, etc.

**`get_current_spot()`** — renvoie le dernier cours de clôture. Le commentaire du code explique le choix technique : `history(period="1d")` est préféré à `fast_info` **pour réduire les erreurs de rate limit** de l'API Yahoo. Lève une `ValueError` explicite si l'historique revient vide.

**Point d'attention sécurité :** `self.session.verify = False` désactive la vérification des certificats TLS, et `urllib3.disable_warnings(...)` masque l'avertissement associé. C'est un contournement classique de proxy d'entreprise / inspection SSL, mais qui expose techniquement à une attaque man-in-the-middle. À réactiver (ou à remplacer par un bundle de CA d'entreprise via la variable `REQUESTS_CA_BUNDLE`) hors environnement contrôlé.

---

### 3.5 `market_data/data_feed.py` — jeu de données simulé

**Rôle :** fournir une chaîne d'options factice mais **réaliste**, pour développer et tester sans dépendre du réseau. C'est la source utilisée par les deux interfaces.

**Dépendances :** `pandas`.
**Importé par :** `app.py`, `main.py`.

**`get_mock_option_chain()`** — renvoie le triplet `(spot_price, expiration_date, raw_chain_mock)` avec :
- un spot à 540 $ (calibré sur le SPY),
- 13 strikes de 480 à 600 (couvrant largement autour de la monnaie),
- des bid/ask **cohérents avec la réalité de marché** : décroissants pour les calls quand le strike monte, croissants pour les puts, avec un spread qui s'élargit en relatif sur les options loin de la monnaie,
- des volumes en **cloche centrée sur le spot** (2500 contrats au strike 540, 50 aux extrémités) — reproduisant fidèlement le fait que la liquidité se concentre à la monnaie.

**Pourquoi c'est un vrai point positif :** avoir un *fixture* de données découplé de la source réelle est une pratique d'ingénierie logicielle mature. Ça rend le développement déterministe et reproductible, et ça permet de faire tourner le dashboard en démonstration sans dépendre de la disponibilité de Yahoo Finance — un vrai atout si le projet est montré en entretien.

---

### 3.6 `market_data/data_cleaner.py` — normalisation

**Rôle :** transformer une chaîne d'options brute en données exploitables par le moteur de pricing.

**Dépendances :** `pandas`, `numpy`, `datetime`.
**Importé par :** `app.py`, `main.py`.

#### Classe `MarketDataCleaner`

**`__init__(raw_chain, expiration_date)`** — copie défensive des DataFrames (`.copy()`), ce qui évite de modifier les données d'origine de l'appelant. **Bon réflexe pandas** : sans ça, on s'expose à des effets de bord et au `SettingWithCopyWarning`.

**`calculate_time_to_maturity()`** — convertit la date d'échéance en **maturité fractionnaire en années** :
```python
(Expiration_date - Today).days / 365.25
```
Le `365.25` intègre les années bissextiles. Cette conversion est indispensable car Black-Scholes raisonne en années, pas en dates. (Convention *calendar days* / ACT-365.25 ; les desks utilisent parfois une convention *business days* pour mieux capter le fait que la volatilité ne se réalise que les jours ouvrés.)

**`clean_dataframe(df)`** — deux opérations :
1. Calcule le **mid-price** : `(bid + ask) / 2`. C'est la meilleure estimation ponctuelle de la « vraie » valeur d'une option, non polluée par le spread bid/ask (qui est la rémunération du market maker, pas de l'information de prix).
2. Filtre `volume > 0 AND bid > 0`. **C'est un filtre de liquidité crucial :** une option sans volume n'a pas de prix fiable (la cotation est un affichage automatique, pas une transaction réelle), et un bid nul signale une option sans valeur ou sans marché. Les inclure produirait des volatilités implicites aberrantes qui déformeraient complètement le skew.

**`process()`** — orchestre le nettoyage sur les calls et les puts, et injecte la colonne `T` dans les deux DataFrames. Renvoie le dictionnaire nettoyé.

---

### 3.7 `market_data/data_enricher.py` — calcul de la structure de volatilité implicite

**Rôle :** ajouter la colonne `IV` (volatilité implicite) à chaque ligne de la chaîne d'options.

**Dépendances :** `pricing_engine.black_scholes.EuropeanOption` — **c'est le pont entre la couche données et la couche modèle**.
**Importé par :** `app.py`, `main.py`.

**`enrich_options_data(clean_data, spot_price, risk_free_rate)`**

Contient une fonction imbriquée `calculate_row_iv(row, spot, risk_free_rate, option_type)` qui, pour une ligne de DataFrame :
1. instancie une `EuropeanOption` avec les paramètres de la ligne (`row['strike']`, `row['T']`) et une volatilité initiale arbitraire de 0.2 — qui sera de toute façon écrasée par `brentq` ;
2. appelle `implied_volatility(row['mid_price'])`.

Puis applique cette fonction ligne par ligne via `df.apply(..., axis=1)` sur les calls et les puts.

Le résultat est la **structure de volatilité implicite** — la donnée la plus importante d'un desk d'options, et celle qui alimente à la fois le graphe du skew et le pricing de chaque ordre.

---

### 3.8 `market_making/pricer_mm.py` — simulateur de desk

**Rôle :** modéliser le comportement d'un market maker sur options : coter, trader, se couvrir.

**Dépendances :** aucune (Python pur — pas même numpy). Volontairement découplé du pricing engine.
**Importé par :** `app.py`, `main.py`.

#### Classe `MarketMaker`

**`__init__(base_spread=0.10, risk_aversion=0.01)`**

| Attribut | Rôle |
|---|---|
| `base_spread` | Largeur de la fourchette bid/ask = la marge brute du MM |
| `risk_aversion` | Coefficient d'ajustement du prix en fonction du stock détenu |
| `inventory` | `dict {option_id: quantité}` — position en options, par instrument |
| `cash` | Trésorerie (float) |
| `stocks_quantity` | `dict {ticker: quantité}` — position de couverture en actions |

L'utilisation de **dictionnaires indexés par instrument** permet de gérer un portefeuille multi-options / multi-sous-jacents. Les deux interfaces exploitent pleinement cette capacité : l'`option_id` est construit comme `f"{ticker}_{option_type}_{int(strike)}"`, ce qui donne une clé unique et lisible par instrument (`AAPL_call_540`), et le hedge est indexé par ticker.

**`quote_price(theorical_price, option_id)` — cotation avec inventory skewing**

```python
price_shift    = -(self.inventory[option_id] * self.risk_aversion)
adjusted_price = theorical_price + price_shift
bid = adjusted_price - base_spread/2
ask = adjusted_price + base_spread/2
```

*Le concept financier — l'« inventory skewing » :* un market maker ne veut pas accumuler de position directionnelle, il veut gagner le spread. S'il a déjà **acheté** beaucoup d'options (inventaire positif), il devient exposé et **baisse sa cotation** pour décourager les vendeurs et attirer les acheteurs — jusqu'à revenir à plat. Le signe négatif du `price_shift` encode exactement ce mécanisme, et `risk_aversion` en règle l'agressivité.

C'est le principe fondateur du modèle **Avellaneda-Stoikov** de market making optimal, ici sous une forme linéaire simplifiée. L'effet est directement observable dans le dashboard : après un gros achat, la cotation suivante sur le même `option_id` est décalée vers le bas.

**`execute_trade(quantity, execution_price, option_id, action_client="buy")`**

Met à jour le cash et l'inventaire en fonction du sens du trade, du **point de vue du client** :
- `action_client="sell"` → le client vend, le MM **achète** : `cash -= quantity × prix`, `inventory += quantity`.
- `action_client="buy"` → le client achète, le MM **vend** : `cash += quantity × prix`, `inventory -= quantity`.

La méthode gère donc **déjà** le signe via `action_client`. C'est précisément la source du bug décrit en §7.1 : les deux interfaces passent en plus une quantité négative dans la branche « vente », ce qui annule l'inversion.

**`hedge_delta(ticker, portfolio_delta, current_spot_price)` — la couverture en delta**

```python
target_stocks_quantity = -portfolio_delta
stocks_adjustment      = target - stocks_quantity[ticker]
stocks_quantity[ticker] += stocks_adjustment
cash += -(current_spot_price * stocks_adjustment)
```

*Le concept financier — le delta hedging :* c'est le cœur du métier de trader d'options. L'idée de Black-Scholes est qu'une option peut être **répliquée dynamiquement** par une position sur le sous-jacent. Si un MM est long un call de delta +0.5, il gagne quand l'action monte : il est exposé au sens du marché, ce qu'il ne veut pas. Il **vend 0.5 action** pour annuler cette exposition.

Le portefeuille combiné devient **delta-neutre** : insensible aux petites variations du sous-jacent. Le trader ne conserve alors que son exposition à la **volatilité** (vega) et à la **convexité** (gamma) — c'est précisément ce qu'il cherche à négocier.

La méthode calcule la position cible (`−delta`), en déduit l'**ajustement incrémental** nécessaire par rapport à la position existante (et non un remplacement brut), puis débite/crédite le cash du coût d'achat/vente des actions. Cette logique incrémentale est ce qui permet le **rehedging dynamique** au fil des ordres successifs — chaque nouveau trade ne recalcule que le delta à ajouter.

**Bloc `if __name__ == "__main__":`** — scénario de démonstration autonome hérité de la phase de développement. Il utilise **l'ancienne signature** des méthodes (sans `option_id` ni `ticker`) et lèverait donc une `TypeError` s'il était exécuté directement (`python market_making/pricer_mm.py`). Sans effet sur l'application, puisque ce bloc ne s'exécute jamais à l'import.

---

### 3.9 `visualisation/plots.py` — tracé du skew

**Rôle :** isoler la logique matplotlib hors des points d'entrée. Le fichier, autrefois vide, contient maintenant la fonction extraite de l'ancien `main.py`.

**Dépendances :** `matplotlib.pyplot`.
**Importé par :** `main.py` (appel actuellement commenté).

**`plot_volatility_skew(clean_data)`** — trace l'IV en fonction du strike : calls en bleu trait plein avec marqueurs ronds, puts en rouge pointillé avec croix, plus titre, axes légendés et `plt.show()`.

`app.py` n'utilise pas cette fonction et construit son propre graphe, pour deux raisons techniques : Streamlit exige un objet `Figure` explicite passé à `st.pyplot(fig)` plutôt que l'interface d'état global `plt`, et le thème sombre du dashboard demande une configuration de couleurs que cette fonction ne prend pas en paramètre. Une évolution naturelle serait de faire accepter à `plot_volatility_skew` un argument `ax` optionnel, ce qui la rendrait réutilisable par les deux interfaces.

---

### 3.10 `tests/test_black_scholes.py`

**Rôle :** valider le moteur de pricing par une relation de **non-arbitrage**.

**`test_call_put_parity()`** — vérifie la **parité call-put** :

```
C − P = S − K·e^(−rT)
```

*Vulgarisation :* acheter un call et vendre un put de même strike et même échéance donne exactement le même profil de gain qu'acheter l'action à crédit. Ces deux stratégies doivent donc coûter le même prix — sinon il existerait un arbitrage sans risque. Cette relation ne dépend **d'aucun modèle** : elle découle uniquement de l'absence d'opportunité d'arbitrage.

C'est donc un **excellent test** : il vérifie simultanément la cohérence de la formule call, de la formule put, de l'actualisation, et des signes — le tout sans avoir à coder en dur une valeur de référence.

Le test est paramétré à la monnaie (S = K = 100, T = 1 an, r = 4 %, σ = 20 %) et compare à 5 décimales avec `np.testing.assert_almost_equal`. **Il passe.**

### 3.11 `tests/test_fetcher.py`

**Rôle :** vérifier manuellement que la connexion à Yahoo Finance fonctionne (récupération du spot SPY + nombre de maturités disponibles), avec affichage ✅ / ❌.

Ce n'est pas un test pytest au sens strict : c'est du code au niveau module, sans fonction `test_*`, donc pytest ne le collecte pas comme cas de test. C'est un **script de diagnostic**, utile en pratique pour distinguer un bug de code d'un problème réseau.

### 3.12 Fichiers annexes

| Fichier | Contenu |
|---|---|
| `market_data/__init__.py`, `pricing_engine/__init__.py`, `tests/__init__.py` | Vides — marquent les répertoires comme packages Python |
| `requirements.txt` | 37 dépendances figées via `pip freeze`. Encodage **UTF-16** (généré par une redirection PowerShell). **Ne contient pas `streamlit`** alors que `app.py` en dépend (voir §7.3) |
| `.gitignore` | Exclut `venv/`, `__pycache__/`, `.pytest_cache/` — correct et minimal |

**Dépendances réellement utilisées :** `streamlit` (1.61.1, installé), `numpy`, `scipy`, `pandas`, `matplotlib`, `yfinance`, `requests`, `pytest`. Le reste sont des dépendances transitives.

**Documentation existante :** aucun README utilisateur. Les docstrings sont présentes et de bonne qualité sur `EuropeanOption`, `MarketDataFetcher` et `MarketDataCleaner` (format `:param:` de type reStructuredText), plus rares sur `MarketMaker`. `app.py` est structuré par commentaires de section (`# --- SIDEBAR ... ---`), ce qui le rend très lisible malgré sa longueur. Commentaires en français, code et noms de variables en anglais.

---

## 4. Concepts techniques et financiers utilisés

### 4.1 Concepts financiers

**Option européenne** — contrat donnant le *droit* (non l'obligation) d'acheter (*call*) ou de vendre (*put*) un actif à un prix fixé (strike), à une date fixée. Le gain à l'échéance est `max(S−K, 0)` pour un call, `max(K−S, 0)` pour un put.

**Modèle de Black-Scholes-Merton (1973)** — suppose que le cours du sous-jacent suit un **mouvement brownien géométrique** (rendements log-normaux, volatilité et taux constants) et démontre qu'on peut couvrir une option en ajustant continûment une position sur le sous-jacent. Ce raisonnement de **réplication dynamique** donne un prix unique, indépendant des anticipations de rendement de chacun (**valorisation risque-neutre**). Prix Nobel 1997.

**Les grecques** — les cinq sensibilités implémentées (delta, gamma, vega, theta, rho) constituent le tableau de bord quotidien d'un trader d'options. Elles permettent de décomposer le P&L : *combien ai-je gagné parce que le marché a bougé (delta/gamma), parce que la vol a bougé (vega), parce que le temps a passé (theta) ?*

**Volatilité implicite** — la volatilité qui, injectée dans Black-Scholes, redonne le prix coté. C'est la manière dont le marché exprime ses anticipations d'agitation future. Sur un desk, on ne cote pas les options en dollars mais **en points de vol** : la vol implicite est la véritable devise du marché des options. Dans ce projet, elle est calculée une fois à l'initialisation puis **réutilisée pour pricer chaque ordre**, ce qui ancre les cotations sur le marché observé.

**Skew / smile de volatilité** — si Black-Scholes était exact, l'IV serait identique pour tous les strikes. Elle ne l'est pas : sur actions elle décroît avec le strike (**skew**), sur devises elle forme un **smile** symétrique. C'est le signe empirique que la distribution réelle des rendements a des queues plus épaisses qu'une loi normale, particulièrement à gauche. Le projet **calcule et affiche ce skew**, et le retrouve bien sur les données de test (30 % à K=480 → 15,7 % à K=590).

**Mid-price** — `(bid+ask)/2`, l'estimateur non biaisé du prix « vrai » d'un instrument coté en fourchette.

**Filtrage de liquidité** — retirer les options sans volume ni bid, dont les cotations affichées ne reflètent aucune transaction réelle et produiraient des IV parasites.

**Market making** — l'activité qui consiste à afficher en permanence un prix acheteur et un prix vendeur, en se rémunérant sur la fourchette, tout en gérant le risque d'inventaire.

**Inventory skewing** — décaler sa cotation en fonction de la position détenue pour inciter le flux à ramener l'inventaire vers zéro. Version simplifiée d'**Avellaneda-Stoikov**.

**Delta hedging** — neutraliser l'exposition directionnelle en prenant une position opposée sur le sous-jacent, pour ne conserver que l'exposition à la volatilité. Implémenté ici en **incrémental** (rehedging à chaque ordre) et sur le **delta agrégé** de la position, pas sur le delta unitaire.

**Exposition brute** — la somme des valeurs absolues des positions. Distincte de l'exposition nette : un portefeuille long 100 / short 100 est net nul mais brut 200, et porte un vrai risque opérationnel. Le KPI « Contrats Ouverts » du dashboard mesure cette grandeur.

**Parité call-put** — relation d'arbitrage `C − P = S − K·e^(−rT)`, indépendante de tout modèle, utilisée ici comme test de validation.

**Actualisation** — le facteur `e^(−rT)` traduit qu'un euro reçu dans T années vaut moins qu'un euro aujourd'hui (valeur temps de l'argent).

### 4.2 Concepts techniques

**Analyse numérique — méthode de Brent** — algorithme de recherche de racine hybride (bissection + sécante + interpolation quadratique inverse) : convergence garantie *et* rapide. Utilisé pour inverser Black-Scholes, qui n'est pas inversible analytiquement en σ.

**Programmation orientée objet** — encapsulation du modèle dans `EuropeanOption` et de l'état du desk dans `MarketMaker`. Chaque objet porte ses données et ses comportements.

**Gestion d'état applicatif (`st.session_state`)** — faire survivre un objet mutable aux réexécutions complètes du script imposées par Streamlit. Distinction claire entre l'état métier (le desk, qui doit s'accumuler) et le cache de calcul (les données de marché, coûteuses et constantes).

**Séparation front-end / back-end** — deux interfaces (`app.py`, `main.py`) pilotent le même moteur sans le dupliquer ni le modifier. C'est la démonstration pratique que le découpage en couches est réel et pas seulement déclaratif.

**Closures / fonctions imbriquées** — `objective_function` dans `implied_volatility` et `calculate_row_iv` dans `enrich_options_data` capturent leur contexte englobant. C'est le pattern idiomatique pour passer une fonction paramétrée à un solveur `scipy`.

**Manipulation pandas** — `df.apply(lambda row: ..., axis=1)` pour appliquer un calcul ligne par ligne ; masques booléens pour le filtrage et la sélection du strike ; `.copy()` défensif ; `.iloc[0]` pour l'accès positionnel ; construction d'un DataFrame par compréhension de liste pour l'affichage de l'inventaire.

**Architecture en couches** — séparation stricte données / modèle / trading / présentation / interface, avec un moteur de pricing sans aucune dépendance interne.

**Tests automatisés (pytest)** — validation par propriété mathématique plutôt que par valeur codée en dur.

**Injection de dépendance / mocking** — `MarketDataCleaner` reçoit sa chaîne d'options en paramètre au lieu d'aller la chercher elle-même : on peut donc lui injecter des données réelles *ou* simulées sans le modifier. C'est ce qui rend le pipeline testable et démontrable hors ligne.

**Gestion d'erreurs** — `try/except ValueError` avec repli sur `NaN` dans le calcul d'IV, `try/except IndexError` sur strike inexistant dans `app.py` (avec message utilisateur au lieu d'un plantage), `ValueError` explicite dans `get_current_spot()`.

**Optimisation d'interface** — `st.form` pour éviter un rerun à chaque frappe, initialisation conditionnelle pour ne calculer les IV qu'une fois par session, contrainte des saisies par le typage des widgets.

**Gestion de session HTTP** — réutilisation d'une session `requests` pour limiter le rate limiting de l'API Yahoo.

---

## 5. Points forts à mettre en avant sur un CV

### 5.1 Formulation possible pour le CV

> **Equity Derivatives Pricer & Market Making Desk — Python / Streamlit** *(projet personnel)*
> Moteur de valorisation d'options européennes et simulateur de desk de market making, avec dashboard web interactif.
> • Implémentation from scratch du modèle **Black-Scholes** et des cinq grecques (delta, gamma, vega, theta, rho) en NumPy/SciPy.
> • Extraction de la **volatilité implicite** par inversion numérique du modèle (algorithme de **Brent**, `scipy.optimize`) et reconstruction de la **courbe de skew** sur chaîne d'options complète.
> • **Pipeline de données de marché** end-to-end : ingestion Yahoo Finance (`yfinance`), nettoyage pandas, filtrage de liquidité, calcul de maturité, enrichissement en IV.
> • Simulateur de **market making** : cotation bid/ask avec **inventory skewing** (inspiré d'Avellaneda-Stoikov), exécution multi-instruments, **delta hedging** dynamique et incrémental, suivi de trésorerie et de position.
> • **Dashboard Streamlit** temps réel : saisie d'ordres, KPI de risque, inventaire et visualisation du skew, avec état de session persistant.
> • Architecture modulaire en couches (deux interfaces sur un même backend), tests **pytest** validés par relation de **parité call-put** (non-arbitrage).

### 5.2 Ce qui démontre le mieux vos compétences (par ordre d'impact en entretien)

**1. La volatilité implicite par méthode de Brent — votre meilleur atout technique.**
C'est ce qui sépare un projet « j'ai codé la formule de Black-Scholes » (que tout le monde fait) d'un projet qui montre une vraie compréhension. Vous démontrez trois choses d'un coup : que vous savez que le modèle n'est pas inversible analytiquement, que vous connaissez les méthodes numériques de recherche de racine, et que vous comprenez ce que la vol implicite **signifie** économiquement. **Soyez prêt à expliquer pourquoi Brent plutôt que Newton-Raphson** — réponse : Newton converge plus vite grâce au vega comme dérivée analytique, mais peut diverger sur les options très loin de la monnaie où le vega tend vers zéro ; Brent garantit la convergence par encadrement.

**2. Le dashboard Streamlit — votre meilleur atout de présentation.**
C'est ce qui rend le projet **démontrable en trente secondes** face à un recruteur, au lieu d'exiger qu'il lise votre code. Un pricer qui reste en console reste abstrait ; un desk qu'on manipule en direct, avec des KPI qui bougent et un skew affiché, raconte immédiatement l'histoire. Deux points à savoir défendre :
- **Pourquoi `st.session_state` est indispensable** : Streamlit réexécute tout le script à chaque interaction ; sans lui, le desk perdrait sa position à chaque ordre. C'est *la* question technique sur Streamlit.
- **Pourquoi `st.form`** : éviter un rerun complet à chaque frappe au clavier.

**3. La séparation front-end / back-end démontrée, pas juste affirmée.**
Avoir **deux interfaces (`app.py` et `main.py`) qui pilotent le même moteur** sans le dupliquer est la preuve concrète que votre architecture en couches fonctionne. C'est un argument bien plus fort que « j'ai fait des modules » : vous pouvez montrer que la logique métier est identique des deux côtés et qu'aucune formule financière ne vit dans l'interface. Sur un poste de quant developer, **cette compétence pèse autant que la finance**.

**4. La reconstruction du skew.**
Passer d'une valorisation à l'unité à l'analyse d'une **structure** de volatilité est exactement le travail d'un desk. Le fait que votre code retrouve un skew baissier réaliste (30 % à K=480 → 15,7 % à K=590) prouve que le pipeline est correct de bout en bout. **Sachez expliquer pourquoi le skew existe** (couverture, queues de distribution, post-1987) — c'est une question d'entretien classique.

**5. Le market making avec inventory skewing et hedge agrégé.**
Très différenciant : la majorité des projets s'arrêtent au pricing. Vous ajoutez la **microstructure de marché** et la gestion du risque d'inventaire. Deux détails à mettre en avant :
- le lien avec **Avellaneda-Stoikov** (le skewing linéaire en est la forme simplifiée) ;
- le fait que `risque_delta = inventory × delta` couvre le **delta agrégé de la position**, et que `hedge_delta` est **incrémental** — donc que le rehedging fonctionne sur une suite d'ordres, pas juste sur un trade isolé.

**6. Le test par parité call-put.**
Détail qui en dit long : vous ne testez pas contre une valeur magique copiée d'un site, vous testez contre une **relation d'arbitrage fondamentale**. Un recruteur quant le remarquera.

**7. Le filtrage de liquidité.**
`volume > 0 AND bid > 0` : deux lignes, mais elles montrent que vous savez que les données de marché brutes sont sales et pourquoi ça compte. Beaucoup de projets académiques ignorent ce point et produisent des skews inexploitables.

### 5.3 Questions d'entretien à préparer sur ce projet

**Sur le quant :**
- Pourquoi Brent et pas Newton-Raphson pour l'IV ? Quelles sont les bornes et pourquoi ?
- Que se passe-t-il si `brentq` ne converge pas — et pourquoi renvoyer `NaN` plutôt que lever une exception ?
- Pourquoi la vol implicite n'est-elle pas constante alors que Black-Scholes le suppose ?
- Pourquoi utiliser le mid-price plutôt que le last, le bid ou le ask ?
- Que devient un portefeuille delta-neutre quand le sous-jacent bouge beaucoup ? *(→ le gamma : le delta change, il faut rehedger, et c'est là qu'on gagne ou perd)*
- Votre modèle ne gère pas les dividendes — quel est l'impact et comment l'ajouteriez-vous ? *(→ Black-Scholes-Merton avec rendement de dividende q : remplacer S par S·e^(−qT) et ajuster d1 ; sans ça les IV des puts sont biaisées)*
- Comment étendriez-vous le projet aux options américaines ? *(→ arbre binomial de Cox-Ross-Rubinstein ou différences finies, car exercice anticipé)*

**Sur l'ingénierie :**
- Pourquoi `st.session_state` ? Que se passerait-il sans ?
- Pourquoi votre pricing engine n'importe-t-il rien du reste du projet ?
- Comment testeriez-vous la logique du `MarketMaker` ? *(→ scénarios d'exécution : vérifier que cash et inventaire évoluent en sens opposés, qu'un aller-retour ramène l'inventaire à zéro et laisse le spread en gain)*
- Que faudrait-il pour brancher des données réelles à la place du mock ? *(→ rien dans le backend : remplacer l'appel à `get_mock_option_chain()` par `MarketDataFetcher` — c'est tout l'intérêt du découplage)*

---

## 6. Bilan de la qualité du code

**Ce qui est solide**
- Formules Black-Scholes et grecques **mathématiquement correctes** (vérifiées analytiquement et par le test de parité).
- Séparation des responsabilités nette entre les couches, **prouvée par la coexistence de deux interfaces**.
- Zéro duplication : après refactoring, chaque logique n'existe qu'à un seul endroit.
- Docstrings au format `:param:` sur les classes principales ; `app.py` structuré par commentaires de section.
- Nommage explicite et proche de la notation académique (`S`, `K`, `T`, `r`, `sigma`, `d1`, `d2`) — un quant lit ce code immédiatement.
- Copie défensive des DataFrames, initialisation défensive des dictionnaires.
- Gestion d'erreurs présente là où elle compte (I/O réseau, convergence numérique, saisie utilisateur).
- Bonnes pratiques Streamlit maîtrisées (`session_state`, `form`, typage des widgets).
- `.gitignore` correct dès le départ.

**Ce qui reste à corriger** — voir §7.

---

## 7. Points d'attention identifiés

*(Aucune modification n'a été apportée au code — ces éléments sont listés pour information.)*

### 7.1 Bug — le sens « vente » est inversé (`app.py` et `main.py`)

**Le symptôme :** le desk ne peut jamais se mettre en position vendeuse, et vendre lui coûte de la trésorerie au lieu de lui en rapporter.

**La cause :** `execute_trade` gère **déjà** le sens du trade via `action_client`. Les deux interfaces passent en plus une quantité négative dans la branche « vente », et les deux inversions s'annulent :

```python
if action_type.lower() == "buy":
    desk.execute_trade(quantity,  bid, option_id, "sell")   # correct
else:
    desk.execute_trade(-quantity, ask, option_id, "buy")    # double négation
```

**Vérifié à l'exécution** (100 contrats, bid 11,95 / ask 12,05) :

| Sens choisi | Cash obtenu | Inventaire obtenu | Attendu |
|---|---|---|---|
| Buy | −1 195,00 | +100 | ✅ conforme |
| Sell | −1 205,00 | **+100** | ❌ attendu : **+1 205,00** et **−100** |

Les deux sens produisent le même inventaire (+100). « Sell » se comporte comme « Buy » mais à un prix défavorable.

**Le correctif** — une seule ligne dans chaque fichier, passer la quantité en positif :
```python
desk.execute_trade(quantity, ask, option_id, "buy")
```
Vérifié : donne bien `cash = +1 205,00` et `inventory = −100`.

**L'effet de bord à noter :** ce bug masque aussi l'*inventory skewing* dans un sens. Comme l'inventaire ne peut que croître, la cotation ne se décale jamais vers le haut — or c'est précisément ce qui devrait se produire quand le desk est short et cherche à racheter.

### 7.2 Bug mineur — casse de `option_type` dans `main.py`

Le prompt affiche `Option Type ( Call or Put)`, mais la saisie sert de clé de dictionnaire :

```python
row_order = clean_data[option_type + "s"][...]
```

Les clés étant `'calls'` / `'puts'` en minuscules, taper `Call` — exactement ce que le message suggère — déclenche :
```
KeyError: 'Calls'
```
`app.py` n'est pas concerné : son `selectbox` impose `["call", "put"]`. Le correctif est un `.lower()` à la saisie. (`EuropeanOption` normalise déjà en interne, donc seule la lecture du DataFrame pose problème.)

### 7.3 `streamlit` absent de `requirements.txt`

`app.py` dépend de Streamlit (installé en 1.61.1 dans le venv), mais le fichier de dépendances — figé avant l'ajout du dashboard — ne le mentionne pas. Quelqu'un qui clone le projet et fait `pip install -r requirements.txt` ne pourra pas lancer l'application. À régénérer.

À la même occasion : le fichier est encodé en **UTF-16** (redirection PowerShell), ce qui peut faire échouer `pip install -r`. Régénérer avec un encodage UTF-8 règle les deux points d'un coup :

```bash
pip freeze | Out-File -Encoding utf8 requirements.txt
```

### 7.4 Points techniques mineurs

- **Figure matplotlib jamais fermée** (`app.py`) : `fig, ax = plt.subplots(...)` crée une figure à chaque rerun, et Streamlit rerun à chaque interaction. Les figures s'accumulent dans le registre global de matplotlib. Un `plt.close(fig)` après `st.pyplot(fig)` évite l'accumulation sur une session longue.
- **`use_container_width` déprécié** dans les versions récentes de Streamlit (remplacé par `width`). Fonctionne encore en 1.61.1, mais émettra un avertissement à terme.
- **Bloc `__main__` obsolète** dans `pricer_mm.py` : utilise l'ancienne signature et lèverait une `TypeError` si le fichier était lancé directement. Sans impact sur l'application (jamais exécuté à l'import), mais à supprimer ou mettre à jour.
- **Packages incomplets** : `market_making/` et `visualisation/` n'ont pas de `__init__.py` (fonctionne en Python 3 via les *namespace packages*, mais l'incohérence avec les autres dossiers surprend).
- **`plot_volatility_skew` non réutilisable par `app.py`** : la fonction appelle `plt.show()` et ne prend pas d'axe en paramètre. Un argument `ax=None` optionnel la rendrait utilisable par les deux interfaces (voir §3.9).
- **Appel au graphe commenté dans `main.py`** — choix défendable (`plt.show()` bloquerait la boucle de saisie), mais qui mériterait un commentaire expliquant pourquoi.
- **`test_black_scholes.py`** fait `return np.testing.assert_almost_equal(...)` — le `return` est inutile (pytest juge sur l'absence d'exception) et déclenche un `PytestReturnNotNoneWarning` sur les versions récentes.
- **`test_fetcher.py`** n'est pas collecté comme test (pas de fonction `test_*`). Suite actuelle : **1 test, 1 passé**.
- **`session.verify = False`** dans `data_fetcher.py` : désactive la vérification TLS (voir §3.4).

### 7.5 Limites du modèle (assumées, à connaître)

- **Pas de dividendes** : le modèle ne prend pas de rendement `q`. Sur un sous-jacent comme le SPY (~1,3 % de rendement), cela biaise légèrement les IV, surtout sur les puts.
- **`theta` est annualisé** : la convention de desk est souvent la décote **journalière** (`theta / 365`).
- **Multiplicateur de contrat ignoré** : une option sur action américaine porte sur 100 titres. Le hedge de 100 contrats devrait donc mobiliser ~5 348 actions, pas 53,48. La logique est juste, l'échelle est celle d'un contrat unitaire — à documenter ou à corriger par un facteur `CONTRACT_SIZE = 100`.
- **Position en actions fractionnaire** : `stocks_quantity` accepte des valeurs décimales (−53,477). Réaliste pour un hedge théorique, pas pour un carnet d'ordres réel où il faudrait arrondir.
- **Pas de revalorisation du portefeuille** : le dashboard affiche la trésorerie et les positions, mais pas le **P&L mark-to-market** (valeur actuelle des options détenues + actions + cash). C'est l'ajout le plus naturel et le plus parlant.
- **Options européennes uniquement** : pas d'exercice anticipé, donc pas d'options américaines.

### 7.6 Pistes d'extension naturelles

Par rapport valeur/effort pour renforcer le projet sur un CV :

| Extension | Ce que ça démontre en plus |
|---|---|
| Corriger le sens « vente » (§7.1) et la casse (§7.2) | **Priorité n°1** — un desk qui ne peut pas vendre est incomplet, et c'est la première chose qu'un recruteur testera dans la démo |
| Ajouter `streamlit` à `requirements.txt` | Reproductibilité — le projet doit s'installer chez quelqu'un d'autre |
| Écrire un `README.md` avec capture d'écran du dashboard | Communication — c'est ce qu'on voit en premier sur GitHub |
| Afficher le **P&L mark-to-market** dans les KPI | Compréhension de la valorisation de portefeuille |
| Afficher les grecques agrégées du desk (delta, gamma, vega totaux) | Gestion de risque — vega et gamma sont les vraies expositions d'un MM |
| Tests sur `MarketMaker` (aller-retour, sens des flux) | Aurait attrapé le bug §7.1 — argument fort sur l'intérêt des tests |
| Ajouter le rendement de dividende `q` | Compréhension fine du modèle |
| **Pricer Monte-Carlo** comparé à la formule fermée | Simulation stochastique, convergence, réduction de variance |
| **Arbre binomial (CRR)** pour les options américaines | Méthodes numériques alternatives, exercice anticipé |
| Surface de vol 3D (strike × maturité) | Passage du skew à la **surface** — très parlant visuellement |
| Backtest du desk sur une série temporelle (P&L, rehedging) | Gestion de risque dynamique, gamma P&L |
| Calibration d'un modèle à vol stochastique (**Heston**, **SABR**) | Niveau quant senior |
