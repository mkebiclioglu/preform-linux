# preform-linux

Run Formlabs **PreFormServer** (the headless PreForm with the
[Local API](https://formlabs.com/support/Formlabs-API-downloads-and-release-notes))
on Linux. Formlabs ships it for macOS and Windows only; this project runs the
Windows build under Wine, headless, with no GPU, as a Docker container or a
plain user-level install. The point is automation: a Linux box, VM or CI runner
that imports models, orients and supports them, estimates print time, writes
`.form` files and sends jobs to printers over plain HTTP.

**Status: working.** The Docker image and a bare Ubuntu 24.04 install both pass
an end-to-end check on every push and every week: import a model, orient,
support, lay out, estimate print time, write the `.form` file, render a
screenshot, probe for printers, all on a GPU-less runner. Printers are reached
by IP address or through a Formlabs account (see *Printers*); mDNS discovery
and USB printers are the two things Wine does not give you.

## Quick start (Docker)

```bash
git clone https://github.com/mkebiclioglu/preform-linux.git
cd preform-linux
mkdir jobs
docker compose up
```

That pulls `ghcr.io/mkebiclioglu/preform-linux:latest` (while this repository
is private the package is too: `docker login ghcr.io` with a token that has
`read:packages` first, or build locally with `docker compose up --build`). The
first start downloads PreFormServer from `downloads.formlabs.com` (about 330 MB),
verifies Formlabs' Authenticode signature, and stores it in the `preform-data`
volume, so later starts are quick. The image itself never contains Formlabs
software. When the log shows `PreFormServer is ready`:

```bash
curl http://127.0.0.1:44388/            # version
cp ~/parts/bracket.stl jobs/
curl -X POST http://127.0.0.1:44388/scene/ -H 'Content-Type: application/json' \
  -d '{"machine_type":"FORM-4-0","material_code":"FLGPBK05","layer_thickness_mm":0.1}'
```

The container runs PreFormServer as an unprivileged user; set `PUID`/`PGID`
(`PUID=$(id -u) PGID=$(id -g) docker compose up`) so the files it writes to
`./jobs` belong to you. Files are passed to the API as PreFormServer sees them: the `./jobs` directory
is mounted at `/jobs` in the container, which Wine exposes as **`Z:/jobs`**.
So `{"file":"Z:/jobs/bracket.stl"}` imports it and `{"file":"Z:/jobs/bracket.form"}`
saves the job back next to it. `examples/smoke.sh` is a complete
import → orient → support → layout → estimate → save → discover run in bash.

Want a self-contained private image with PreFormServer baked in?
`docker build -f docker/Dockerfile --build-arg BUNDLE=1 -t preform-linux:bundled .`
(do not publish it; see *Licensing*).

## Quick start (bare metal)

Needs Wine **11.5 or newer**, Xvfb, curl, unzip and osslsigncode. Distro Wine
will not do: PreFormServer 3.63.0's Qt imports the Windows ICU libraries, which
Wine only gained in 11.5 (March 2026), and Ubuntu 24.04 ships 9.0. Install
[WineHQ devel](https://wiki.winehq.org/Ubuntu) (11.13 or newer runs it as is;
11.5 to 11.12 also need `gcc-mingw-w64-x86-64` so the installer can build a
tiny `dnsapi.dll` shim).

```bash
# Ubuntu 24.04: WineHQ devel + the rest
sudo dpkg --add-architecture i386
sudo mkdir -pm755 /etc/apt/keyrings
sudo curl -fsSL https://dl.winehq.org/wine-builds/winehq.key -o /etc/apt/keyrings/winehq-archive.key
sudo curl -fsSL https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources -o /etc/apt/sources.list.d/winehq-noble.sources
sudo apt update && sudo apt install --install-recommends winehq-devel
sudo apt install xvfb osslsigncode

git clone https://github.com/mkebiclioglu/preform-linux.git ~/preform-linux
~/preform-linux/bin/preform-linux install    # download, verify, install, init the Wine prefix
~/preform-linux/bin/preform-linux run        # foreground; Ctrl-C stops it
```

`preform-linux doctor` explains what is missing. `systemd/preform-server.service`
is a user unit that keeps it running. Paths given to the API are Wine paths:
`/home/me/parts/x.stl` is `Z:/home/me/parts/x.stl`.

## Printers

Three ways to reach a printer from a Linux-hosted PreFormServer, in the order
an automation setup should prefer them:

1. **By IP address.** `POST /scene/{id}/print/` takes `"printer": "10.0.0.21"`
   directly, and `POST /discover-devices/` with `"ip_address"` probes one host.
   Neither needs mDNS. Give the printers fixed addresses or DHCP reservations
   (standard practice on a production network anyway) and list them:

   ```bash
   PREFORM_PRINTERS=10.0.0.21,10.0.0.22 docker compose up
   ```

   The server probes each one as soon as it is up and again every 10 minutes
   (`PREFORM_PRINTERS_INTERVAL`), so `GET /devices/` and the MCP's
   `list_devices` show them with status, tank and cartridge.
   `preform-linux printers 10.0.0.21` (or `docker exec preform preform-linux
   printers 10.0.0.21`) probes on demand and prints the device list. The default
   Docker bridge network is enough: the container connects out to the printer;
   the printer never has to connect back.

2. **Through a Formlabs account.** Set `FORMLABS_USERNAME` and
   `FORMLABS_PASSWORD` (or `FORMLABS_ACCESS_TOKEN`; the `*_FILE` variants read
   Docker/Podman secrets) and the server logs in as soon as it is ready. Fleet
   Control queues and every printer registered to the Dashboard then appear in
   `/devices/` and accept jobs, wherever they are. Nothing on the LAN is needed.
   `preform-linux login` does it on demand. This is HTTPS through Wine; it is
   wired up but has not been exercised in CI (no account there).

3. **mDNS discovery: not under Wine.** PreFormServer discovers LAN printers with
   Windows' `DnsStartMulticastQuery`, which Wine 11.13+ (and the shim for older
   Wine) implements as a stub that never answers. `POST /discover-devices/`
   without an address therefore returns nothing. The query it makes (captured
   with `PREFORM_SHIM_TRACE=1` in CI) is a PTR lookup for
   `_formlabs_formule._tcp.local`, so a real implementation in `shim/dnsapi.c`
   (Winsock multicast to 224.0.0.251:5353, answer with the PTR/SRV/A records,
   plus `--network host` for the container) is a well-defined job; contributions
   are welcome.

**USB printers** are out of reach: PreFormServer drives them through a bundled
Windows `libusb-1.0.dll` and Wine has no USB passthrough. A winelib
`libusb-1.0.dll` that forwards to the host's libusb would close that gap, but a
server-side automation box next to a printer on a USB cable is rarely the
architecture you want; put the printer on the network.

## Using it from formlabs-local-mcp

[formlabs-local-mcp](https://github.com/mkebiclioglu/formlabs-local-mcp) 1.0.6
and newer talk to a Wine-hosted PreFormServer directly, mapping file paths for
you. For the Docker image with `./jobs` mounted at `/jobs`:

```
PREFORM_SERVER_URL=http://127.0.0.1:44388
PREFORM_SERVER_PATH_STYLE=wine
PREFORM_PATH_MAP=/home/me/preform-linux/jobs=Z:/jobs
```

For a bare-metal install only the first two lines are needed (a Linux path
`/home/me/x.stl` becomes `Z:/home/me/x.stl`). Every MCP tool then works as on
macOS: `import_model`, `auto_support`, `save_form`, `discover_devices` with an
`ip_address`, `print_to_printer` with an IP or, after `login`, a Fleet Control
queue.

## How it works

- **Wine, headless.** PreFormServer is a Qt 6 application that needs a display
  even without a window, so `run` starts a private Xvfb. Rendering goes through
  the Mesa software renderer that Formlabs bundles (`opengl32sw.dll`) via
  `QT_OPENGL=software`; no GPU or GLX is required.
- **Wine 11.5+.** Qt6Core in PreFormServer 3.63.0 imports `icuuc.dll`, the ICU
  build Windows 10 ships in System32. Wine added `icu`, `icuuc` and `icuin`
  in 11.5; on anything older the loader stops with `STATUS_DLL_NOT_FOUND`
  before a single line of PreFormServer runs. `install` and `run` refuse older
  Wine with a clear message (`PREFORM_WINE_UNCHECKED=1` overrides, for older
  PreFormServer releases whose Qt did not use ICU).
- **The dnsapi problem.** Right after opening its HTTP port PreFormServer calls
  `DnsStartMulticastQuery` (Windows mDNS) to look for printers. Wine aborts a
  process on the first call to a function it does not export, and no Wine
  release before 11.13 exported this one, so PreFormServer died at
  "starting HTTP server". Wine 11.13 (July 2026, commits `c13fd5de90` and
  `11bca8ddea`) added it as a stub that reports success. For older Wine,
  `shim/dnsapi.c` is a small DLL that does the same (plus the handful of
  dnsapi entry points Qt and Wine's own iphlpapi, ws2_32 and netapi32 expect)
  and is loaded with `WINEDLLOVERRIDES=dnsapi=n`; the installer builds it only
  when needed.
- **After "READY FOR INPUT".** `run` watches PreFormServer's output; once it is
  ready it logs in to Formlabs if an account is configured and probes the
  configured printers, then keeps re-probing on the interval. Passwords are
  sent to the loopback API from a pipe, never on a command line.
- **No debugger hangs.** The Wine prefix disables `winedbg` auto-attach
  (`AeDebug\Auto = 0`), so a crash exits instead of parking the process for a
  debugger that never comes. A server that never reports ready within
  `PREFORM_STARTUP_TIMEOUT` is stopped so a supervisor can restart it.
- **Clean shutdown.** `run` traps SIGTERM/SIGINT, stops PreFormServer, kills the
  wineserver and its Xvfb. The container uses `tini` as PID 1.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PREFORM_LINUX_HOME` | `~/.local/share/preform-linux` (`/data` in Docker) | Install root: PreFormServer, Wine prefix, metadata. |
| `PREFORM_PORT` | `44388` | Port PreFormServer listens on. It binds all interfaces and has no authentication. |
| `PREFORM_VERSION` | `latest` | Pin a PreFormServer release, e.g. `3.63.0`. |
| `PREFORM_PRINTERS` | unset | Printer IPs or hostnames, comma or space separated, probed once the server is up. |
| `PREFORM_PRINTERS_TIMEOUT` | `10` | Seconds to wait for each probed printer. |
| `PREFORM_PRINTERS_INTERVAL` | `600` | Seconds between re-probes; `0` probes once. |
| `FORMLABS_USERNAME`, `FORMLABS_PASSWORD` | unset | Formlabs account; the server logs in once it is up. |
| `FORMLABS_ACCESS_TOKEN` | unset | Token alternative to username/password. |
| `FORMLABS_PASSWORD_FILE`, `FORMLABS_ACCESS_TOKEN_FILE` | unset | Read the secret from a file (Docker secrets). |
| `PREFORM_TELEMETRY` | `0` | `1` lets PreFormServer send telemetry. |
| `PREFORM_INSTALL_UNVERIFIED` | `0` | `1` accepts a download whose signature cannot be checked (osslsigncode missing). |
| `PREFORM_SHIM` | auto | `1` always installs the dnsapi shim, `0` never. Auto: only when Wine < 11.13. |
| `PREFORM_SHIM_DLL` | unset | Prebuilt shim to use instead of compiling (the Docker image sets this). |
| `PREFORM_SHIM_TRACE` | `0` | `1` logs the mDNS queries PreFormServer makes (needs the shim). |
| `PREFORM_WINE_UNCHECKED` | `0` | `1` skips the Wine >= 11.5 check. |
| `PREFORM_STARTUP_TIMEOUT` | `300` | Seconds to wait for `READY FOR INPUT`; PreFormServer is stopped if it never gets there. `0` disables. |
| `PREFORM_XVFB` | auto | `1` always starts Xvfb; `0` uses `$DISPLAY`. Auto: Xvfb when no DISPLAY. |
| `QT_OPENGL` | `software` | Qt renderer. `desktop` uses Wine's OpenGL (needs GLX). |
| `WINEPREFIX`, `WINEDEBUG`, `WINEDLLOVERRIDES` | prefix under home, `-all`, `mscoree=d;mshtml=d` | Passed to Wine. |

Docker build arguments: `WINE_BRANCH` (`devel`), `WINE_VERSION`
(`11.17~noble-1`), `PREFORM_VERSION` (`latest`), `BUNDLE` (`0`). Container
environment: `PUID`/`PGID` (`1000`) own `/data` and `/jobs`; every `PREFORM_*`,
`FORMLABS_*`, `QT_*` and `WINE*` variable is passed through to PreFormServer.
Image tags: `latest` and `X.Y.Z` from releases, `main` from every green build of
the main branch.

## Running it in production

- One container (or unit) per PreFormServer; it is single-tenant and keeps
  scene state in memory. Scale by running more of them on different ports.
- Put a reverse proxy with authentication in front of the port if anything but
  localhost must reach it; the API has none of its own.
- Mount the directory your pipeline writes models to at `/jobs` and speak `Z:/jobs/...`
  to the API. Output `.form` files land in the same place.
- Pin `PREFORM_VERSION` and the image tag; the weekly CI run here tells you
  when a new PreFormServer or Wine release breaks something before you upgrade.
- The health check (`GET /` answering) turns healthy about a minute after
  start, later on the very first start while PreFormServer downloads.

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
- Account credentials are read from the environment or a secrets file, sent to
  the loopback API through a pipe, and never logged.
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
WineHQ devel and runs `examples/smoke.sh` against it (including printer probing
and the `printers` subcommand), repeats the smoke test on a bare Ubuntu 24.04
runner with WineHQ devel and the dnsapi shim forced on with tracing, and
publishes the image to GHCR when everything is green. It runs weekly so new
PreFormServer or Wine releases show up as red rather than as surprises.
See `CHANGELOG.md` for what changed.

## Roadmap

- Real mDNS in the shim (or upstream in Wine) for zero-config LAN discovery.
- A winelib `libusb-1.0.dll` bridge for USB printers, if anyone needs one.
- arm64 hosts (Raspberry Pi, Apple Silicon without Rosetta) via FEX/box64:
  unexplored.
