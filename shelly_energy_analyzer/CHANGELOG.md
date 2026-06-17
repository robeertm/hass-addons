# Changelog

## 16.41.4-1 — 2026-06-17

- **Fix**: upstream `pyproject.toml` ships only `.py` files, so `pip install` was leaving HTML templates, static CSS/JS and i18n JSON files out of the installed package. Result: `/setup` returned `Setup wizard not available`, and several routes (`/settings`, `/widget_page`) would have failed similarly. The Dockerfile now clones the upstream source and overlays the resource files onto the installed package directory after `pip install`. Build adds a smoke-test that fails the build if `setup.html` isn't reachable from the installed module path.

## 16.41.4 — 2026-06-17

- Initial add-on release. Wraps upstream [shelly-energy-analyzer v16.41.4](https://github.com/robeertm/shelly-energy-analyzer/releases/tag/v16.41.4).
- Supports `aarch64`, `amd64`, `armv7`, `armhf`.
- MQTT auto-discovery integrates with the HA Mosquitto add-on (auto-pulls credentials from HA service registry when add-on options leave `username`/`password` empty).
- Persistent state under `/data`.
