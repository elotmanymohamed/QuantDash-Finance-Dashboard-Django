from django.contrib import admin
from .models import Asset, Portfolio, Holding, PriceHistory, RiskMetric


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['ticker', 'name', 'asset_type', 'current_price', 'currency', 'sector']
    list_filter = ['asset_type', 'currency']
    search_fields = ['ticker', 'name']


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'asset', 'quantity', 'avg_purchase_price', 'purchase_date']
    list_filter = ['portfolio']


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['asset', 'date', 'close_price', 'volume']
    list_filter = ['asset']
    date_hierarchy = 'date'


@admin.register(RiskMetric)
class RiskMetricAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'computed_at', 'var_95', 'sharpe_ratio', 'volatility_annual']
    list_filter = ['portfolio']
