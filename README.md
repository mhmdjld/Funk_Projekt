# Installation von Funk_Projekt (Windows)

## Schritt 1: Voraussetzungen
Bevor Sie starten, stellen Sie bitte sicher, dass die folgenden Programme auf Ihrem System installiert sind:

### Docker installieren
- Docker Desktop für Windows herunterladen: [Docker Download](https://www.docker.com/get-started)
- Nach der Installation: Überprüfen Sie die Version:
  ```sh
  docker --version
  ```
- Starten Sie Docker Desktop, bevor Sie mit den nächsten Schritten fortfahren.

---

## Schritt 2: Docker-Container herunterladen und starten
Da der Container bereits im GitHub-Repository definiert ist, kann das Docker-Image direkt heruntergeladen und gestartet werden. Verwenden Sie dazu die folgenden Befehle:
- Container herunterladen:
```sh
docker pull ghcr.io/mhmdjld/funk_projekt:latest
```
- Container starten:
```sh
docker run -d -p 8000:8000 --name funk_projekt_container ghcr.io/mhmdjld/funk_projekt:latest
```
---

## Schritt 3: Anwendung im Browser öffnen
Nach dem erfolgreichen Start des Containers können Sie die Anwendung über folgende Adresse im Browser aufrufen:

http://localhost:8000/

---

## Schritt 4: Container verwalten (Container stoppen / Container neu starten:)
Um den Betrieb der Anwendung flexibel zu steuern, können Sie den Docker-Container jederzeit stoppen oder neu starten. Dies ist besonders nützlich, wenn Änderungen vorgenommen wurden oder die Anwendung vorübergehend nicht benötigt wird
- Container Stoppen:
```sh
docker stop funk_projekt_container
```
- Container neu starten:
```sh
docker restart funk_projekt_container
```

---
