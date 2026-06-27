# TV Dashboard

Edles Bento-Grid-Dashboard für Wohnzimmer-TVs. Catppuccin Mocha · Glassmorphism · 7 Pages · animierte Wetter-Icons · Live-Plots überall.

## Pages (Auto-Rotate)

**Robert-Profil:** Home · Wetter · Energie-Detail · Räume · Status (Batterien/Thread/Backup) · Internet · Kalender

**Mike-Profil:** Home · Wetter · Solar (PV-Flow + Akku + Wallbox) · Pool (Wassertemp/pH/ORP + Pumpe + Aktion-Log) · Status · Internet · Kalender

## Setup

1. In Settings → Add-ons → Add-on Store → ⋮ → Repositories: `https://github.com/robeertm/hass-addons`
2. „TV Dashboard" installieren
3. **Configuration** → `profile: mike` (oder `robert`)
4. Start. Auf TV-Browser `http://<HA-Host>:8765` aufrufen.

## Options

| Option | Default | Beschreibung |
|---|---|---|
| `profile` | `mike` | `robert`, `mike` oder `custom` |
| `refresh_seconds` | 15 | HA-Polling-Intervall |
| `page_rotate_seconds` | 22 | Page-Carousel-Geschwindigkeit |

## Entity-Mapping

Die Profile in `app/profiles/` enthalten alle Entity-IDs pro Haushalt — wenn deine IDs abweichen, anpassen + neu builden.

