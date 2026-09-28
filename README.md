# Noiloi

Sunset-driven lighting for **Yeelight** bulbs and a local **Razer** backlight server. The name is a Londoner pronunciation of “night light”.

Before sunset it turns lamps to a neutral color temperature, then steps warmer over ~2 hours (aligned with a KDE Night Color–style ramp). On overcast days the ramp starts earlier.

Scheduling uses [Cronicle](https://github.com/jhuckaby/Cronicle) one-shot events (no long-running wait processes). Sunset is computed with [astral](https://astral.readthedocs.io/). Cloud cover comes from [Open-Meteo](https://open-meteo.com/) (no API key).

## How it works

1. **`noiloi daily`** (Cronicle, every day at noon) — compute today’s sunset, create a one-shot weather job ~50 minutes before sunset.
2. **`noiloi weather`** — fetch Open-Meteo `cloud_cover` for the sunset hour; if cover ≥ threshold, start 40 minutes early, otherwise 10 minutes; create nine one-shot step jobs (15 minutes apart); delete the weather event.
3. **`noiloi step <kelvin> [hex]`** — set Yeelight CT (and optional Razer color); delete the step event.

```text
noon ──► daily ──► weather@sunset−50m ──► steps@start+N×15m
                      │                      │
                   Open-Meteo            Yeelight + Razer
```

## Requirements

- Python 3.10+
- [Cronicle](https://github.com/jhuckaby/Cronicle) with a Shell Script plugin and an API key (create/edit/delete events)
- Yeelight bulbs reachable on LAN (TCP port `55443`, LAN control enabled)
- Optional: local Razer color server on TCP (default `127.0.0.1:13000`) accepting a hex color string

## Install

```bash
git clone <repo-url> noiloi
cd noiloi
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp noiloi.conf.example noiloi.conf   # or path of your choice
chmod 600 noiloi.conf
# edit: coordinates, timezone, Cronicle URL + API key, yeelight IPs, noiloi_bin

# Point scripts/noiloi at this checkout’s .venv / root, then:
install -m 755 scripts/noiloi /usr/local/bin/noiloi
```

Set `NOILOI_CONF` if the config is not at `/home/cds/bin/noiloi.conf` or `./noiloi.conf`.

Register the permanent noon job:

```bash
noiloi setup-daily
```

Or create a Cronicle Shell event titled `noiloi-daily` that runs daily at `12:00` in your timezone:

```sh
#!/bin/sh
exec /path/to/noiloi daily
```

## Configuration

See [`noiloi.conf.example`](noiloi.conf.example). Important keys:

| Key | Meaning |
|-----|---------|
| `latitude` / `longitude` / `timezone` | Observer for astral + Open-Meteo |
| `cronicle_url` / `cronicle_api_key` | Cronicle REST API |
| `cronicle_category` / `plugin` / `target` | Must match your Cronicle setup |
| `cloud_threshold` | Cloud cover % → overcast (default `70`) |
| `offset_clear_min` / `offset_overcast_min` | Minutes before sunset to start |
| `weather_lead_min` | When to fetch weather (default `50`) |
| `yeelight_ips` | Space-separated bulb IPs |
| `noiloi_bin` | Absolute path Cronicle scripts should `exec` |

Do not commit `noiloi.conf` (API keys). It is gitignored.

## CLI

```bash
noiloi daily          # schedule today’s weather one-shot
noiloi weather        # fetch clouds, schedule color steps, self-delete
noiloi step 4100 a34410   # one CT (+ optional Razer hex)
noiloi setup-daily    # create/replace permanent noon Cronicle event
```

Logs append to the path in `log_file` (default `/home/cds/tmp/noiloi.log`).

## Color ramp

| Step | Kelvin | Razer hex |
|------|--------|-----------|
| 0 | 6500 | `fcc68d` |
| 1 | 6100 | `ffa463` |
| 2 | 5700 | `fa9248` |
| 3 | 5300 | `ff8b38` |
| 4 | 4900 | `fc791c` |
| 5 | 4500 | `b85212` |
| 6 | 4100 | `a34410` |
| 7 | 3700 | `8c320e` |
| 8 | 3300 | — |

## Layout

```text
noiloi/
  config.py      # conf loader + color table
  sun.py         # astral sunset
  weather.py     # Open-Meteo
  cronicle.py    # REST client
  devices.py     # Yeelight + Razer TCP
  cli.py         # entrypoint commands
scripts/noiloi
noiloi.conf.example
requirements.txt
dirtyhack/       # legacy bash/PHP (not used by the new path)
```

## License

Add a license of your choice before publishing; none is set in this tree yet.

## Credits

- [astral](https://github.com/sffjunkie/astral) — solar times  
- [Open-Meteo](https://open-meteo.com/) — cloud cover forecast  
- [Cronicle](https://github.com/jhuckaby/Cronicle) — job scheduling  
