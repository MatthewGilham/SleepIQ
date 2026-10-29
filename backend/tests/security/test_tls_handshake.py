"""Real TLS handshakes in memory, with ephemeral synthetic certificates only."""

import base64
import json
import secrets
import shutil
import ssl
import subprocess
from pathlib import Path

import pytest
from app.transport.serve import configuration


@pytest.fixture
def certificates(scratch: Path) -> Path:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-File",
         "backend/tests/security/make_tls_fixtures.ps1", "-Destination", str(scratch)],
        capture_output=True, text=True, check=False, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr
    parameters = json.loads(scratch.joinpath("synthetic-key.json").read_text())

    def der(tag: int, value: bytes) -> bytes:
        length = len(value)
        encoded = length.to_bytes(max(1, (length.bit_length() + 7) // 8), "big")
        prefix = bytes([length]) if length < 128 else bytes([128 + len(encoded)]) + encoded
        return bytes([tag]) + prefix + value

    # Encode PKCS#1 RSA parameters exported by Windows; no custom signing/cryptography.
    integers = [der(2, b"\0")]
    for name in ("Modulus", "Exponent", "D", "P", "Q", "DP", "DQ", "InverseQ"):
        value = base64.b64decode(parameters[name]).lstrip(b"\0")
        if value[0] & 128:
            value = b"\0" + value
        integers.append(der(2, value))
    pem = base64.encodebytes(der(48, b"".join(integers)))
    # The allowlisted line contains only PEM delimiters, not key material.
    # Key bytes are freshly generated synthetic data in the ignored scratch directory.
    scratch.joinpath("sync.mgilham.online.key").write_bytes(
        b"-----BEGIN RSA PRIVATE KEY-----\n" + pem + b"-----END RSA PRIVATE KEY-----\n",  # pragma: allowlist secret
    )
    return scratch


def handshake(server: ssl.SSLContext, client: ssl.SSLContext, hostname: str) -> None:
    server_in, server_out, client_in, client_out = (ssl.MemoryBIO() for _ in range(4))
    server_socket = server.wrap_bio(server_in, server_out, server_side=True)
    client_socket = client.wrap_bio(client_in, client_out, server_hostname=hostname)
    client_done = server_done = False
    for _ in range(20):
        if not client_done:
            try:
                client_socket.do_handshake()
                client_done = True
            except ssl.SSLWantReadError:
                pass
        if data := client_out.read():
            server_in.write(data)
        if not server_done:
            try:
                server_socket.do_handshake()
                server_done = True
            except ssl.SSLWantReadError:
                pass
        if data := server_out.read():
            client_in.write(data)
        if client_done and server_done:
            assert client_socket.version() in ("TLSv1.2", "TLSv1.3")
            return
    pytest.fail("TLS handshake failed to finish")


@pytest.mark.parametrize("case", ["valid", "chain", "hostname", "expired"])
def test_real_tls_certificate_validation(certificates: Path, case: str) -> None:
    if case == "expired":
        shutil.copyfile(
            certificates / "expired.crt", certificates / "sync.mgilham.online.crt",
        )
    config = configuration(secrets.token_hex(32), certificates)
    config.load()  # Uses the real application server configuration; no network socket opened.
    assert config.ssl is not None
    assert config.ssl.minimum_version >= ssl.TLSVersion.TLSv1_2
    client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if case != "chain":
        client.load_verify_locations(cafile=certificates / "root.crt")
    hostname = "wrong.invalid" if case == "hostname" else "sync.mgilham.online"
    if case == "valid":
        handshake(config.ssl, client, hostname)
    else:
        with pytest.raises(ssl.SSLCertVerificationError) as error:
            handshake(config.ssl, client, hostname)
        expected = {"chain": "issuer certificate", "hostname": "Hostname mismatch", "expired": "expired"}
        assert expected[case] in error.value.verify_message
