# Robert Manuwald — Home Assistant Add-ons

Home Assistant Add-on repository.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Frobeertm%2Fhass-addons)

## Installation

**One-click**: use the button above (works on HA Cloud, HAOS, supervised HA).

**Manually**: In Home Assistant go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories**, then add:

```
https://github.com/robeertm/hass-addons
```

After a moment the add-ons in this repository will appear in the store.

## Available add-ons

### [Shelly Energy Analyzer](./shelly_energy_analyzer)

Self-hosted energy monitoring, cost tracking and smart automation for Shelly EM / 3EM. Includes 23 dashboards, dynamic spot tariffs, real ENTSO-E CO₂ intensity, PV/solar, NILM appliance detection, MQTT/Home Assistant auto-discovery, InfluxDB/Prometheus export, iOS widget.

Upstream: [robeertm/shelly-energy-analyzer](https://github.com/robeertm/shelly-energy-analyzer)
