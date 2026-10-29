import secrets
import ssl
from pathlib import Path

import pytest
from app.transport.serve import configuration


def test_network_server_is_restricted_and_requires_tls_files() -> None:
    config = configuration(secrets.token_hex(32), Path('missing-synthetic-certificates'))
    assert (config.host, config.port) == ('192.168.1.190', 8443)
    assert config.proxy_headers is False
    assert config.access_log is False
    assert config.server_header is False
    assert config.ws == 'none'
    assert config.limit_concurrency == 16
    assert config.ssl_version == ssl.PROTOCOL_TLS_SERVER
    # Fail before a socket is opened; absence of TLS files cannot fall back to HTTP.
    with pytest.raises(FileNotFoundError):
        config.load()


def test_launcher_requires_explicit_activation() -> None:
    import subprocess

    result = subprocess.run(
        ['powershell', '-NoProfile', '-File', 'scripts/start-probe.ps1'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert 'explicit -Activate' in result.stderr
