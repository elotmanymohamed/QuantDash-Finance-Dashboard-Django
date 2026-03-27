from django.db import models


class Asset(models.Model):
    """Represents a financial asset (stock, bond, ETF, etc.)"""
    ASSET_TYPES = [
        ('STOCK', 'Action'),
        ('BOND', 'Obligation'),
        ('ETF', 'ETF'),
        ('CRYPTO', 'Crypto'),
        ('COMMODITY', 'Matière Première'),
    ]

    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES, default='STOCK')
    sector = models.CharField(max_length=50, blank=True)
    current_price = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ticker']

    def __str__(self):
        return f"{self.ticker} — {self.name}"


class Portfolio(models.Model):
    """A collection of assets with allocation weights."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def total_value(self):
        return sum(
            h.quantity * h.asset.current_price
            for h in self.holdings.select_related('asset')
        )


class Holding(models.Model):
    """A position within a portfolio."""
    portfolio = models.ForeignKey(Portfolio, related_name='holdings', on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, related_name='holdings', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=16, decimal_places=6)
    avg_purchase_price = models.DecimalField(max_digits=12, decimal_places=4)
    purchase_date = models.DateField()

    class Meta:
        unique_together = ('portfolio', 'asset')

    def __str__(self):
        return f"{self.portfolio.name} — {self.asset.ticker} x{self.quantity}"

    def market_value(self):
        return self.quantity * self.asset.current_price

    def unrealized_pnl(self):
        return self.quantity * (self.asset.current_price - self.avg_purchase_price)

    def pnl_pct(self):
        if self.avg_purchase_price == 0:
            return 0
        return ((self.asset.current_price - self.avg_purchase_price) / self.avg_purchase_price) * 100


class PriceHistory(models.Model):
    """Daily OHLCV data for an asset."""
    asset = models.ForeignKey(Asset, related_name='price_history', on_delete=models.CASCADE)
    date = models.DateField()
    open_price = models.DecimalField(max_digits=12, decimal_places=4)
    high_price = models.DecimalField(max_digits=12, decimal_places=4)
    low_price = models.DecimalField(max_digits=12, decimal_places=4)
    close_price = models.DecimalField(max_digits=12, decimal_places=4)
    volume = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('asset', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.asset.ticker} — {self.date}"


class RiskMetric(models.Model):
    """Computed risk metrics for a portfolio (VaR, Sharpe, etc.)."""
    portfolio = models.ForeignKey(Portfolio, related_name='risk_metrics', on_delete=models.CASCADE)
    computed_at = models.DateTimeField(auto_now_add=True)
    var_95 = models.DecimalField(max_digits=10, decimal_places=4, help_text="Value at Risk 95%")
    var_99 = models.DecimalField(max_digits=10, decimal_places=4, help_text="Value at Risk 99%")
    sharpe_ratio = models.DecimalField(max_digits=8, decimal_places=4)
    volatility_annual = models.DecimalField(max_digits=8, decimal_places=4, help_text="Annualized volatility (%)")
    beta = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ['-computed_at']

    def __str__(self):
        return f"RiskMetrics({self.portfolio.name}) @ {self.computed_at.date()}"
