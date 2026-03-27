# QuantDash — Finance Dashboard Django

Dashboard analytique financier construit avec Django, Chart.js, et des données simulées
prêtes à être remplacées par de vraies sources de données (yfinance, Bloomberg API, etc.).

## Structure du projet

```
finance_dashboard/
├── manage.py
├── requirements.txt
├── finance_dashboard/          # Config Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── dashboard/                  # App principale
    ├── models.py               # Asset, Portfolio, Holding, PriceHistory, RiskMetric
    ├── views.py                # Dashboard, Assets, Risk + API JSON
    ├── urls.py
    ├── admin.py
    └── templates/dashboard/
        ├── base.html           # Layout sidebar + topbar
        ├── index.html          # Portfolio overview + NAV chart + donut
        ├── assets.html         # Asset screener
        └── risk.html           # VaR, Sharpe, histogramme des rendements
```

## Installation & Lancement

```bash
# 1. Créer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Migrations
python manage.py makemigrations
python manage.py migrate

# 4. Créer un superutilisateur (pour /admin/)
python manage.py createsuperuser

# 5. Lancer le serveur
python manage.py runserver
```

Accéder à : http://127.0.0.1:8000

## Pages disponibles

| URL           | Description                              |
|---------------|------------------------------------------|
| `/`           | Dashboard principal (KPIs, NAV, donut)   |
| `/assets/`    | Screener des positions                   |
| `/risk/`      | Risk analytics (VaR, Sharpe, histogramme)|
| `/admin/`     | Interface d'administration Django        |
| `/api/nav/`   | Endpoint JSON — série temporelle NAV     |
| `/api/holdings/` | Endpoint JSON — liste des positions   |

## Modèles de données

| Modèle        | Description                                      |
|---------------|--------------------------------------------------|
| `Asset`       | Actif financier (ticker, prix, type, secteur)    |
| `Portfolio`   | Portefeuille avec positions                      |
| `Holding`     | Position: qté, prix moyen, PnL latent            |
| `PriceHistory`| Données OHLCV journalières                       |
| `RiskMetric`  | VaR 95/99%, Sharpe, Volatilité, Beta             |

## Extensions possibles

- **yfinance** : remplacer les données mock par des prix réels
- **Celery + Redis** : calcul asynchrone des métriques de risque
- **Django REST Framework** : transformer les endpoints en API complète
- **PostgreSQL** : migrer de SQLite pour la production
- **Monte Carlo VaR** : implémenter la simulation de Monte Carlo dans `views.py`

## Calculs quantitatifs (à intégrer dans views.py)

```python
import numpy as np

def compute_var(returns: np.ndarray, confidence: float = 0.95) -> float:
    """Paramétric VaR under normality assumption."""
    from scipy.stats import norm
    mu, sigma = returns.mean(), returns.std()
    return mu + sigma * norm.ppf(1 - confidence)

def annualized_sharpe(returns: np.ndarray, rf: float = 0.0525/252) -> float:
    excess = returns - rf
    return (excess.mean() / excess.std()) * np.sqrt(252)
```
