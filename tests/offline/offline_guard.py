"""The test suite runs offline (#169): no test may open a connection to, or look up, a host
other than this computer.

`install(log)` replaces `socket.socket.connect`, `socket.socket.connect_ex` and
`socket.getaddrinfo` with versions that refuse any address that is not loopback (127.0.0.0/8,
::1, `localhost`) or a Unix socket, raise `NetworkBlocked` (a `ConnectionError`, so the code
under test sees what it would see offline) and append one line naming the host to `log`. A
`.invalid` name (RFC 6761) is answered here as unresolvable, without a query or a log line.
Every HTTP client in the package (urllib, `OPENER`, http.client, httpx inside the anthropic
SDK, huggingface_hub) ends in one of those three calls.

The log, not the exception, is what fails a test: `tests/conftest.py` reads it after every
test, so a judge that catches the error and records it as a failed row still fails its test.
`sitecustomize.py` next to this file installs the same guard in every Python process a test
starts with this environment (`python -m judge_audit.cli ...`), writing to the same log.
"""
from __future__ import annotations

import ipaddress
import os
import socket

LOG_VAR = "JUDGE_AUDIT_OFFLINE_LOG"
LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}


class NetworkBlocked(ConnectionError):
    """A test tried to reach a host other than this computer."""


def _loopback(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    host = host.split("%", 1)[0].strip("[]").lower()        # an IPv6 zone, brackets
    if host in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def allowed(address) -> bool:
    """Whether a test may connect to `address`: a Unix socket path, or a loopback host."""
    if isinstance(address, (str, bytes)):                    # AF_UNIX
        return True
    if isinstance(address, tuple) and address:
        return _loopback(address[0])
    return False


def install(log: str) -> None:
    """Refuse and record every connection or lookup that leaves this computer. Idempotent."""
    if getattr(socket.socket.connect, "_offline_guard", False):
        return

    def record(what: str, host) -> None:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{what} {host!r}\n")

    connect, connect_ex, getaddrinfo = (socket.socket.connect, socket.socket.connect_ex,
                                        socket.getaddrinfo)

    def guarded_connect(self, address):
        if not allowed(address):
            record("connect", address)
            raise NetworkBlocked(f"tests run offline: a connection to {address!r} was refused")
        return connect(self, address)

    def guarded_connect_ex(self, address):
        if not allowed(address):
            record("connect", address)
            raise NetworkBlocked(f"tests run offline: a connection to {address!r} was refused")
        return connect_ex(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        name = host.decode("ascii", "replace") if isinstance(host, bytes) else host
        if isinstance(name, str) and name.lower().rstrip(".").endswith(".invalid"):
            # RFC 6761: a .invalid name never resolves. Answer as the resolver would, here,
            # so a test of the "no such host" path does not send a query out.
            raise socket.gaierror(socket.EAI_NONAME, f"{name} does not resolve (.invalid)")
        if host is not None and not _loopback(host):
            record("lookup", host)
            raise NetworkBlocked(f"tests run offline: a lookup of {host!r} was refused")
        return getaddrinfo(host, *args, **kwargs)

    for f in (guarded_connect, guarded_connect_ex, guarded_getaddrinfo):
        f._offline_guard = True  # type: ignore[attr-defined]
    socket.socket.connect = guarded_connect                  # type: ignore[method-assign]
    socket.socket.connect_ex = guarded_connect_ex            # type: ignore[method-assign]
    socket.getaddrinfo = guarded_getaddrinfo


def install_from_env() -> None:
    log = os.environ.get(LOG_VAR)
    if log:
        install(log)
