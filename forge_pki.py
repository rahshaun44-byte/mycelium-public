#!/usr/bin/env python3
"""
Quantum Flex: Pure-Python Ed25519 PKI Forge
===========================================
Generates a complete, compliant mTLS certificate authority, server cert (with SANs),
and client cert using Ed25519 curve parameters.
Zero external dependencies (uses standard python `cryptography`).
"""

import datetime
from pathlib import Path
import ipaddress

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def generate_pki(output_dir: Path):
    ca_dir = output_dir / "ca"
    server_dir = output_dir / "server"
    client_dir = output_dir / "client"

    for d in (ca_dir, server_dir, client_dir):
        d.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(datetime.timezone.utc)
    valid_until = now + datetime.timedelta(days=365)

    print("[*] Generating Ed25519 Root CA...")
    ca_key = ed25519.Ed25519PrivateKey.generate()
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "QuantumFlex-Root-CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QuantumFlex"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Security"),
    ])

    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(valid_until)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key=ca_key, algorithm=None)
    )

    # Save CA
    (ca_dir / "ca.key").write_bytes(
        ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (ca_dir / "ca.crt").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    print(f"    -> Created {ca_dir / 'ca.crt'}")

    print("[*] Generating Ed25519 Server Certificate (with SAN 127.0.0.1 / localhost)...")
    server_key = ed25519.Ed25519PrivateKey.generate()
    server_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "quantum-flex-server"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QuantumFlex"),
    ])

    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(valid_until)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(private_key=ca_key, algorithm=None)
    )

    (server_dir / "server.key").write_bytes(
        server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (server_dir / "server.crt").write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    print(f"    -> Created {server_dir / 'server.crt'}")

    print("[*] Generating Ed25519 Client Certificate...")
    client_key = ed25519.Ed25519PrivateKey.generate()
    client_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "quantum-flex-client"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "QuantumFlex"),
    ])

    client_cert = (
        x509.CertificateBuilder()
        .subject_name(client_name)
        .issuer_name(ca_name)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(valid_until)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(private_key=ca_key, algorithm=None)
    )

    (client_dir / "client.key").write_bytes(
        client_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (client_dir / "client.crt").write_bytes(client_cert.public_bytes(serialization.Encoding.PEM))
    print(f"    -> Created {client_dir / 'client.crt'}")

    print("\n[+] PKI Perimeter Successfully Established:")
    print(f"    CA Cert     : {ca_dir / 'ca.crt'}")
    print(f"    Server Cert : {server_dir / 'server.crt'}")
    print(f"    Client Cert : {client_dir / 'client.crt'}")


if __name__ == "__main__":
    import sys
    target = Path("pki") if len(sys.argv) < 2 else Path(sys.argv[1])
    generate_pki(target)
