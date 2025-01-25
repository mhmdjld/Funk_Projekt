from django.contrib import admin
from django.urls import path
from .views import weather_map_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('weather-map/', weather_map_view, name='weather_map'),
]
