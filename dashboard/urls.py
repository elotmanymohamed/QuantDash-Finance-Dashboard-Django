from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='index'),
    path('assets/', views.assets_list, name='assets'),
    path('assets/<str:ticker>/', views.asset_detail, name='asset_detail'),
    path('risk/', views.risk_view, name='risk'),
    # JSON API
    path('api/nav/', views.api_nav_series, name='api_nav'),
    path('api/holdings/', views.api_holdings, name='api_holdings'),
    path('api/ohlcv/<str:ticker>/', views.api_ohlcv, name='api_ohlcv'),
]
