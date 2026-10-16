"""Retardo tras varios intentos fallidos de contrasena. Puro (el reloj se puede inyectar para probarlo).

Los dos primeros fallos no cuestan nada (un despiste es normal); a partir del tercero hay que esperar y la espera crece:
5, 10, 20 y, como maximo, 30 segundos. Un acierto lo reinicia todo.
"""
from __future__ import annotations

import time
from collections.abc import Callable

FREE_ATTEMPTS = 2
FIRST_DELAY = 5.0
MAX_DELAY = 30.0


def delay_after(failures: int) -> float:
    """Segundos de espera tras `failures` fallos seguidos."""
    if failures <= FREE_ATTEMPTS:
        return 0.0
    return min(MAX_DELAY, FIRST_DELAY * 2 ** (failures - FREE_ATTEMPTS - 1))


class AttemptThrottle:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.failures = 0
        self._until = 0.0

    def failed(self) -> float:
        """Anota un fallo y devuelve los segundos que hay que esperar ahora."""
        self.failures += 1
        wait = delay_after(self.failures)
        self._until = self._clock() + wait
        return wait

    def succeeded(self) -> None:
        self.failures = 0
        self._until = 0.0

    def wait_left(self) -> float:
        return max(0.0, self._until - self._clock())
