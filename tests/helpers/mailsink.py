"""
A local "catch-all" mail server for tests (nothing is sent to the internet).

The backend sends mail with SMTP + STARTTLS (services/email_service.py). This starts an
aiosmtpd server on localhost that accepts any login, requires STARTTLS with a throwaway
certificate made for "localhost", and saves every message as an .eml file. The test backend
trusts that certificate through SSL_CERT_FILE (a bundle of certifi's CAs + this one, so its
other HTTPS calls, e.g. Google reCAPTCHA, still verify).

Turn it on for a pytest run with TEST_MAIL_SINK=1 (see helpers/config.backend_env and the
`mail_sink` fixture in conftest.py). Tests read the captured emails with MailSink.messages().
"""

import datetime
import email
import email.policy
import ipaddress
import ssl
from pathlib import Path

import certifi
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .config import REPORTS_DIR

MAIL_DIR = REPORTS_DIR / "mail"
CERT_DIR = MAIL_DIR / "tls"
CERT_FILE, KEY_FILE, BUNDLE_FILE = CERT_DIR / "cert.pem", CERT_DIR / "key.pem", CERT_DIR / "bundle.pem"
MAIL_PORT = 2525


def ensure_certificate() -> Path:
    """Create (once) a self-signed certificate for localhost and a CA bundle that trusts it."""
    if BUNDLE_FILE.exists():
        return BUNDLE_FILE
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                                                        x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
            .sign(key, hashes.SHA256()))
    KEY_FILE.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    pem = cert.public_bytes(serialization.Encoding.PEM)
    CERT_FILE.write_bytes(pem)
    BUNDLE_FILE.write_bytes(Path(certifi.where()).read_bytes() + b"\n" + pem)
    return BUNDLE_FILE


class _SaveToDisk:
    async def handle_DATA(self, server, session, envelope):
        MAIL_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        (MAIL_DIR / f"{stamp}.eml").write_bytes(envelope.content)
        return "250 Message accepted for delivery"


def _accept_any_login(server, session, envelope, mechanism, auth_data):
    return AuthResult(success=True)


class MailSink:
    def __init__(self, port: int = MAIL_PORT):
        ensure_certificate()
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(CERT_FILE, KEY_FILE)
        self.controller = Controller(_SaveToDisk(), hostname="127.0.0.1", port=port, server_hostname="localhost",
                                     tls_context=context, require_starttls=True,
                                     authenticator=_accept_any_login, auth_require_tls=True)

    def start(self) -> "MailSink":
        MAIL_DIR.mkdir(parents=True, exist_ok=True)
        for old in MAIL_DIR.glob("*.eml"):
            old.unlink()
        self.controller.start()
        return self

    def stop(self) -> None:
        self.controller.stop()

    @staticmethod
    def messages(to: str | None = None) -> list[email.message.EmailMessage]:
        """Captured emails, oldest first (optionally only those sent to `to`)."""
        found = []
        for path in sorted(MAIL_DIR.glob("*.eml")):
            msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
            if to is None or to.lower() in str(msg["To"]).lower():
                found.append(msg)
        return found
