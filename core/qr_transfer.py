"""Pasar los datos del ordenador al movil con un codigo QR animado, sin red ni servidores. Sin Qt.

Un QR solo guarda un par de KB, asi que el ordenador ensena una secuencia de codigos y el movil los lee con la camara.
Lo que viaja es la exportacion `.kreix` cifrada con la contrasena maestra (el movil la pide al terminar): quien grabe la
pantalla no puede leer nada sin ella.

Codigo fuente ("fountain code"): da igual que fotogramas se pierdan o en que momento empiece a mirar el movil. Los datos se
cortan en K bloques; los fotogramas pares llevan un bloque tal cual (en orden, dando vueltas) y los impares, la suma XOR de
unos pocos bloques elegidos al azar con una semilla que sale del propio fotograma. Con cualquier conjunto suficiente de
fotogramas, el movil despeja los bloques que le faltan (decodificacion por "pelado"). El reparto y el generador aleatorio
son los mismos aqui y en `pwa/web/js/qr.js`.

Fotograma (bytes del QR, modo binario):
    b"KX" | version (1) | id de la transferencia (4) | longitud total (4) | tamano de bloque (2) | numero (4) | bloque
"""
from __future__ import annotations

import os
import struct
import zlib
from collections.abc import Iterator

MAGIC = b"KX"
VERSION = 1
HEADER = struct.Struct(">2sBIIHI")
PACK_MAGIC = b"KXQ1"
BLOCK_SIZE = 600                 # bytes por QR: cabe en un codigo de version ~17 con correccion L, que una camara lee bien
DEGREES = (0.10, 0.60, 0.77, 0.85, 0.90, 0.94, 0.97, 1.00)    # probabilidad acumulada de sumar 1, 2, ... 8 bloques
_M = 0xFFFFFFFF


def pack(kreix: bytes) -> bytes:
    """El .kreix comprimido (el cifrado va en base64, que comprime bien: viajan menos fotogramas)."""
    return PACK_MAGIC + zlib.compress(kreix, 9)


def unpack(data: bytes) -> bytes:
    if not data.startswith(PACK_MAGIC):
        raise ValueError("not a Kreix transfer")
    try:
        return zlib.decompress(data[len(PACK_MAGIC):])
    except zlib.error as exc:
        raise ValueError("damaged transfer") from exc


def mulberry32(seed: int):
    """Generador pseudoaleatorio de 32 bits (el mismo que en JS, bit a bit)."""
    state = seed & _M

    def next_value() -> int:
        nonlocal state
        state = (state + 0x6D2B79F5) & _M
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & _M
        t = ((t + (((t ^ (t >> 7)) * (t | 61)) & _M)) & _M) ^ t
        return (t ^ (t >> 14)) & _M

    return next_value


def block_count(total: int, block_size: int = BLOCK_SIZE) -> int:
    return max(1, -(-total // block_size))


def indices(transfer_id: int, seq: int, k: int) -> list[int]:
    """Que bloques lleva el fotograma `seq`: uno en orden (pares) o varios al azar sumados con XOR (impares)."""
    if seq % 2 == 0:
        return [(seq // 2) % k]
    rng = mulberry32(transfer_id ^ ((seq * 2654435761) & _M))
    roll = rng() / 2 ** 32
    degree = next(i + 1 for i, edge in enumerate(DEGREES) if roll < edge)
    degree = min(degree, k)
    chosen: list[int] = []
    while len(chosen) < degree:
        value = rng() % k
        if value not in chosen:
            chosen.append(value)
    return sorted(chosen)


def _xor(a: bytes, b: bytes) -> bytes:
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big")


class Encoder:
    """Los fotogramas de una transferencia. `frame(seq)` sirve para cualquier numero: la secuencia no se acaba."""

    def __init__(self, data: bytes, block_size: int = BLOCK_SIZE, transfer_id: int | None = None) -> None:
        self.data = data
        self.block_size = block_size
        self.transfer_id = int.from_bytes(os.urandom(4), "big") if transfer_id is None else transfer_id & _M
        self.k = block_count(len(data), block_size)
        padded = data.ljust(self.k * block_size, b"\0")
        self.blocks = [padded[i * block_size:(i + 1) * block_size] for i in range(self.k)]

    def frame(self, seq: int) -> bytes:
        chosen = indices(self.transfer_id, seq, self.k)
        payload = self.blocks[chosen[0]]
        for i in chosen[1:]:
            payload = _xor(payload, self.blocks[i])
        return HEADER.pack(MAGIC, VERSION, self.transfer_id, len(self.data), self.block_size, seq & _M) + payload

    def frames(self, start: int = 0) -> Iterator[bytes]:
        seq = start
        while True:
            yield self.frame(seq)
            seq += 1


class Decoder:
    """Junta fotogramas hasta tener todos los bloques (la version de JS hace lo mismo en el movil)."""

    def __init__(self) -> None:
        self.transfer_id: int | None = None
        self.total = self.block_size = self.k = 0
        self.known: dict[int, bytes] = {}
        self._pending: list[tuple[set[int], bytes]] = []
        self._seen: set[int] = set()

    @property
    def done(self) -> bool:
        return self.k > 0 and len(self.known) == self.k

    @property
    def progress(self) -> float:
        return len(self.known) / self.k if self.k else 0.0

    def add(self, frame: bytes) -> bool:
        """Anade un fotograma; True si era de esta transferencia. Un fotograma de otra transferencia empieza de cero."""
        if len(frame) < HEADER.size:
            return False
        magic, version, transfer_id, total, block_size, seq = HEADER.unpack_from(frame)
        if magic != MAGIC or version != VERSION or len(frame) != HEADER.size + block_size:
            return False
        if transfer_id != self.transfer_id:
            self.__init__()
            self.transfer_id, self.total, self.block_size = transfer_id, total, block_size
            self.k = block_count(total, block_size)
        if seq in self._seen or self.done:
            return True
        self._seen.add(seq)
        self._absorb(set(indices(transfer_id, seq, self.k)), frame[HEADER.size:])
        return True

    def _absorb(self, chosen: set[int], payload: bytes) -> None:
        queue = [(chosen, payload)]
        while queue:
            chosen, payload = queue.pop()
            for i in [i for i in chosen if i in self.known]:
                payload = _xor(payload, self.known[i])
                chosen.discard(i)
            if not chosen:
                continue
            if len(chosen) > 1:
                self._pending.append((chosen, payload))
                continue
            (index,) = chosen
            self.known[index] = payload
            still = []                                 # el bloque nuevo puede despejar otros que esperaban
            for item in self._pending:
                (queue if index in item[0] else still).append(item)
            self._pending = still

    def result(self) -> bytes:
        if not self.done:
            raise ValueError("transfer incomplete")
        return b"".join(self.known[i] for i in range(self.k))[:self.total]
