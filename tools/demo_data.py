"""Genera extractos de demostracion 100 % inventados (para capturas y pruebas manuales).

Uso:  python tools/demo_data.py carpeta_destino
Crea: imagin.csv, myinvestor_operaciones.csv y myinvestor_cartera.csv
La logica vive en services/demo_data.py (la app la usa para el modo "datos de ejemplo").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.demo_data import build  # noqa: E402,F401  (se reexporta para las capturas)

if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "demo")
    print(f"Datos de demostracion en {folder} (fecha de cartera sugerida: {build(folder)})")
