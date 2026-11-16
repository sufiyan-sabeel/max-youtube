#!/usr/bin/env python3
"""Generate a throwaway test keystore for prototype builds, and print only its public fingerprint.

The keystore stays on this machine. It is never committed, never uploaded as an artifact, and its
password is never printed — the generated file is written to a path outside the repository and the
script's only output is the certificate fingerprint and a reminder that builds signed with it are TEST
BUILDS.

Production signing is a separate workflow with a permanent, user-controlled key. Nothing here touches it.

Usage:
    python3 tools/make_test_keystore.py [output.p12] [--password-env VAR]

If --password-env names an environment variable, that value is used as the password; otherwise a random
one is generated and written to a sibling `.password` file with mode 0600 so a later build step can read
it without anyone typing it.
"""
import datetime
import os
import secrets
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

ALIAS = "max-youtube-test"


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "max-youtube-test.p12"
    password_env = None
    if "--password-env" in sys.argv:
        password_env = sys.argv[sys.argv.index("--password-env") + 1]

    if os.path.exists(out):
        print("refusing to overwrite %s" % out, file=sys.stderr)
        return 2

    if password_env:
        password = os.environ.get(password_env)
        if not password:
            print("%s is not set" % password_env, file=sys.stderr)
            return 2
        password = password.encode()
    else:
        password = secrets.token_urlsafe(24).encode()

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "MAX YouTube TEST BUILD - not for release"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MAX Patcher test"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    with open(out, "wb") as f:
        f.write(pkcs12.serialize_key_and_certificates(
            ALIAS.encode(), key, cert, None,
            serialization.BestAvailableEncryption(password)))
    os.chmod(out, 0o600)

    if not password_env:
        with open(out + ".password", "wb") as f:
            f.write(password)
        os.chmod(out + ".password", 0o600)

    # Public information only. The private key and the password never leave this machine.
    fingerprint = cert.fingerprint(hashes.SHA256()).hex()
    print("keystore:   %s (mode 0600, not in any repository)" % out)
    print("alias:      %s" % ALIAS)
    print("subject:    %s" % cert.subject.rfc4514_string())
    print("valid to:   %s" % cert.not_valid_after_utc.date())
    print("SHA-256:    %s" % fingerprint)
    print("")
    print("Every APK signed with this key is a TEST BUILD and must be labelled as one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
