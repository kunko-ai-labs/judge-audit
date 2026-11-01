"""The test suite runs offline (#169): a test that connects to, sends to or looks up a host
other than this computer fails, within the limits listed below.

`install(log)` replaces, in the Python process it runs in:
- `socket.socket.connect`, `connect_ex`, `sendto` and `sendmsg` (with an address);
- `socket.getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr` and
  `getnameinfo`, in `socket` and in the `_socket` C module it wraps.
Each refuses any address that is not this computer (loopback 127.0.0.0/8, ::1 and its
IPv4-mapped form ::ffff:127.0.0.1, the unspecified 0.0.0.0 and ::, `localhost`, or a Unix
socket), raises `NetworkBlocked` (a `ConnectionError`, so the code under test sees what it
would see offline) and appends one line naming the host to `log`. A `.invalid` name (RFC 6761)
is answered here as unresolvable, without a query or a log line. Every HTTP client in the
package (urllib, `OPENER`, http.client, httpx inside the anthropic SDK, huggingface_hub) ends
in one of these calls. This computer's own host name is refused like any other name: checking
that it resolves to loopback would itself be a lookup that can leave the computer.

The log, not the exception, is what fails a test: `tests/conftest.py` reads it after every
test, so a judge that catches the error and records it as a failed row still fails its test.
`sitecustomize.py` next to this file installs the same guard in every Python process a test
starts with this environment (`python -m judge_audit.cli ...`), writing to the same log.

Not covered, by construction:
- a child process that is not Python (the Node bridge, `curl`, `git`);
- a Python child started with `-I`, `-E` or `-S`, or with an `env=` that drops PYTHONPATH or
  JUDGE_AUDIT_OFFLINE_LOG: it does not load `sitecustomize.py`;
- a socket built from the C type `_socket.socket` directly, or opened by a C extension: the
  C type's methods cannot be replaced, and `socket.socket.__init__` calls `_socket.socket` by
  name, so it cannot be swapped for the guarded class either;
- the `custom` provider of the `llm` judge, a user's own module loaded from
  LLM_PROVIDER_MODULE: it runs under this guard in a test, but the static inventory
  (`tests/test_network_guard.py`) cannot read it, by design.
"""
from __future__ import annotations

import _socket
import ipaddress
import os
import socket

LOG_VAR = "JUDGE_AUDIT_OFFLINE_LOG"
LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}
LOOKUPS = ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr")


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
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or ip.is_unspecified or bool(mapped and mapped.is_loopback)


def allowed(address) -> bool:
    """Whether a test may reach `address`: a Unix socket path, or a host on this computer."""
    if isinstance(address, (str, bytes)):                    # AF_UNIX
        return True
    if isinstance(address, tuple) and address:
        return _loopback(address[0])
    return False


def _invalid(host) -> bool:
    name = host.decode("ascii", "replace") if isinstance(host, bytes) else host
    return isinstance(name, str) and name.lower().rstrip(".").endswith(".invalid")


def install(log: str) -> None:
    """Refuse and record every connection, datagram or lookup that leaves this computer.
    Idempotent."""
    if getattr(socket.socket.connect, "_offline_guard", False):
        return

    def record(what: str, host) -> None:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{what} {host!r}\n")

    def refuse(what: str, host):
        record(what, host)
        return NetworkBlocked(f"tests run offline: a {what} of {host!r} was refused")

    sock = socket.socket
    connect, connect_ex, sendto, sendmsg = (sock.connect, sock.connect_ex, sock.sendto,
                                            sock.sendmsg)

    def guarded_connect(self, address):
        if not allowed(address):
            raise refuse("connect", address)
        return connect(self, address)

    def guarded_connect_ex(self, address):
        if not allowed(address):
            raise refuse("connect", address)
        return connect_ex(self, address)

    def guarded_sendto(self, data, *rest):
        if rest and not allowed(rest[-1]):          # (data, address) or (data, flags, address)
            raise refuse("send", rest[-1])
        return sendto(self, data, *rest)

    def guarded_sendmsg(self, buffers, *rest, **kwargs):
        address = rest[2] if len(rest) > 2 else kwargs.get("address")
        if address is not None and not allowed(address):
            raise refuse("send", address)
        return sendmsg(self, buffers, *rest, **kwargs)

    def lookup(original):
        def guarded(host, *args, **kwargs):
            if _invalid(host):
                # RFC 6761: a .invalid name never resolves. Answer as the resolver would,
                # here, so a test of the "no such host" path does not send a query out.
                raise socket.gaierror(socket.EAI_NONAME, f"{host!r} does not resolve (.invalid)")
            if host is not None and not _loopback(host):
                raise refuse("lookup", host)
            return original(host, *args, **kwargs)
        guarded._offline_guard = True  # type: ignore[attr-defined]
        return guarded

    for f in (guarded_connect, guarded_connect_ex, guarded_sendto, guarded_sendmsg):
        f._offline_guard = True  # type: ignore[attr-defined]
    sock.connect = guarded_connect                           # type: ignore[method-assign]
    sock.connect_ex = guarded_connect_ex                     # type: ignore[method-assign]
    sock.sendto = guarded_sendto                             # type: ignore[method-assign]
    sock.sendmsg = guarded_sendmsg                           # type: ignore[method-assign]
    # Each module's own function is wrapped: socket.getaddrinfo is Python code that calls
    # _socket.getaddrinfo by name, so one wrapper over both would call itself.
    for module in (socket, _socket):
        for name in LOOKUPS:
            setattr(module, name, lookup(getattr(module, name)))
        original = module.getnameinfo

        def guarded_getnameinfo(sockaddr, flags, original=original):
            if not allowed(sockaddr):
                raise refuse("lookup", sockaddr)
            return original(sockaddr, flags)
        guarded_getnameinfo._offline_guard = True  # type: ignore[attr-defined]
        module.getnameinfo = guarded_getnameinfo


def install_from_env() -> None:
    log = os.environ.get(LOG_VAR)
    if log:
        install(log)
