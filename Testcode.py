import pandas as pd
import gzip

def get_temperature(station_id, year, temp_type):
    # Pfad zur Datei 
    file_path = f"/Users/robin/Documents/stations/{station_id}.csv.gz"
    
    try:
        # Datei entpacken und einlesen
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            df = pd.read_csv(f, header=None)
        
        # Spaltennamen definieren (basierend auf NOAA GHCN-D Format)
        df.columns = ["Station", "Date", "Element", "Value", "M-Flag", "Q-Flag", "S-Flag", "Obs-Time"]
        
        # Datum konvertieren
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d")
        
        # Daten für das angegebene Jahr filtern
        df_year = df[df["Date"].dt.year == year]
        
        # Temperaturart filtern (TMIN für minimale Temperaturen, TMAX für maximale Temperaturen)
        if temp_type.lower() == "min":
            df_filtered = df_year[df_year["Element"] == "TMIN"]
        elif temp_type.lower() == "max":
            df_filtered = df_year[df_year["Element"] == "TMAX"]
        else:
            raise ValueError("Ungültiger Temperaturtyp! Bitte 'min' oder 'max' angeben.")
        
        # Werte in Grad Celsius umrechnen (NOAA speichert Werte in Zehntel-Grad)
        temperature_celsius = df_filtered["Value"] / 10
        
        # Durchschnitt berechnen
        average_temperature = temperature_celsius.mean()
        
        # Ergebnis ausgeben
        print(f"Die durchschnittliche {temp_type.lower()}imale Temperatur für Station {station_id} im Jahr {year} beträgt {average_temperature:.2f}°C")
    
    except FileNotFoundError:
        print(f"Die Datei für Station {station_id} wurde nicht gefunden.")
    except Exception as e:
        print(f"Es gab einen Fehler: {e}")

# Benutzerabfragen für die Eingabe
station_id = input("Bitte gib die ID der Wetterstation ein: ")
year = int(input("Bitte gib das Jahr ein: "))
temp_type = input("Möchtest du die minimale oder maximale Temperatur? (min/max): ")

# Funktion aufrufen
get_temperature(station_id, year, temp_type)
