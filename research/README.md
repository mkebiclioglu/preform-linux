# Printer protocol notes

How `sim/printer-sim.py` came to speak PreFormServer's printer protocol, kept so
the next person can extend it (firmware update, formlogs, secure handshake) or
re-derive it for a new PreFormServer release. Nothing here is Formlabs
documentation; it was learned by watching PreFormServer 3.63.0 talk and by reading
the strings and string references in its binary.

## Transport and framing (captured)

- Directed discovery (`POST /discover-devices/ {"ip_address": ...}`) opens plain
  TCP to the address on **port 35** (Formlabs' documented printer port), retrying
  every 15 s until the timeout. Works under Wine with or without the dnsapi shim.
  No DNS, no TLS.
- Frame: little-endian `uint32` JSON length, the JSON, little-endian `uint64`
  attachment length, the attachment. Requests: `{"Id": "{guid}", "Method":
  "PROTOCOL_METHOD_...", "Version": 1, "Parameters": {...}?}`.

## Reply envelope and packet schemas (read from the binary)

`FormulePacketMetadata.cpp`: `Id` string, `ReplyToMethod` string, `Version` number,
`Success` bool, `Parameters` object, `Error` string (optional). A known key with the
wrong JSON type fails the whole packet silently (PreFormServer just closes and
retries), which is why replies that merely guessed key names never worked.

`GetInformation_v1.cpp` Parameters: `connectionInterface` string
(`PROTOCOL_INTERFACE_ETHERNET|WIFI|USB|NO_INTERFACE`), `version` object (the
compatibility descriptor; `CompatibilityCheckerImpl.cpp` wants `PF_printing` and/or
`PF_updating` objects, and accepts an empty object), `printerID` string, `printer`
object `{Serial, DeviceAlias, MachineTypeId, FactoryMACAddress?}`, `ipAddresses`
array, `capabilities` array.

`GetStatus.cpp` (shared) and the per-family `GetStatus_v*.cpp` files: see the
`status()` function in the simulator, which sends the union with the right types.
Enum values: `READY_TO_PRINT_{READY,NOT_READY,NEEDS_CONFIRMATION,NOT_SUPPORTED}`,
`BUILD_PLATFORM_CONTENTS_{CONFIRMED_CLEAR,CONFIRMED_DIRTY,MISSING,POST_PRINT,
UNCONFIRMED,NOT_SUPPORTED}`, `USER_STATE_{IDLE,PRINTING,...}`,
`PUMP_STATE_{NOT_PRESENT,PRESENT,...}`, `CAMERA_STATE_{DISABLED,ENABLED,...}`,
`FORMCELL_{UNKNOWN,IDLE,...}`.

What PreFormServer sends when printing, in order: `GET_CALIBRATION`
(`{layerThickness_mm, materialCode}`), `START_JOB` (~50 metadata fields:
`Guid`, `Name`, `MaterialCode`, `LayerCount`, `TotalPrintTimeEstimated_ms`,
`AllowedMachineTypeIds`, `PrintSettings*`, `PreFormVersionNumber`, an
`AllKnobsX` blob, ...), `UPLOAD_FILE` (`FileName` `misc.flfc`, attachment ~100 KB),
then `UPLOAD_LAYER` with `Layer`, `BinaryLayerStartOffsets` and `FileExtensions`
(`.flfc`) and the layers as the attachment, and `HEARTBEAT`.

Other packets in the binary: `SecureHandshake_v1` (`DataBase64`, `NonceBase64`,
`Length`, `Guid`), `ResumeJob_v1`, `AbortJob_v1`, `Update`, `GenerateFormlogs`/
`GetFormlogsChunk`/`DeleteFormlogs`, `GetSnapshot`, `StartIdleRoutine`/
`AbortIdleRoutine`, `GetScaleCorrection`, `LocalForward`,
`RegisterUserToDashboard`.

## What still blocks SLS jobs to a simulated printer

With family-specific status packets a simulated Fuse 1, Fuse 1+ or Fuse X1 is
discovered, shows material, cylinder, powder credit and "Primed", and gets
`GET_STATUS` polled (v1 for Fuse 1/1+, v3 for Fuse X1). A print request still ends
in `Cannot print, the printer might have an incompatible firmware version` before
any upload starts, the same answer PreFormServer gives its own virtual SLS printers.
Ruled out: the compatibility descriptor (`PF_printing` widened to every version),
`firmware_version` (2.5.0 and 9.9.9 both show in the device record), the layer and
formule compatibility numbers, `machine_capabilities` on scene creation (the API
rejects the field), and capability strings or category/revision objects in the
information reply. The check lives next to `Incorrect MachineCapabilities for: %1`
and `Machine firmware doesn't support the following capabilities: %1`
(`Form4PrinterCapabilities.cpp`, "Invalid category revisions for machine type"):
PreForm matches the printer's reported capability categories and revisions against
the job's, and the category names are not string literals in the binary. A capture
from a real Fuse (`tcpdump port 35` while PreForm probes it) would give them in one
shot. 

Update, from disassembly of PreFormServer 3.63.0: the SLS printer's usable
capabilities are not taken from the `capabilities` array a printer reports at all.
`StricklandPrinterBase::_processGetInformationReply` reads only `version` (the
`build`/`name` compatibility object) and, in a helper that takes the firmware
version string, derives the capability set by comparing the parsed version against
thresholds the process loads at runtime (the check at `+0x1b0`, backed by
`PrinterCapabilities` built in `sub_141ad3880`). The job's required capabilities are
then matched against that derived set (`Form4PrinterCapabilities.cpp`,
`Incorrect MachineCapabilities for: %1`). So a print to a simulated SLS printer is
gated on the printer reporting a real Formlabs firmware **version** that maps to the
capabilities the Fuse job needs, not on any field the simulator can simply assert.
That mapping is keyed to genuine firmware build numbers and is not a string literal
in the binary, which is why fourteen rounds of synthetic identities never satisfied
it. This is a firmware-authenticity gate, not a missing field; a capture of one real
Fuse's `GET_INFORMATION` reply remains the way to get a value that passes, and it may
not be worth chasing since no real automation setup prints to a fake SLS machine.

## How the schemas were read

`strings` gives the vocabulary but MSVC pools string literals by suffix, so
neighbours in the dump mean nothing. The useful trick: scan `.text` for
RIP-relative `lea` instructions, map each to the string it points at, and group by
code address. The parser helper pattern `<key> "is not " is<Type> "was"` then yields
every key and its expected type, and the `X:\src\PreForm\vendor\FormuleProtocol\...`
assertion paths label which packet each group belongs to. The scripts are small
(~80 lines of Python each, no dependencies) and live in this directory's history;
`.github/workflows/research-printer-probe.yml` is the harness that ran the rounds.

## Fuse X1 in PreFormServer 3.63.0

Same method, other question. The binary carries `FUSX-1-0` and exactly one Fuse X1
print setting (`FLP12G01_110_FUSX-1_00.fps`: Nylon 12 GF at 0.11 mm), inside the
Strickland (Fuse 1+ 30W) plugin. `POST /scene/` with that triple works and yields a
330 x 330 x 565 mm build volume; `list-materials` does not mention the family;
every other material or layer thickness answers `Scene type not supported` (the
server's message for "no print setting for that combination", also given for
made-up machine types); `auto-pack` answers `3D Packing is not supported for the
given machine type: FUSX-1-0`; the virtual Fuse X1 (like every virtual SLS
printer) answers `Cannot print, the printer might have an incompatible firmware
version`. `FUSL-2-0` behaves like `FUSX-1-0` (a `PP_ENABLE_FUSE_2L` build flag
exists in the source paths).
