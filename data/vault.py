"""Almacen cifrado de Kreix (`.krx`): la base de datos entera, cifrada con una Contrasena Maestra.

Mecanismo: la clave se deriva de la contrasena con PBKDF2-HMAC-SHA256 (sal aleatoria de 16 bytes, 600 000 vueltas) y
cifra con Fernet (AES-128-CBC + HMAC-SHA256, autenticado: si la contrasena es mala o el archivo se altera, se rechaza).
Archivo: `KRX1` | vueltas (4 bytes) | sal (16 bytes) | token Fernet con la base de datos serializada.

Los datos viven en memoria mientras la app esta abierta (ver `data.secure_store`); a disco solo llega texto cifrado.
Este modulo es puro: no conoce SQLite, SQLAlchemy ni la interfaz.
"""
from __future__ import annotations

import base64
import os
import struct
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"KRX1"
SALT_BYTES = 16
ITERATIONS = 600_000
EXTENSION = ".krx"
_HEADER = len(MAGIC) + 4 + SALT_BYTES
MIN_PASSWORD = 8


class VaultError(Exception):
    """Base de los fallos del almacen cifrado."""


class WrongPasswordError(VaultError):
    """La contrasena no abre el archivo (o el archivo esta alterado)."""


class CorruptVaultError(VaultError):
    """El archivo no es un almacen de Kreix."""


def derive_key(password: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


class Vault:
    """Una clave ya derivada. Se deriva una sola vez al abrir la app; cada guardado solo cifra."""

    def __init__(self, password: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> None:
        self._salt = salt if salt is not None else os.urandom(SALT_BYTES)
        self._iterations = iterations
        self._fernet = Fernet(derive_key(password, self._salt, iterations))

    @property
    def iterations(self) -> int:
        return self._iterations

    # ------------------------------------------------------------------ bytes <-> bytes
    def seal(self, plain: bytes) -> bytes:
        return MAGIC + struct.pack(">I", self._iterations) + self._salt + self._fernet.encrypt(plain)

    @classmethod
    def unseal(cls, blob: bytes, password: str) -> tuple["Vault", bytes]:
        """Abre un archivo: devuelve el almacen (con su clave) y el contenido en claro."""
        if len(blob) <= _HEADER or not blob.startswith(MAGIC):
            raise CorruptVaultError("not a Kreix vault")
        (iterations,) = struct.unpack(">I", blob[len(MAGIC):len(MAGIC) + 4])
        if not 1 <= iterations <= 10_000_000:
            raise CorruptVaultError("bad key derivation parameters")
        salt = blob[len(MAGIC) + 4:_HEADER]
        vault = cls(password, salt, iterations)
        try:
            return vault, vault._fernet.decrypt(blob[_HEADER:])
        except InvalidToken as exc:
            raise WrongPasswordError("wrong password or altered file") from exc

    # ------------------------------------------------------------------ archivo
    def write(self, path: Path, plain: bytes) -> None:
        """Guarda cifrado y de forma atomica; conserva la version anterior como `.bak` (tambien cifrada)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".part")
        partial.write_bytes(self.seal(plain))
        if path.exists():
            os.replace(path, path.with_name(path.name + ".bak"))
        os.replace(partial, path)


class SessionSeal:
    """Cifrado con una clave aleatoria que solo existe en memoria durante esta sesion (copias de "Deshacer")."""

    def __init__(self) -> None:
        self._fernet = Fernet(Fernet.generate_key())

    def seal(self, plain: bytes) -> bytes:
        return self._fernet.encrypt(plain)

    def unseal(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)

