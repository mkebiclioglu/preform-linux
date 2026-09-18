# Printer protocol research

What PreFormServer says to a printer over the network, learned by pointing it at
fake printers in CI (`.github/workflows/research-printer-probe.yml`, run by hand).
The goal is a simulated printer that PreFormServer discovers and prints to, so the
network print path can be tested without hardware. That goal is **not reached yet**;
this is what is known.

## Verified

- **Transport.** A directed `POST /discover-devices/ {"ip_address": ...}` opens a
  plain TCP connection to the address on **port 35** (Formlabs' documented printer
  port) and retries every 15 s until the timeout. This works under Wine with the
  dnsapi shim and with Wine's own dnsapi alike, so printers by IP are not blocked
  by the mDNS gap. Nothing is sent to DNS ports; nothing uses TLS.
- **Framing.** Little-endian `uint32` length, that many bytes of JSON, then a
  little-endian `uint64` (0 in every probe; presumably the length of a binary
  attachment that follows, which is how layers and files would be uploaded).
- **The probe.** Pretty-printed JSON, one request per connection:

  ```json
  {"Id": "{guid}", "Method": "PROTOCOL_METHOD_GET_INFORMATION", "Version": 1}
  ```

- **Vocabulary** (strings in `PreFormServer.exe` 3.63.0). Methods:
  `GET_INFORMATION`, `GET_STATUS`, `SECURE_HANDSHAKE`, `HEARTBEAT`, `START_JOB`,
  `START_FORM`, `UPLOAD_FILE`, `UPLOAD_LAYER`, `RESUME_JOB`, `ABORT_JOB`,
  `GET_CALIBRATION`, `GET_SCALE_CORRECTION`, `GET_SNAPSHOT`, `UPDATE`,
  `START_IDLE_ROUTINE`, `ABORT_IDLE_ROUTINE`, `GENERATE_FORMLOGS`,
  `GET_FORMLOGS_CHUNK`, `DELETE_FORMLOGS`, `REGISTER_USER_TO_DASHBOARD`,
  `LOCAL_FORWARD` (all `PROTOCOL_METHOD_*`). Fields: `PROTOCOL_FIELD_ID`,
  `_METHOD`, `_VERSION`, `_SUCCESS`, `_ERROR`, `_REPLY_TO_METHOD`; the literal
  strings `Success`, `Error`, `ReplyToMethod`, `Signature`, `ProductName`,
  `MachineTypeId` exist; error codes `PROTOCOL_ERROR_*` and `PROTOCOL_SUCCESS`;
  interfaces `PROTOCOL_INTERFACE_{ETHERNET,WIFI,USB,NO_INTERFACE}`. Response
  structs: `GetStatusResponse_v1/_v2`, `SecureHandshake_v1`,
  `StartJobMetadata_v1/_v2`, `UploadFileMetadata_v1`, `UploadLayerMetadata_v1/_v2`
  (namespace `FormuleProtocol`; the mDNS service is `_formlabs_formule._tcp`).
  PreForm's own compatibility descriptor is
  `{"PF_printing": {"formule": {"compatible": [4]}, "flx": {"compatible": 6}, ...}}`.
- **Machine type ids in the binary** beyond what `list-materials` exposes:
  `FUSX-1-0` (Fuse X1), `FUSL-2-0`, `SIFT-1-x`, `CLRK-1-x`, `CURL-1-x`,
  `CHEW-1-0`, `WSHL-1-0`, `CELL-0-0`. PreFormServer 3.63.0 answers
  `Scene type not supported` for a `FUSX-1-0` scene: Fuse X1 job preparation is
  not in this Local API release, only the virtual device entry.

## Not yet known

The shape of an acceptable `GET_INFORMATION` reply. Sixteen shapes were tried
(`printer-sim.py --variant N`): payload flat or nested under `Result`, `Response`,
`Data`, `Payload`, `Information`, `Parameters`; with `Method` or `ReplyToMethod`;
with `Success`/`Error` as booleans, empty, or `PROTOCOL_SUCCESS`; `Version` 1 or 4;
with, without, or with a relocated trailer; and a superset of every plausible key
spelling for serial, product, machine type, firmware, status and capabilities.
PreFormServer closes the connection right after each reply, logs nothing, retries,
and reports `Couldn't find printer, timeout occurred`. The next step would be a
capture of a real printer's reply (one `tcpdump port 35` on a network with a
printer, while PreForm probes it) rather than more guessing.

## What works without any of this

PreFormServer ships a built-in **virtual printer per model** (`GET /devices/`,
`connection_type: VIRTUAL`, ids `Form 4`, `Form 3L`, `Fuse 1+`, `Fuse X1`, ...,
parked on 192.0.2.x). `POST /scene/{id}/print/ {"printer": "Form 4"}` runs the
whole job generation and upload path and returns a `job_id`; `examples/smoke.sh`
and the CI do this on every run. The virtual SLS printers reject jobs
(`Cannot print, the printer might have an incompatible firmware version`), so the
dry run is SLA only.

```bash
python3 research/printer-sim.py --bind 198.51.100.21 --variant 2   # needs port 35: root or CAP_NET_BIND_SERVICE
PREFORM_PRINTERS_TIMEOUT=8 preform-linux printers 198.51.100.21     # logs the probe it received
```
