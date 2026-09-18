#!/usr/bin/env python3
"""A fake Formlabs printer on TCP port 35, for testing PreFormServer without hardware.

Wire format (captured from PreFormServer 3.63.0): little-endian uint32 length, that
many bytes of JSON, then a little-endian uint64 attachment length (0 for control
messages) followed by the attachment. Requests look like
    {"Id": "{guid}", "Method": "PROTOCOL_METHOD_GET_INFORMATION", "Version": 1}
and replies are parsed (FormulePacketMetadata.cpp in the binary) as
    {"Id": str, "ReplyToMethod": str, "Version": number, "Success": bool,
     "Parameters": object, "Error": str (optional)}
The Parameters schemas below come from the packet parsers in the same binary
(research/README.md lists how they were read). Types matter: a known key with the
wrong type fails the whole reply silently.

    printer-sim.py --bind 198.51.100.21 --product "Form 4" --machine FORM-4-0

--compat selects the shape of the "version" (compatibility) object, the one part
that is still being confirmed. Logs every frame to stderr.
"""
import argparse, json, socket, struct, sys, threading, uuid

def log(*a):
    print("[printer-sim]", *a, file=sys.stderr, flush=True)

def read_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            return None
        buf += chunk
    return buf

def read_frame(conn):
    head = read_exact(conn, 4)
    if head is None:
        return None
    (n,) = struct.unpack("<I", head)
    if n > 64 * 1024 * 1024:
        log(f"refusing frame of {n} bytes")
        return None
    body = read_exact(conn, n)
    if body is None:
        return None
    trailer = read_exact(conn, 8)
    alen = struct.unpack("<Q", trailer)[0] if trailer else 0
    attachment = b""
    if 0 < alen < 2 * 1024 * 1024 * 1024:
        attachment = read_exact(conn, alen) or b""
    try:
        msg = json.loads(body.decode("utf-8"))
    except ValueError:
        log(f"non-JSON frame ({n} bytes): {body[:200]!r}")
        msg = {"_raw": body[:200].decode("latin-1")}
    return msg, alen, attachment

def frame(obj, attachment=b""):
    body = json.dumps(obj, indent=4).encode("utf-8") + b"\n"
    return struct.pack("<I", len(body)) + body + struct.pack("<Q", len(attachment)) + attachment

# --- compatibility ("version") object -------------------------------------------
# PreForm's own descriptor, embedded in the binary, is
#   {"PF_printing": {"compatible": 1, "formule": {"compatible": [4]}, "flx": {"compatible": 6},
#                    "build": {"num": [21, "dev"]}}, "PF_updating": {"compatible": 1},
#    "PF_log_download": {"formule": {"logDownload": {"compatible": 1}}}}
# and CompatibilityCheckerImpl.cpp requires the printer's object to contain
# "PF_printing" and/or "PF_updating" objects.
def compat(args):
    c = args.compat
    if c == "mirror":
        return {"PF_printing": {"compatible": 1, "formule": {"compatible": [4]}, "flx": {"compatible": 6},
                                "build": {"num": [21, "dev"]}},
                "PF_updating": {"compatible": 1},
                "PF_log_download": {"formule": {"logDownload": {"compatible": 1}}}}
    if c == "wide":
        return {"PF_printing": {"compatible": [1, 2, 3, 4, 5, 6], "formule": {"compatible": [1, 2, 3, 4, 5, 6]},
                                "flx": {"compatible": [1, 2, 3, 4, 5, 6, 7, 8]}, "build": {"num": [21, "dev"]}},
                "PF_updating": {"compatible": [1, 2, 3]},
                "PF_log_download": {"formule": {"logDownload": {"compatible": [1, 2]}}}}
    if c == "minimal":
        return {"PF_printing": {"compatible": 1}, "PF_updating": {"compatible": 1}}
    if c == "empty":
        return {}
    return {}

def information(args):
    return {
        "connectionInterface": "PROTOCOL_INTERFACE_ETHERNET",
        "version": compat(args),
        "printerID": args.serial,
        "printer": {
            "Serial": args.serial,
            "DeviceAlias": args.alias,
            "MachineTypeId": args.machine,
            "FactoryMACAddress": args.mac,
        },
        "ipAddresses": [args.bind],
        "capabilities": [],
    }

def status(args):
    cart = {"cartridgeMaterialCode": args.material, "cartridgeOriginalVolume_mL": 1000.0,
            "cartridgeId": "CART-SIM-1", "cartridgeEstimatedVolumeDispensed_mL": 100.0,
            "cartridgeMeasuredVolume_mL": 900.0}
    return {
        # Shared/src/GetStatus.cpp
        "tankMaterialCode": args.material, "tankId": "TANK-SIM-1",
        "isPrinting": False, "isOpenMode": False, "isPrimed": True, "isRemotePrintEnabled": False,
        "readyToPrintNow_v2": "READY_TO_PRINT_READY",
        "buildPlatformContents_v2": "BUILD_PLATFORM_CONTENTS_CONFIRMED_CLEAR",
        "buildPlatformType": "BUILD_PLATFORM_TYPE_UNKNOWN",
        "estimatedTotalPrintTime_ms": 0.0, "estimatedPrintTimeRemaining_ms": 0.0,
        "isPrePrint": False, "isDashboardRegistrationAllowed": False, "printerIssues": [],
        # Diesel/src/GetStatus_v3.cpp
        "tankTypeString": "FLGPBK05", "readyToPrintNow": True,
        "printerState": "USER_STATE_IDLE",
        "cartridges": [cart], "tankVersionMajor": 1.0, "tankVersionMinor": 0.0,
        "cameraStatus": "CAMERA_STATE_DISABLED", "pumpStatus": "PUMP_STATE_NOT_PRESENT",
        # GetStatus_v1.h / v2.h
        "cartridgeMaterialCode": args.material, "cartridgeOriginalVolume_mL": 1000.0, "cartridgeId": "CART-SIM-1",
        "cartridgeEstimatedVolumeDispensed_mL": 100.0,
        "formAutoStatus": "FORMCELL_UNKNOWN", "formAutoRotation": "", "formAutoFirmwareVersion": "", "formAutoSerial": "",
        "frontCartridgeMaterialCode": args.material, "frontCartridgeOriginalVolume_mL": 1000.0, "frontCartridgeId": "CART-SIM-1",
        "frontCartridgeEstimatedVolumeDispensed_mL": 100.0,
        "backCartridgeMaterialCode": args.material, "backCartridgeOriginalVolume_mL": 1000.0, "backCartridgeId": "CART-SIM-2",
        "backCartridgeEstimatedVolumeDispensed_mL": 0.0,
        # Fuse / Pilkington (harmless for an SLA identity; a Fuse identity needs them)
        "printerMaterial": args.material, "printerPowderLevel_L": 10.0, "isAcceptingJobs": True,
        "estimatedPreprintTime_ms": 0.0, "estimatedPostprintTime_ms": 0.0, "totalPrintTimeRemaining_ms": 0.0,
        "totalPreprintTimeRemaining_ms": 0.0, "totalPostprintTimeRemaining_ms": 0.0,
        "cylinderMaterialCode": args.material, "cylinderMechanicalVersion": 1.0, "cylinderSerial": "CYL-SIM-1",
        "cylinderZAxisRange_mm": 300.0, "materialCredit_g": 0.0, "printingLayer": -1.0, "printingJobRevision": 0.0,
        "printingJobGuid": "{00000000-0000-0000-0000-000000000000}", "jobGuid": "{00000000-0000-0000-0000-000000000000}",
        "bedTemperature_C": 25.0, "primedTimeout_UnixStamp": 0.0, "currentlyRunningJobHeights": [],
        "heightColdFills_mm": 0.0, "heightPostPrint_mm": 0.0, "heightHotPrecoats_mm": 0.0, "heightCorePrint_mm": 0.0,
        "jobBundleIndex": 0.0,
    }

def reply(args, msg, attachment):
    rid = msg.get("Id", "{" + str(uuid.uuid4()) + "}")
    method = msg.get("Method", "")
    version = msg.get("Version", 1)
    params = {}
    ok = True
    if method == "PROTOCOL_METHOD_GET_INFORMATION":
        params = information(args)
    elif method == "PROTOCOL_METHOD_GET_STATUS":
        params = status(args)
    elif method == "PROTOCOL_METHOD_HEARTBEAT":
        params = {}
    elif method in ("PROTOCOL_METHOD_START_JOB", "PROTOCOL_METHOD_UPLOAD_LAYER", "PROTOCOL_METHOD_UPLOAD_FILE",
                    "PROTOCOL_METHOD_ABORT_JOB", "PROTOCOL_METHOD_RESUME_JOB"):
        params = {}          # accept everything; the point is to see what arrives
    else:
        ok = False
    out = {"Id": rid, "ReplyToMethod": method, "Version": version, "Success": ok, "Parameters": params}
    if not ok:
        out["Error"] = "PROTOCOL_ERROR_NO_HANDLER"
    return out

def serve(conn, addr, args):
    log(f"connection from {addr[0]}:{addr[1]}")
    try:
        conn.settimeout(args.idle)
        while True:
            got = read_frame(conn)
            if got is None:
                break
            msg, alen, attachment = got
            log(f"recv {json.dumps(msg, separators=(',', ':'))[:600]} attachment={alen}")
            if args.silent:
                continue
            out = reply(args, msg, attachment)
            conn.sendall(frame(out))
            log(f"sent {json.dumps(out, separators=(',', ':'))[:300]}")
    except socket.timeout:
        log("idle timeout")
    except (ConnectionResetError, BrokenPipeError) as e:
        log(f"peer went away: {e}")
    finally:
        conn.close()
        log(f"closed {addr[0]}:{addr[1]}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--port", type=int, default=35)
    p.add_argument("--compat", default="mirror", choices=["mirror", "wide", "minimal", "empty"])
    p.add_argument("--product", default="Form 4")
    p.add_argument("--machine", default="FORM-4-0")
    p.add_argument("--material", default="FLGPBK05")
    p.add_argument("--serial", default="SimForm4-Loud-Otter")
    p.add_argument("--alias", default="Simulated Form 4")
    p.add_argument("--mac", default="02:00:00:00:00:01")
    p.add_argument("--idle", type=float, default=120.0)
    p.add_argument("--silent", action="store_true", help="log frames but never answer")
    args = p.parse_args()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.bind, args.port))
    s.listen(8)
    log(f"listening on {args.bind}:{args.port} compat={args.compat} serial={args.serial} machine={args.machine}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=serve, args=(conn, addr, args), daemon=True).start()

if __name__ == "__main__":
    main()
