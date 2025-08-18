# hub/discovery.py
import ipaddress
import json
import socket
from contextlib import closing
from typing import List, Dict

# ------- VISA (USB/GPIB/LXI) DISCOVERY -------
def visa_scan() -> List[Dict]:
    """
    Return a list of reachable VISA resources and their *IDN?.
    Works with real pyvisa or the pyvisa-sim backend if installed.
    """
    out: List[Dict] = []
    try:
        import pyvisa
    except Exception:
        # pyvisa not installed → return empty (API will handle gracefully)
        return out

    try:
        # If a simulator config is exported (PYVISA_SIM_CONF), this will still work
        rm = pyvisa.ResourceManager()
        for rsrc in rm.list_resources():
            info = {"resource": rsrc, "ok": False, "idn": "", "error": ""}
            try:
                with rm.open_resource(rsrc) as inst:
                    inst.timeout = 1000  # ms
                    # Not all instruments support *IDN?, so try/except
                    try:
                        idn = inst.query("*IDN?").strip()
                    except Exception:
                        idn = ""
                    info.update({"ok": True, "idn": idn})
            except Exception as e:
                info["error"] = str(e)
            out.append(info)
    except Exception:
        # If VISA backends aren't present (e.g., no NI backend), just return empty.
        pass
    return out

# ------- SIMPLE LAN SWEEP (TCP PROBE) -------
def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except Exception:
            return False

def quick_lan_sweep(subnet: str = "192.168.0.0/24", ports=(5025, 80, 8080, 4880)) -> List[Dict]:
    """
    Very small TCP sweep for SCPI-over-TCP devices (5025 is common),
    plus a few generic control ports. This is best-effort only.
    """
    results: List[Dict] = []
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except Exception:
        return results

    # Keep it light: only probe the first 64 hosts by default (skip .0/.255)
    to_check = list(net.hosts())[:64]
    for ip in to_check:
        ip_str = str(ip)
        open_ports = [p for p in ports if _port_open(ip_str, p)]
        if not open_ports:
            continue

        # Try SCPI *IDN? on 5025 if open
        idn = ""
        if 5025 in open_ports:
            try:
                with closing(socket.create_connection((ip_str, 5025), timeout=0.4)) as s:
                    s.sendall(b"*IDN?\n")
                    s.settimeout(0.4)
                    data = s.recv(512)
                    idn = data.decode(errors="ignore").strip()
            except Exception:
                pass

        results.append({"ip": ip_str, "open_ports": open_ports, "idn": idn})
    return results
