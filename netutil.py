"""Finding the address phones use to reach this laptop."""
from __future__ import annotations

import ipaddress
import socket

HOTSPOT_IP = "192.168.137.1"  # Windows Mobile Hotspot always gives the laptop this address
VIRTUAL_PREFIXES = ("192.168.56.",)  # VirtualBox host-only adapter: phones can never reach it


def _route_ip() -> str | None:
    """The address of the network card Windows uses for normal traffic (no data is actually sent)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def lan_ips() -> list[str]:
    """All usable IPv4 addresses of this laptop, best first."""
    found: set[str] = set()
    try:
        found |= {info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        pass
    route = _route_ip()
    if route:
        found.add(route)

    usable = []
    for ip in found:
        try:
            addr = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if addr.is_loopback or addr.is_link_local or addr.is_unspecified or ip.startswith(VIRTUAL_PREFIXES):
            continue
        usable.append(ip)

    def rank(ip: str) -> tuple:
        return (ip != HOTSPOT_IP, ip != route, ip)

    return sorted(usable, key=rank)


def best_ip(override: str = "") -> str:
    if override:
        return override
    ips = lan_ips()
    return ips[0] if ips else "127.0.0.1"


def base_url(port: int, override: str = "") -> str:
    return f"http://{best_ip(override)}:{port}"


def guest_url(token: str, port: int, override: str = "") -> str:
    return f"{base_url(port, override)}/s/{token}"


def port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()
