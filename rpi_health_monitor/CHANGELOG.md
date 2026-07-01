# Changelog

## 1.0.3 — 2026-07-01
- **NVMe SMART support**: when the configured `disk.block_device` starts with `nvme`,
  the add-on now runs `nvme smart-log --output-format=json` and reports **real
  chip-reported endurance** instead of estimated TBW ratios. New sensors: Lifetime
  Written/Read (TB), Available Spare (%), Media Errors, Critical Warning bits,
  Unsafe Shutdowns, Power-Cycles, Power-On Hours, Composite Temperature, Model.
- Storage sensor friendly names switched to device-neutral wording ("Storage Write"
  instead of "SD Write") so they read correctly on NVMe/SSD/eMMC hosts.
- Sensor keys (`sd_*`) kept for backward compatibility — existing Lovelace
  references keep working; new NVMe sensors use `nvme_*` prefix.
- `nvme-cli` added to the Alpine image (~2 MB). Also usable by future USB-SSD
  migrations (SanDisk Extreme Portable, USB-NVMe adapters).
- Two independent years-left estimates (TBW-linear + Percentage-Used trajectory);
  the more conservative wins. Fixes the "0.0 years" glitch on newly-flashed NVMe.

## 1.0.2 — 2026-07-01
- Optional idempotent HA `configuration.yaml` patcher (`config_patcher.enabled: true`).
  Sets `recorder.commit_interval` to a target value (default 60) to reduce SQLite
  WAL write amplification on SD cards. Creates a timestamped backup before writing.
  Safe to re-run — no-ops when target value is already present. Requires
  `homeassistant_config:rw` map (added).
- HA restart required after first apply to activate new recorder config.

## 1.0.1 — 2026-06-30
- Drop `raspberrypi-utils` from Dockerfile (not available on Alpine aarch64). Pi-specific health (throttling, voltage) reads `/sys` directly with graceful fallback when vcgencmd is absent.

## 1.0.0 — 2026-06-30
- Initial release
- 38 sensors + 6 binary_sensors
- CPU/Memory/Disk/SD-IO/Network/Voltage/Throttling/Health-Score
- Daily SD-write tracking + endurance estimation
- vcgencmd integration (Pi-specific)
- Falls back gracefully on non-Pi hardware
