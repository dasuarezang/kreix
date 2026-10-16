"""Cuanta proteccion da una contrasena. Puro, sin Qt: es un aviso para quien la escribe, no una regla (la unica regla
es el minimo de `data.vault.MIN_PASSWORD`).

La estimacion es deliberadamente simple y honesta: tamano del alfabeto usado por la longitud efectiva (los caracteres
repetidos valen poco), con tope bajo para claves tipicas (listas de contrasenas comunes, teclas seguidas, una sola letra
repetida, solo numeros cortos).
"""
from __future__ import annotations

import math
import string
from dataclasses import dataclass

from core.i18n import N_

LEVELS = 5            # 0 muy debil ... 4 muy fuerte
LABELS = (N_("Muy débil"), N_("Débil"), N_("Aceptable"), N_("Buena"), N_("Muy fuerte"))

_COMMON = frozenset("""
password contraseña contrasena password1 password123 123456 1234567 12345678 123456789 1234567890 12345678910 qwerty qwertyui
qwerty123 qwertyuiop abc123 abcd1234 iloveyou admin administrador letmein welcome monkey dragon football futbol barcelona
realmadrid madrid kreix kreix123 kreixkreix 11111111 00000000 87654321 asdfghjk asdfghjkl zxcvbnm 1q2w3e4r 1qaz2wsx
contraseña1 contraseña123 secreto secret passw0rd p@ssw0rd p@ssword hola1234 holamundo
""".split())
_ROWS = ("qwertyuiopasdfghjklzxcvbnm", "abcdefghijklmnopqrstuvwxyz", "0123456789", "qazwsxedcrfvtgbyhnujmikolp")


@dataclass(frozen=True, slots=True)
class Strength:
    level: int           # 0..4
    hint: str            # que mejorar (castellano, para traducir con tr); vacio si no hace falta nada

    @property
    def label(self) -> str:
        return LABELS[self.level]


def _runs_of_keys(text: str) -> bool:
    """Casi toda la clave es una tirada de teclas contiguas (abcdef, 123456, qwerty, 987654...)."""
    lower = text.lower()
    covered = [False] * len(lower)
    for row in _ROWS:
        for source in (row, row[::-1]):
            for size in range(len(lower), 3, -1):
                for start in range(len(source) - size + 1):
                    chunk = source[start:start + size]
                    at = lower.find(chunk)
                    while at != -1:
                        for i in range(at, at + size):
                            covered[i] = True
                        at = lower.find(chunk, at + 1)
    return sum(covered) >= max(4, round(len(lower) * 0.75))


def _core(text: str) -> str:
    """Si la clave es un bloque repetido (abab..., Xy7!Xy7!...), solo vale el bloque."""
    for size in range(1, len(text) // 2 + 1):
        if len(text) % size == 0 and text == text[:size] * (len(text) // size):
            return text[:size]
    return text


def _bits(text: str) -> float:
    pool = 0
    pool += 26 if any(c in string.ascii_lowercase for c in text) else 0
    pool += 26 if any(c in string.ascii_uppercase for c in text) else 0
    pool += 10 if any(c.isdigit() for c in text) else 0
    pool += 33 if any(not c.isalnum() or ord(c) > 127 for c in text) else 0
    pool = max(pool, 10)
    unique = len(set(text))
    effective = unique + (len(text) - unique) * 0.3          # repetir caracteres casi no suma
    return effective * math.log2(pool)


def _hint(text: str) -> str:
    if len(text) < 12:
        return N_("Hazla más larga: cada carácter extra la protege mucho más.")
    classes = sum((any(c.islower() for c in text), any(c.isupper() for c in text),
                   any(c.isdigit() for c in text), any(not c.isalnum() for c in text)))
    if classes < 3:
        return N_("Mezcla mayúsculas, números o símbolos.")
    if len(set(text)) < len(text) * 0.6:
        return N_("Evita repetir los mismos caracteres.")
    return N_("Una frase larga y fácil de recordar también funciona muy bien.")


def assess(password: str) -> Strength:
    """Nivel de proteccion de 0 (muy debil) a 4 (muy fuerte) y un consejo."""
    if not password:
        return Strength(0, "")
    password = password[:128]
    lowered = password.lower()
    if lowered in _COMMON or lowered.rstrip(string.digits) in _COMMON or len(set(password)) == 1:
        return Strength(0, N_("Es una contraseña muy habitual: cualquiera la probaría primero."))
    if _runs_of_keys(password):
        return Strength(0, N_("Evita teclas seguidas o secuencias como abcd o 1234."))
    password = _core(password)
    bits = _bits(password)
    if len(password) < 8:
        level = 0
    elif bits < 36:
        level = 1
    elif bits < 52:
        level = 2
    elif bits < 70:
        level = 3
    else:
        level = 4
    if password.isdigit():
        level = min(level, 1)                                 # solo numeros: pocas combinaciones aunque sea larga
    return Strength(level, _hint(password) if level < 4 else "")
