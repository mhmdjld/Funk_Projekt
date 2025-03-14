import math
import gzip
import pandas as pd
import requests
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest


def index(request):
    """
    Liefert die Startseite (das Frontend) aus templates/frontend.html.
    """
    return render(request, "frontend.html")


def haversine(lat1, lon1, lat2, lon2):
    """
    Berechnet die Distanz (in Kilometern) zwischen zwei Punkten (lat: (Breite), lon: (Länger))
    mittels der Haversine-Formel.
    """
    R = 6371  # Erdradius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def search_stations(request):
    """
    API-Endpunkt: Sucht nach Stationen anhand übergebener Parameter.

    Erwartete GET-Parameter:
      - latitude (Breite, float)
      - longitude (Länge, float)
      - radius (Suchradius in km, Standard: 10 km)
      - station_count (Anzahl der Wetterstationen)
      - start_year (nur Stationen anzeigen, die seit diesem Jahr existieren)
      - end_year (Stationen müssen bis dieses Jahres Daten haben)
    """
    try:
        lat = float(request.GET.get('latitude'))
        lon = float(request.GET.get('longitude'))
        radius = float(request.GET.get('radius', 10))  # Standard: 10 km

        station_count_str = request.GET.get('station_count', '')
        if not station_count_str:
            station_count = None  # Kein Wert
        else:
            station_count = int(station_count_str)
        start_year = int(request.GET.get('start_year'))
        end_year = int(request.GET.get('end_year'))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Ungültige Parameter.")
    # Falls station_count nicht angegeben wurde, eine leere Liste zurückgeben:
    if station_count is None:
        return JsonResponse({"stations": []})

    # Stationendaten abrufen
    stations_url = "https://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-stations.txt"
    try:
        response = requests.get(stations_url)
        if response.status_code != 200:
            return HttpResponseBadRequest("Fehler beim Abrufen der Stationendaten.")
        station_data = response.text.splitlines()
    except Exception as e:
        return HttpResponseBadRequest("Fehler beim Abrufen der Stationendaten: " + str(e))

    # Inventory Daten laden und filtern
    try:
        inventory_url = "https://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-inventory.txt"
        inv_response = requests.get(inventory_url)
        if inv_response.status_code != 200:
            return HttpResponseBadRequest("Fehler beim Abrufen der Inventardaten.")
        inventory_data = inv_response.text.splitlines()
    except Exception as e:
        return HttpResponseBadRequest("Fehler beim Abrufen der Inventardaten: " + str(e))

    # Baue ein Dictionary: station_id -> { "TMAX": (first_year, last_year), "TMIN": (first_year, last_year) }
    inventory = {}
    for line in inventory_data:
        parts = line.split()
        if len(parts) < 6:
            continue
        station_id = parts[0]
        element = parts[3]
        # Nur TMAX und TMIN berücksichtigen
        if element not in ["TMAX", "TMIN"]:
            continue
        try:
            first_year = int(parts[4])  # Erstes Jahr, in dem diese Messgröße vorliegt
            last_year = int(parts[5])   # Letztes Jahr, in dem diese Messgröße vorliegt
        except ValueError:
            continue
        if station_id not in inventory:
            inventory[station_id] = {}
        if element in inventory[station_id]:
            # Falls mehrere Einträge vorhanden sind, nehme den frühesten first_year und den spätesten last_year
            prev_first, prev_last = inventory[station_id][element]
            inventory[station_id][element] = (min(prev_first, first_year), max(prev_last, last_year))
        else:
            inventory[station_id][element] = (first_year, last_year)


    # Finde Stationen im Umkreis
    matching_stations = []
    # Fixed-Width-Parsing: ID [0:11], Latitude [12:20], Longitude [21:30], Name [41:71]
    for line in station_data:
        if len(line) < 71:
            continue
        station_id = line[0:11].strip()
        try:
            station_lat = float(line[12:20].strip())
            station_lon = float(line[21:30].strip())
        except ValueError:
            continue
        distance = haversine(lat, lon, station_lat, station_lon)
        if distance <= radius:
            station_name = line[41:71].strip()
            matching_stations.append({
                "id": station_id,
                "name": station_name,
                "latitude": station_lat,
                "longitude": station_lon,
                "distance": round(distance, 2)
            })

    # Station muss laut Inventor daten beide Messgrößen TMAX und TMIN haben und
    # der verfügbare Zeitraum muss den gesamten Zeitraum von start_year bis end_year abdecken
    filtered_stations = []
    for station in matching_stations:
        inv_data = inventory.get(station["id"])
        if inv_data and "TMAX" in inv_data and "TMIN" in inv_data:
            tmax_first, tmax_last = inv_data["TMAX"]
            tmin_first, tmin_last = inv_data["TMIN"]
            effective_start = max(tmax_first, tmin_first)
            effective_end = min(tmax_last, tmin_last)
            if effective_start <= start_year and effective_end >= end_year:
                filtered_stations.append(station)

    filtered_stations.sort(key=lambda x: x["distance"])
    filtered_stations = filtered_stations[:station_count]
    return JsonResponse({"stations": filtered_stations})


def get_station_data(request):
    """
    API-Endpunkt: Ruft für eine ausgewählte Station und einen definierten Zeitraum
    (Start- und Endjahr) die zugehörige CSV.gz-Datei ab, parst diese mit pandas und
    berechnet die jährlichen sowie saisonalen Durchschnittswerte (nur TMAX und TMIN).

    Erwartete GET-Parameter:
      - station_id
      - start_year (z.B. 2000)
      - end_year (z.B. 2010)
    """
    station_id = request.GET.get("station_id")
    try:
        start_year = int(request.GET.get("start_year"))
        end_year = int(request.GET.get("end_year"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ungültige Jahresparameter."}, status=400)
    if not station_id:
        return JsonResponse({"error": "Station ID wird benötigt."}, status=400)

    # Verwende die URL aus dem S3-Bucket:
    station_data_url = f"https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/{station_id}.csv.gz"

    try:
        response = requests.get(station_data_url, stream=True)
        response.raise_for_status()
    except Exception as e:
        return JsonResponse({"error": f"Fehler beim Abrufen der Stationsdatei: {e}"}, status=400)

    try:
        with gzip.GzipFile(fileobj=response.raw) as f:
            data = pd.read_csv(
                f,
                header=None,
                names=['ID', 'DATE', 'ELEMENT', 'VALUE', 'M-FLAG', 'Q-FLAG', 'S-FLAG', 'OBS-TIME'],
                dtype={
                    'ID': str,
                    'DATE': str,
                    'ELEMENT': str,
                    'VALUE': float,
                    'M-FLAG': str,
                    'Q-FLAG': str,
                    'S-FLAG': str,
                    'OBS-TIME': str,
                },
                low_memory=False
            )
    except Exception as e:
        return JsonResponse({"error": f"Fehler beim Lesen der Stationsdatei: {e}"}, status=400)

    # Umwandeln der DATE-Spalte in ein Datetime-Objekt (Format: YYYYMMDD)
    data['DATE'] = pd.to_datetime(data['DATE'], format="%Y%m%d", errors='coerce')
    data = data.dropna(subset=['DATE'])
    data['YEAR'] = data['DATE'].dt.year
    data['MONTH'] = data['DATE'].dt.month

    # Für den Winter: Wir benötigen auch den Dezember des Vorjahres
    data = data[(data['YEAR'] >= start_year - 1) & (data['YEAR'] <= end_year)]

    # Nur Temperaturdaten (TMAX und TMIN) verarbeiten
    data = data[data['ELEMENT'].isin(['TMAX', 'TMIN'])]

    # Skalieren der Temperaturwerte (z.B. 250 -> 25.0 °C)
    data['VALUE'] = data['VALUE'] / 10.0

    # Ergebnis-Dictionaries initialisieren
    annual = {}
    seasonal = {}
    for year in range(start_year, end_year + 1):
        annual[year] = {"TMAX": {"avg": None}, "TMIN": {"avg": None}}
        seasonal[year] = {
            "spring": {"TMAX": None, "TMIN": None},
            "summer": {"TMAX": None, "TMIN": None},
            "autumn": {"TMAX": None, "TMIN": None},
            "winter": {"TMAX": None, "TMIN": None},
        }

    # Berechne jährliche Durchschnittswerte
    for year in range(start_year, end_year + 1):
        year_data = data[data['YEAR'] == year]
        if not year_data.empty:
            tmax_vals = year_data[year_data['ELEMENT'] == 'TMAX']['VALUE']
            tmin_vals = year_data[year_data['ELEMENT'] == 'TMIN']['VALUE']
            if not tmax_vals.empty:
                annual[year]["TMAX"]["avg"] = format(tmax_vals.mean(), '.1f')
            if not tmin_vals.empty:
                annual[year]["TMIN"]["avg"] = format(tmin_vals.mean(), '.1f')

    # Berechne saisonale Durchschnittswerte:
    for year in range(start_year, end_year + 1):
        # Frühling: März, April, Mai
        spring = data[(data['YEAR'] == year) & (data['MONTH'].isin([3, 4, 5]))]
        if not spring.empty:
            tmax_vals = spring[spring['ELEMENT'] == 'TMAX']['VALUE']
            tmin_vals = spring[spring['ELEMENT'] == 'TMIN']['VALUE']
            if not tmax_vals.empty:
                seasonal[year]["spring"]["TMAX"] = format(tmax_vals.mean(), '.1f')
            if not tmin_vals.empty:
                seasonal[year]["spring"]["TMIN"] = format(tmin_vals.mean(), '.1f')
        # Sommer: Juni, Juli, August
        summer = data[(data['YEAR'] == year) & (data['MONTH'].isin([6, 7, 8]))]
        if not summer.empty:
            tmax_vals = summer[summer['ELEMENT'] == 'TMAX']['VALUE']
            tmin_vals = summer[summer['ELEMENT'] == 'TMIN']['VALUE']
            if not tmax_vals.empty:
                seasonal[year]["summer"]["TMAX"] = format(tmax_vals.mean(), '.1f')
            if not tmin_vals.empty:
                seasonal[year]["summer"]["TMIN"] = format(tmin_vals.mean(), '.1f')
        # Herbst: September, Oktober, November
        autumn = data[(data['YEAR'] == year) & (data['MONTH'].isin([9, 10, 11]))]
        if not autumn.empty:
            tmax_vals = autumn[autumn['ELEMENT'] == 'TMAX']['VALUE']
            tmin_vals = autumn[autumn['ELEMENT'] == 'TMIN']['VALUE']
            if not tmax_vals.empty:
                seasonal[year]["autumn"]["TMAX"] = format(tmax_vals.mean(), '.1f')
            if not tmin_vals.empty:
                seasonal[year]["autumn"]["TMIN"] = format(tmin_vals.mean(), '.1f')
        # Winter: Dezember des Vorjahres plus Januar und Februar des laufenden Jahres
        winter = pd.concat([
            data[(data['YEAR'] == year - 1) & (data['MONTH'] == 12)],
            data[(data['YEAR'] == year) & (data['MONTH'].isin([1, 2]))]
        ])
        if not winter.empty:
            tmax_vals = winter[winter['ELEMENT'] == 'TMAX']['VALUE']
            tmin_vals = winter[winter['ELEMENT'] == 'TMIN']['VALUE']
            if not tmax_vals.empty:
                seasonal[year]["winter"]["TMAX"] = format(tmax_vals.mean(), '.1f')
            if not tmin_vals.empty:
                seasonal[year]["winter"]["TMIN"] = format(tmin_vals.mean(), '.1f')

    result = {"annual": annual, "seasonal": seasonal}
    return JsonResponse(result)
