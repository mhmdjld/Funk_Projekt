import os
import django
from django.conf import settings
from django.test import RequestFactory
from django.http import HttpResponse, QueryDict
import unittest
import gzip
from io import BytesIO
from unittest.mock import patch, MagicMock
import json
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "weather_stations.settings")
    django.setup()
    
# Importiere die Funktionen aus views.py
from weather_stations.views import index, haversine, search_stations, get_station_data  

class ViewsTestCase(unittest.TestCase):
    """
    Testfälle für die Funktionen in views.py.
    Hier werden Dummy-Daten für Frankfurt (Main und Riedberg) benutzt.
    """

    def setUp(self):
        # RequestFactory für Django-Tests initialisieren
        self.factory = RequestFactory()

    def test_haversine_function(self):
        # Teste die Distanzberechnung
        dist1 = haversine(50.1109, 8.6821, 50.1119, 8.6831)
        self.assertGreater(dist1, 0)
        self.assertLess(dist1, 2)  # Sollte weniger als 2 km sein

        dist2 = haversine(50.1109, 8.6821, 50.1700, 8.7000)
        self.assertGreater(dist2, 5)

    def test_index_view(self):
        # Teste die index-Funktion, die ein Template rendert
        with patch("weather_stations.views.render") as fake_render:
            fake_render.return_value = HttpResponse("MOCKED FRONTEND")
            req = self.factory.get("/")
            resp = index(req)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.content, b"MOCKED FRONTEND")
            fake_render.assert_called_once_with(req, "frontend.html")

    @patch("weather_stations.views.requests.get")
    def test_search_stations_success(self, mock_get):
        # search_stations-Funktion mit Dummy-Daten für Frankfurt testen.
        # Die Daten kommen aus ghcnd-stations.txt:
        # Format: ID (11 Zeichen), lat (8 Zeichen), lon (9 Zeichen) und Name (30 Zeichen).
        line1 = "{:<11} {:>8} {:>9}           {:<30}".format("FRK00000001", "50.1109", "8.6821", "FRANKFURT MAIN STATION")
        line2 = "{:<11} {:>8} {:>9}           {:<30}".format("FRK00000002", "50.1700", "8.7000", "FRANKFURT RIEDBERG")
        stat_data = line1 + "\n" + line2 + "\n"

        # Dummy-Daten für ghcnd-inventory.txt
        inv_data = (
            "FRK00000001 50.1109 8.6821 TMAX 2000 2020\n"
            "FRK00000001 50.1109 8.6821 TMIN 2000 2020\n"
            "FRK00000002 50.1700 8.7000 TMAX 2000 2020\n"
            "FRK00000002 50.1700 8.7000 TMIN 2000 2020\n"
        )

        fake_resp1 = MagicMock()
        fake_resp1.status_code = 200
        fake_resp1.text = stat_data

        fake_resp2 = MagicMock()
        fake_resp2.status_code = 200
        fake_resp2.text = inv_data

        # Reihenfolge: erst Stationen, dann Inventar
        mock_get.side_effect = [fake_resp1, fake_resp2]

        req = self.factory.get("/search_stations/", {
            "latitude": "50.1150",
            "longitude": "8.6850",
            "radius": "20",
            "station_count": "2",
            "start_year": "2005",
            "end_year": "2010",
        })
        resp = search_stations(req)
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.content)
        self.assertIn("stations", data)
        # Hier erwarte ich 2 Stationen
        self.assertEqual(len(data["stations"]), 2, "Es sollten 2 Stationen gefunden werden")

    def test_search_stations_missing_params(self):
        # Test, wenn keine Parameter mitgegeben werden -> 400
        req = self.factory.get("/search_stations/")
        resp = search_stations(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Ung\xc3\xbcltige Parameter", resp.content)

    @patch("weather_stations.views.requests.get")
    def test_search_stations_no_station_count(self, mock_get):
        # Test, wenn station_count fehlt -> leere Liste
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.text = ""
        mock_get.side_effect = [fake_resp, fake_resp]

        req = self.factory.get("/search_stations/", {
            "latitude": "50.1150",
            "longitude": "8.6850",
            "radius": "20",
            "start_year": "2005",
            "end_year": "2010",
        })
        resp = search_stations(req)
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.content)
        self.assertEqual(len(data["stations"]), 0)

    @patch("weather_stations.views.requests.get")
    def test_get_station_data_success(self, mock_get):
        # Teste get_station_data mit Dummy CSV.gz-Daten für Frankfurt Main Station.
        # CSV: TMAX=55 (entspricht 5.5°C), TMIN=25 (entspricht 2.5°C)
        csv_content = (
            "FRK00000001,20000101,TMAX,55,,,,\n"
            "FRK00000001,20000102,TMIN,25,,,,\n"
        ).encode("utf-8")
        gz_data = gzip.compress(csv_content)

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.raise_for_status.return_value = None
        fake_resp.raw = BytesIO(gz_data)

        mock_get.return_value = fake_resp

        req = self.factory.get("/get_station_data/", {
            "station_id": "FRK00000001",
            "start_year": "2000",
            "end_year": "2000",
        })
        resp = get_station_data(req)
        self.assertEqual(resp.status_code, 200, "get_station_data sollte 200 liefern")

        data = json.loads(resp.content)
        self.assertIn("annual", data)
        self.assertIn("seasonal", data)
        # Prüfe, ob TMAX und TMIN richtig umgerechnet wurden (5.5°C und 2.5°C)
        self.assertEqual(data["annual"]["2000"]["TMAX"]["avg"], "5.5")
        self.assertEqual(data["annual"]["2000"]["TMIN"]["avg"], "2.5")

    def test_get_station_data_missing_station_id(self):
        # Test, wenn station_id fehlt -> 400
        req = self.factory.get("/get_station_data/", {
            "start_year": "2000",
            "end_year": "2001",
        })
        resp = get_station_data(req)
        self.assertEqual(resp.status_code, 400)

    def test_get_station_data_invalid_years(self):
        # Test bei ungültigen Jahreswerten -> 400
        req = self.factory.get("/get_station_data/", {
            "station_id": "FRK00000001",
            "start_year": "abc",
            "end_year": "2001",
        })
        resp = get_station_data(req)
        self.assertEqual(resp.status_code, 400)

    @patch("weather_stations.views.requests.get")
    def test_get_station_data_fetch_error(self, mock_get):
        # Simuliere einen Fehler beim Abrufen der CSV -> 400
        fake_resp = MagicMock()
        fake_resp.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = fake_resp

        req = self.factory.get("/get_station_data/", {
            "station_id": "FRK00000001",
            "start_year": "2000",
            "end_year": "2001",
        })
        resp = get_station_data(req)
        self.assertEqual(resp.status_code, 400)

if __name__ == "__main__":
    unittest.main()
