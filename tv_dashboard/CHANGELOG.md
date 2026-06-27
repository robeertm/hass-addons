## 1.0.4 (2026-06-27)

- Page-Rotation Default 10s → 3s (Robert-Wunsch: lebhaftere Rotation)
- Schema-Min: `page_rotate_seconds` von 8 auf 2 gelockert

## 1.0.3 (2026-06-27)

- Mike-Profil: Wetterstation-Entities erweitert (Wind, Regen, Luftdruck, Außen-Luftfeuchte, Indoor-CO₂/Lärm)
- Mike-Profil: Außentemp-Historie auf Netatmo Outdoor-Modul gefixt (war auf nicht existierender `sensor.aussentemperatur`)
- Mike-Profil: 13 Batterien aus realem Inventar (Netatmo Outdoor/Regen/Wind, Roborock, 3 Rauchmelder, Wasserwarner, Treppe Motion, …)
- Wetter-Page: Wind / Regen / Luftdruck / Außen-Luftfeuchte Mini-Tiles statt leerem Whitespace
- Status-Page: für Mike Wetterstation-Tile (Wind/Regen/CO₂/Lärm) statt nicht existierender Thread-Mesh-RSSI
- Data-driven Tile-Hide: `tile-needs-data` blendet leere Kacheln aus (Urlaub, Thread, leere Wetter-Sensoren)
- Page-Rotation Default 22s → 10s ("lebender" wirken)
- Outdoor-Temperatur Hover-History liest jetzt korrekt das jeweils profil-konfigurierte Outdoor-Entity

## 1.0.0 (2026-06-27)

Initial release.

- 7 Pages mit Catppuccin Mocha, Glassmorphism, responsive clamp()
- Profile-System für Robert + Mike
- Robert-Profil: Wohnzimmer-Setup mit 7 TRVs, 7 Fenstern, Strom-Detail, Räume mit Mini-Sparklines
- Mike-Profil: EMMA-Solar-Flow, Pool-Suite, 4 Personen, ZAOE-Garbage-Auto-Discovery aus Kalender
- Live-Plots: Außentemp 24h, Strom 24h, PV 24h, 4 Sub-Counter, 7 Per-Room, Pool pH/ORP/Temp, Internet Down/Up
- TRV-Status pro Raum mit Heizt-Badge + Soll + Ventilstellung
- 19-Sensor-Batterie-Grid mit Farb-Level
- Thread-Mesh-RSSI mit Bar-Visualisierung
- Internet-Page mit Top-Clients + Friendly-Name-Mapping
