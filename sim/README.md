# Simulated printer

`printer-sim.py` is a fake Formlabs printer. PreFormServer discovers it by IP,
lists it as a connected Ethernet printer with a tank and cartridge, and prints to
it: calibration request, job metadata, the job file and every layer arrive at the
simulator, which logs them and answers "ok". Nothing is printed; the point is to
test a pipeline's discovery and print path without hardware, on any machine.

```bash
# bind a spare address (port 35 needs root or CAP_NET_BIND_SERVICE) and start a Form 4
sudo ip addr add 198.51.100.21/32 dev lo
sudo python3 sim/printer-sim.py --bind 198.51.100.21 --serial SimForm4 --machine FORM-4-0

# make PreFormServer probe it (or list it in PREFORM_PRINTERS)
preform-linux printers 198.51.100.21          # -> printer at 198.51.100.21: Form 4 (...)
curl -s http://127.0.0.1:44388/devices/       # id SimForm4, connection_type ETHERNET

# then print to it: "printer": "SimForm4" (or the IP) in POST /scene/{id}/print/
```

With Docker Compose the simulator is a sidecar: `docker compose --profile sim up`
starts it as `printer-sim` on the compose network and the PreFormServer container
probes it at start (`PREFORM_PRINTERS=printer-sim`).

Identities: `--machine FORM-4-0 --product "Form 4"` (default), `--machine FS30-1-0
--product "Fuse 1+" --material FLP12B01`, `--machine FUSX-1-0 --product "Fuse X1"
--material FLP12G01`, or any machine type PreFormServer knows. `--serial` is the
device id PreFormServer will use, `--alias` the display name. SLA identities take
jobs; SLS ones are discovered and monitored but PreFormServer 3.63.0 refuses to
send them a job ("incompatible firmware version"), the same answer its own virtual
SLS printers get.

## What it speaks

The printer protocol ("Formule", `_formlabs_formule._tcp`) on TCP port 35, as
PreFormServer 3.63.0 uses it. Frames are a little-endian `uint32` JSON length, the
JSON, then a little-endian `uint64` attachment length and the attachment (layers
and files are attachments). Requests carry `Id`, `Method`, `Version` and optional
`Parameters`; replies carry `Id`, `ReplyToMethod`, `Version`, `Success`,
`Parameters` and optionally `Error`. Every reply schema in the script was read from
the packet parsers in the PreFormServer binary (`research/README.md` says how);
the parser is strict about types and silently drops a reply with a wrongly typed
known key, which is why the earlier guesswork never matched.

Methods PreFormServer sends: `GET_INFORMATION` (identity, compatibility, capabilities),
`GET_STATUS` (tank, cartridges, readiness), `GET_CALIBRATION`, then for a print
`START_JOB` (metadata), `UPLOAD_FILE` (`misc.flfc`), `UPLOAD_LAYER` (chunks of
layers) and `HEARTBEAT`. The simulator accepts them all. It does not implement
`SECURE_HANDSHAKE` (PreFormServer 3.63.0 does not ask for it), firmware update,
formlogs, snapshots or idle routines; those answer `PROTOCOL_ERROR_NO_HANDLER`.

Not affiliated with or endorsed by Formlabs; the protocol is theirs and undocumented,
and what is here was learned by talking to their software. Do not point real
printers' traffic at it.
