import socket
from companion.cli import _find_free_port


def test_find_free_port_returns_int():
    port = _find_free_port(start=15000)
    assert isinstance(port, int)
    assert 15000 <= port < 15100


def test_find_free_port_skips_occupied():
    # Occupy 15000
    s = socket.socket()
    s.bind(("127.0.0.1", 15000))
    try:
        port = _find_free_port(start=15000)
        assert port != 15000
        assert 15001 <= port < 15100
    finally:
        s.close()
