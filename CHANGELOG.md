# Changelog

## 0.3.0 (2026-09-18)

- **Simulated printer.** `sim/printer-sim.py` is a fake Formlabs printer on TCP port
  35 that PreFormServer discovers by IP, lists as a connected Form 4 / Fuse 1+ /
  Fuse X1 with tank and cartridge, and prints to: calibration, job metadata, the
  job file and every layer arrive at the simulator. `docker compose --profile sim
  up` runs it as the `printer-sim` sidecar. The CI discovers it and prints to it on
  every run, on the Docker image and on bare metal.
- The reply schemas were read from PreFormServer's binary (`research/README.md`):
  envelope `Id/ReplyToMethod/Version/Success/Parameters/Error`, `GetInformation_v1`,
  the `GetStatus` family, and the print sequence `GET_CALIBRATION`, `START_JOB`,
  `UPLOAD_FILE`, `UPLOAD_LAYER`.
- **Fuse X1.** Documented what PreFormServer 3.63.0 can do for it (job prep with
  `FUSX-1-0` / `FLP12G01` / 0.11 mm, estimate, `.form`, network print) and what it
  cannot (not in `list-materials`, no other settings, no 3D packing, virtual
  printer refuses jobs). `examples/smoke.sh` prints to the simulator when
  `SMOKE_SIM_PRINTER` names it.

## 0.2.1 (2026-09-18)

- The repository and the GHCR image are public.
- The smoke test (and so CI) sends the prepared job to PreFormServer's built-in
  virtual Form 4 and checks for a `job_id`: the print path is exercised on every run.
- CI probes 198.51.100.1 instead of 192.0.2.1: PreFormServer parks its virtual
  printers on 192.0.2.x, so the old address was a virtual Form 3B.
- `research/`: what a directed printer probe looks like on the wire (TCP port 35,
  length-prefixed JSON, `PROTOCOL_METHOD_GET_INFORMATION`), the protocol vocabulary
  from the binary, a fake printer to experiment with, and the workflow that runs it.
  Verified that the probe goes out under Wine with and without the shim.
- README: printers by IP, virtual printers as a dry run, Fuse X1 status.

## 0.2.0 (2026-09-18)

Automation-ready release.

- **Printers by address.** `PREFORM_PRINTERS=10.0.0.21,10.0.0.22` makes the server
  probe those printers as soon as it is up (the Local API's directed
  `discover-devices`, no mDNS involved) and again every `PREFORM_PRINTERS_INTERVAL`
  seconds, so `GET /devices/` and the MCP's `list_devices` stay populated.
  `preform-linux printers [ip ...]` does the same on demand and prints the device list.
- **Formlabs account.** `FORMLABS_USERNAME`/`FORMLABS_PASSWORD` or
  `FORMLABS_ACCESS_TOKEN` (or `*_FILE` variants for Docker secrets) log the server in
  once it is ready, which unlocks Fleet Control queues and Dashboard printers.
  `preform-linux login` does it on demand.
- **Prebuilt image** on GHCR: `ghcr.io/mkebiclioglu/preform-linux` (`:latest`,
  `:0.2.0`, `:main`). It still contains no Formlabs software.
- **Shim tracing.** `PREFORM_SHIM_TRACE=1` logs the mDNS queries PreFormServer
  makes, the groundwork for a real mDNS implementation.
- Container: every `PREFORM_*`, `FORMLABS_*`, `QT_*` and `WINE*` variable now
  crosses the privilege drop; `libgnutls30t64` added for Wine's TLS (account login).
- `doctor` reports printers, account and, when the server is up, known devices.
- The smoke test now exercises broadcast and directed discovery.

## 0.1.0 (2026-09-17)

First working version: PreFormServer 3.63.0 under Wine 11.17, headless, in Docker
and on bare metal, with the dnsapi shim for Wine 11.5 to 11.12.
