#!/usr/bin/env python3
"""A fake Formlabs printer on TCP port 35, for testing PreFormServer without hardware.

Speaks the framing PreFormServer uses when it probes a printer address
(captured in CI): a little-endian uint32 length, that many bytes of JSON
({"Id": "{guid}", "Method": "PROTOCOL_METHOD_...", "Version": 1}), then a
little-endian uint64 that is presumably the length of a binary attachment
that follows (0 for a probe). Replies use the same framing.

    printer-sim.py --bind 198.51.100.20 --variant 1 --product "Form 4" --machine FORM-4-0

Logs every frame it receives to stderr. --variant picks the shape of the reply,
which is what the research runs are working out.
"""
import argparse, json, socket, struct, sys, threading, time, uuid

def log(*a):
    print("[printer-sim]", *a, file=sys.stderr, flush=True)

def read_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
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
    if 0 < alen < 512 * 1024 * 1024:
        attachment = read_exact(conn, alen) or b""
    try:
        msg = json.loads(body.decode("utf-8"))
    except ValueError:
        log(f"non-JSON frame ({n} bytes): {body[:200]!r}")
        msg = {"_raw": body[:200].decode("latin-1")}
    return msg, alen, attachment

def frame(obj, attachment=b"", variant=1):
    body = json.dumps(obj, indent=4).encode("utf-8") + b"\n"
    if variant == 4:
        return struct.pack("<I", len(body)) + body
    if variant == 9:
        return struct.pack("<I", len(body)) + struct.pack("<Q", len(attachment)) + body + attachment
    return struct.pack("<I", len(body)) + body + struct.pack("<Q", len(attachment)) + attachment

def info(args):
    """Every plausible spelling of the device information at once: a parser that
    ignores unknown keys will find whichever it wants. (Bisect once something is accepted.)"""
    caps = ["PROTOCOL_INTERFACE_ETHERNET"]
    compat = {"PF_printing": {"compatible": 1, "formule": {"compatible": [1, 2, 3, 4]}, "flx": {"compatible": 6},
                              "build": {"num": [21, "dev"]}},
              "PF_updating": {"compatible": 1}, "PF_log_download": {"formule": {"logDownload": {"compatible": 1}}}}
    flat = {}
    for k in ("serial_number", "serialNumber", "SerialNumber", "SerialName", "serial", "Serial", "alias", "Alias", "name", "Name", "hostname"):
        flat[k] = args.serial
    for k in ("product_name", "productName", "ProductName", "product", "Product"):
        flat[k] = args.product
    for k in ("machine_type", "machineType", "machineTypeId", "MachineTypeId", "MachineType", "machine_type_id", "printer_type", "printerType"):
        flat[k] = args.machine
    for k in ("firmware_version", "firmwareVersion", "FirmwareVersion", "version", "Version", "firmware"):
        flat[k] = args.firmware
    flat["firmware_build_number"] = flat["firmwareBuildNumber"] = flat["buildNumber"] = 1234
    for k in ("printer_status", "printerStatus", "PrinterStatus", "status", "Status", "state", "State"):
        flat[k] = "IDLE"
    for k in ("ip_address", "ipAddress", "IpAddress"):
        flat[k] = args.bind
    flat["device_id"] = flat["deviceId"] = flat["DeviceId"] = args.serial
    flat["interface"] = flat["Interface"] = "PROTOCOL_INTERFACE_ETHERNET"
    flat["printer_capabilities"] = flat["machine_capabilities"] = flat["capabilities"] = flat["Capabilities"] = caps
    flat["protocol_version"] = flat["protocolVersion"] = flat["ProtocolVersion"] = 1
    flat.update(compat)
    return flat

def reply(args, msg):
    rid = msg.get("Id", "{" + str(uuid.uuid4()) + "}")
    method = msg.get("Method", "")
    i = info(args)
    v = args.variant
    nested = {c: dict(i) for c in ("Result", "Response", "Data", "Payload", "Information", "Info", "Printer", "Device", "Parameters")}
    everything = {**i, **nested}
    head = {"Id": rid, "ReplyToMethod": method, "Success": True, "Version": 1, "Error": ""}
    if v == 1:   return {**head, **i}
    if v == 2:   return {**head, **everything}
    if v == 3:   return {**head, "Version": 4, **everything}
    if v == 4:   return {**head, **everything}                       # sent without the 8-byte trailer (see frame())
    if v == 5:   return {**head, "Method": method, **everything}
    if v == 6:   return {"Id": rid, "ReplyToMethod": method, "Version": 1, **everything}
    if v == 7:   return {**head, "Error": "PROTOCOL_SUCCESS", **everything}
    if v == 8:   return {**head, "Method": method, "Error": "PROTOCOL_SUCCESS", "Success": "PROTOCOL_SUCCESS", **everything}
    if v == 9:   return {**head, **everything}                       # sent with the trailer before the JSON
    return {**head, **i}

def serve(conn, addr, args):
    log(f"connection from {addr[0]}:{addr[1]}")
    try:
        conn.settimeout(args.idle)
        while True:
            got = read_frame(conn)
            if got is None:
                break
            msg, alen, attachment = got
            log(f"recv {json.dumps(msg, separators=(',', ':'))[:400]} attachment={alen}")
            if args.silent:
                continue
            out = reply(args, msg)
            conn.sendall(frame(out, variant=args.variant))
            log(f"sent {json.dumps(out, separators=(',', ':'))[:400]}")
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
    p.add_argument("--variant", type=int, default=1)
    p.add_argument("--product", default="Form 4")
    p.add_argument("--machine", default="FORM-4-0")
    p.add_argument("--serial", default="SimForm4-Loud-Otter")
    p.add_argument("--firmware", default="2.5.0")
    p.add_argument("--idle", type=float, default=60.0)
    p.add_argument("--silent", action="store_true", help="log frames but never answer")
    args = p.parse_args()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.bind, args.port))
    s.listen(8)
    log(f"listening on {args.bind}:{args.port} variant={args.variant} product={args.product!r} machine={args.machine}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=serve, args=(conn, addr, args), daemon=True).start()

if __name__ == "__main__":
    main()
