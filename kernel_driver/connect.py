import os
import tempfile
import socket
import json
import asyncio


def get_port(ip: str) -> int:
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\0" * 8)
    sock.bind((ip, 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def write_connection_file(
    fname: str = "",
    ip: str = "",
    key: bytes = b"",
    transport: str = "tcp",
    signature_scheme: str = "hmac-sha256",
    kernel_name: str = "",
):
    ip = ip or "127.0.0.1"

    if not fname:
        f, fname = tempfile.mkstemp(suffix=".json")
        os.close(f)
    f = open(fname, "wt")

    channels = ["shell", "iopub", "stdin", "control", "hb"]

    cfg = {f"{c}_port": get_port(ip) for c in channels}

    cfg["ip"] = ip
    cfg["key"] = key.decode()
    cfg["transport"] = transport
    cfg["signature_scheme"] = signature_scheme
    cfg["kernel_name"] = kernel_name

    f.write(json.dumps(cfg, indent=2))
    f.close()

    return fname, cfg


async def launch_kernel(kernel_spec_path, connection_file_path):
    with open(kernel_spec_path) as f:
        kernel_spec = json.load(f)
    cmd = [s.format(connection_file=connection_file_path) for s in kernel_spec["argv"]]
    p = await asyncio.create_subprocess_exec(*cmd)
    return p
