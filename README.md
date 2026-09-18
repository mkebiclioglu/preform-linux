# preform-linux

Run Formlabs **PreFormServer** (the headless PreForm with the
[Local API](https://formlabs.com/support/Formlabs-API-downloads-and-release-notes))
on Linux. Formlabs ships it for macOS and Windows only; this project runs the
Windows build under Wine, headless, with no GPU, as a Docker container or a
plain user-level install. The point is automation: a Linux box, VM or CI runner
that imports models, orients and supports them, estimates print time and writes
`.form` files over plain HTTP.

**Status: experimental.** Everything the Local API does through PreFormServer's
own code (import, orient, support, layout, packing, validation, estimates,
`.form` export) is exercised weekly in CI. mDNS printer discovery does not work
under Wine (details below). USB printers are out of reach.

## Quick start (Docker)

```bash
git clone https://github.com/mkebiclioglu/preform-linux.git
cd preform-linux
mkdir jobs
docker compose up --build
```

The first start downloads PreFormServer from `downloads.formlabs.com` (about
330 MB), verifies Formlabs' Authenticode signature, and stores it in the
`preform-data` volume, so later starts are quick. The image itself never
contains Formlabs software. When the log shows `READY FOR INPUT`:

```bash
curl http://127.0.0.1:44388/            # version
cp ~/parts/bracket.stl jobs/
curl -X POST http://127.0.0.1:44388/scene/ -H 'Content-Type: application/json' \
  -d '{"machine_type":"FORM-4-0","material_code":"FLGPBK05","layer_thickness_mm":0.1}'
```

Files are passed to the API as PreFormServer sees them: the `./jobs` directory
is mounted at `/jobs` in the container, which Wine exposes as **`Z:/jobs`**.
So `{"file":"Z:/jobs/bracket.stl"}` imports it and `{"file":"Z:/jobs/bracket.form"}`
saves the job back next to it. `examples/smoke.sh` is a complete
import → orient → support → layout → estimate → save run in 100 lines of bash.

Want a self-contained private image with PreFormServer baked in?
`docker build -f docker/Dockerfile --build-arg BUNDLE=1 -t preform-linux:bundled .`
(do not publish it; see *Licensing*).

## Quick start (bare metal)

Needs Wine, Xvfb, curl, unzip and osslsigncode. Wine **11.13 or newer** runs
PreFormServer as is; anything older (Ubuntu 24.04 ships 9.0, WineHQ stable is
11.0) also needs `gcc-mingw-w64-x86-64` so the installer can build a tiny
`dnsapi.dll` shim.

```bash
# Ubuntu 24.04 with distro Wine 9.0 (shim path)
sudo apt install wine wine64 xvfb osslsigncode gcc-mingw-w64-x86-64 mingw-w64-x86-64-dev make
# or WineHQ devel >= 11.13 (no shim): https://wiki.winehq.org/Ubuntu

git clone https://github.com/mkebiclioglu/preform-linux.git ~/preform-linux
~/preform-linux/bin/preform-linux install    # download, verify, install, init the Wine prefix
~/preform-linux/bin/preform-linux run        # foreground; Ctrl-C stops it
```

`preform-linux doctor` explains what is missing. `systemd/preform-server.service`
is a user unit that keeps it running. Paths given to the API are Wine paths:
`/home/me/parts/x.stl` is `Z:/home/me/parts/x.stl`.

## Using it from formlabs-local-mcp

[formlabs-local-mcp](https://github.com/mkebiclioglu/formlabs-local-mcp) can
connect to a PreFormServer it did not start:

```
PREFORM_SERVER_URL=http://127.0.0.1:44388
```

Today the MCP server passes Linux paths straight through, so with a Wine-hosted
PreFormServer file tools need the `Z:` form. Teaching the MCP server to map
paths when it talks to preform-linux is the obvious next step.

## How it works

- **Wine, headless.** PreFormServer is a Qt 6 application that needs a display
  even without a window, so `run` starts a private Xvfb. Rendering goes through
  the Mesa software renderer that Formlabs bundles (`opengl32sw.dll`) via
  `QT_OPENGL=software`; no GPU or GLX is required.
- **The dnsapi problem.** Right after opening its HTTP port PreFormServer calls
  `DnsStartMulticastQuery` (Windows mDNS) to look for printers. Wine aborts a
  process on the first call to a function it does not export, and no Wine
  release before 11.13 exported this one, so PreFormServer died at
  "starting HTTP server". Wine 11.13 (July 2026, commits `c13fd5de90` and
  `11bca8ddea`) added it as a stub that reports success. For older Wine,
  `shim/dnsapi.c` is a 60-line DLL that does the same and is loaded with
  `WINEDLLOVERRIDES=dnsapi=n`; the installer builds it only when needed.
  Either way no mDNS answers ever arrive, so LAN printers are not discovered.
  Printing through a Formlabs account (Dashboard / Fleet Control) is plain
  HTTPS and should be unaffected, but is untested here.
- **No debugger hangs.** The Wine prefix disables `winedbg` auto-attach
  (`AeDebug\Auto = 0`), so a crash exits instead of parking the process for a
  debugger that never comes.
- **Clean shutdown.** `run` traps SIGTERM/SIGINT, stops PreFormServer, kills the
  wineserver and its Xvfb. The container uses `tini` as PID 1.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PREFORM_LINUX_HOME` | `~/.local/share/preform-linux` (`/data` in Docker) | Install root: PreFormServer, Wine prefix, metadata. |
| `PREFORM_PORT` | `44388` | Port PreFormServer listens on. It binds all interfaces and has no authentication. |
| `PREFORM_VERSION` | `latest` | Pin a PreFormServer release, e.g. `3.63.0`. |
| `PREFORM_TELEMETRY` | `0` | `1` lets PreFormServer send telemetry. |
| `PREFORM_INSTALL_UNVERIFIED` | `0` | `1` accepts a download whose signature cannot be checked (osslsigncode missing). |
| `PREFORM_SHIM` | auto | `1` always installs the dnsapi shim, `0` never. Auto: only when Wine < 11.13. |
| `PREFORM_SHIM_DLL` | unset | Prebuilt shim to use instead of compiling (the Docker image sets this). |
| `PREFORM_XVFB` | auto | `1` always starts Xvfb; `0` uses `$DISPLAY`. Auto: Xvfb when no DISPLAY. |
| `QT_OPENGL` | `software` | Qt renderer. `desktop` uses Wine's OpenGL (needs GLX). |
| `WINEPREFIX`, `WINEDEBUG`, `WINEDLLOVERRIDES` | prefix under home, `-all`, `mscoree=d;mshtml=d` | Passed to Wine. |

Docker build arguments: `WINE_BRANCH` (`devel`), `WINE_VERSION`
(`11.17~noble-1`), `PREFORM_VERSION` (`latest`), `BUNDLE` (`0`).

## Security

- Downloads only from `https://downloads.formlabs.com/PreFormServer/Release/…`,
  with the zip scanned for path traversal before extraction, and
  `PreFormServer.exe` verified with `osslsigncode` against the pinned Microsoft
  Identity Verification root (`certs/`) requiring a Formlabs Inc. leaf. A failed
  check leaves the previous install untouched.
- PreFormServer is an unauthenticated HTTP server that reads and writes files
  as the user running it. Publish the port on loopback only
  (`127.0.0.1:44388:44388`, as `docker-compose.yml` does) or firewall it. In the
  container it runs as an unprivileged user and only `/data` and `/jobs` are
  writable and persistent.
- Telemetry is off unless you turn it on.

## Licensing

This repository is MIT. It ships no Formlabs code: PreFormServer is fetched from
Formlabs at install time and is covered by the
[Formlabs API License Agreement](https://formlabs.com/legal/formlabs-api-license-agreement/)
and the PreForm terms; running it under Wine is your call under those terms. Do
not publish an image built with `BUNDLE=1`. Not affiliated with or endorsed by
Formlabs Inc.

## Development

```bash
shellcheck -S warning -x bin/preform-linux docker/*.sh examples/smoke.sh
make -C shim check                  # needs gcc-mingw-w64-x86-64
docker build -f docker/Dockerfile -t preform-linux:dev .
```

CI (`.github/workflows/ci.yml`) lints, builds the shim, builds the image with
WineHQ devel and runs `examples/smoke.sh` against it, and repeats the smoke test
on a bare Ubuntu 24.04 runner with distro Wine 9.0 plus the shim. It runs weekly
so new PreFormServer or Wine releases show up as red rather than as surprises.

## Roadmap

- Path mapping in formlabs-local-mcp so Linux users get the full MCP experience
  against this server.
- A prebuilt image on GHCR (without Formlabs software) once the CI has a few
  green weeks.
- arm64 hosts (Raspberry Pi, Apple Silicon without Rosetta) via FEX/box64:
  unexplored.
- Real mDNS in the shim if there is demand for LAN printer discovery.
