"""Host-only HTTPS keep-alive, with one connection per thread and origin.

An exchange sends its request once. In particular, a lost claim response must
never cause an automatic replay. Retry decisions remain in resilience.py.
"""
import http.client
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit


class ExchangeError(RuntimeError):
    def __init__(self, reason, *, retryable=False):
        # Exception details may contain private headers or URLs; never copy them.
        super().__init__(reason)
        self.retryable = retryable


_local = threading.local()
_tls = ssl.create_default_context()
_IDLE_SECONDS = 45


def close_connections():
    """Close only this thread's connections; other requests are independent."""
    for connection, _ in getattr(_local, 'connections', {}).values():
        connection.close()
    _local.connections = {}


def _connection(site, proxy, timeout):
    origin = urlsplit(site)
    if (origin.scheme != 'https' or not origin.hostname or origin.username
            or origin.password or origin.query or origin.fragment):
        raise ExchangeError('invalid HTTPS site configuration')
    key = (origin.hostname, origin.port or 443, proxy)
    connections = getattr(_local, 'connections', None)
    if connections is None:
        connections = _local.connections = {}
    now = time.monotonic()
    for old_key, (connection, used) in list(connections.items()):
        if now - used >= _IDLE_SECONDS:
            connection.close()
            del connections[old_key]
    if key not in connections:
        if len(connections) >= 4:
            old_key = min(connections, key=lambda k: connections[k][1])
            connections.pop(old_key)[0].close()
        if proxy:
            route = urlsplit(proxy)
            if (route.scheme != 'http' or not route.hostname or route.username
                    or route.password or route.path not in ('', '/')
                    or route.query or route.fragment):
                raise ExchangeError('invalid HTTP proxy configuration')
            connection = http.client.HTTPSConnection(
                route.hostname, route.port or 80, timeout=timeout, context=_tls)
            connection.set_tunnel(origin.hostname, origin.port or 443)
        else:
            connection = http.client.HTTPSConnection(
                origin.hostname, origin.port or 443, timeout=timeout, context=_tls)
        connections[key] = (connection, now)
    return key, connections[key][0]


def exchange(site, path, headers, body, *, proxy=None, timeout=10, maximum=1024*1024):
    """Return one bounded response. TLS is verified; redirects are not followed.

    The proxy is explicit, so this transport cannot silently change the server's
    route based on an inherited environment or fall back to a direct connection.
    Credentials are supplied anew on every request, never stored in the pool.
    """
    deadline = time.monotonic() + timeout
    key = connection = None
    response = None
    completed = False

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError()
        return seconds

    try:
        key, connection = _connection(site, proxy, min(8, remaining()))
        if connection.sock is None:
            connection.timeout = min(8, remaining())
            connection.connect()
        connection.sock.settimeout(remaining())
        target = urlsplit(site.rstrip('/') + path)
        request_path = target.path or '/'
        if target.query:
            request_path += '?' + target.query
        connection.request('POST', request_path, body=body, headers=headers)
        connection.sock.settimeout(remaining())
        response = connection.getresponse()
        if response.length is not None and response.length > maximum:
            raise ExchangeError('response too large')
        data = bytearray()
        while True:
            # getresponse may detach a Connection: close socket. The response
            # still owns it, with the original bounded socket timeout.
            if connection.sock is not None:
                connection.sock.settimeout(remaining())
            else:
                remaining()
            chunk = response.read1(min(65536, maximum + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > maximum:
                raise ExchangeError('response too large')
        if response.length not in (None, 0):
            raise ExchangeError('incomplete response', retryable=True)
        _local.connections[key] = (connection, time.monotonic())
        completed = True
        return response.status, bytes(data)
    except ssl.SSLCertVerificationError:
        error = ExchangeError('TLS certificate verification failed')
    except (socket.timeout, TimeoutError):
        error = ExchangeError('transport timeout', retryable=True)
    except (OSError, http.client.HTTPException):
        error = ExchangeError('connection failed', retryable=True)
    except ExchangeError as caught:
        error = caught
    except ValueError:
        error = ExchangeError('invalid HTTP configuration')
    finally:
        # No stale or partially read stream can be reused after an exception.
        if not completed:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
                _local.connections.pop(key, None)
    raise error from None
