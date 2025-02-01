from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/search_stations/", views.search_stations, name="search_stations"),
    path("api/get_station_data/", views.get_station_data, name="get_station_data"),
]
