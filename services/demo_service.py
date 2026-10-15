"""Datos de ejemplo: para explorar Kreix sin importar nada. Todo inventado (services/demo_data.py)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from services.demo_data import build
from services.import_service import ImportReport, ImportService


class DemoService:
    def __init__(self, importer: ImportService) -> None:
        self._importer = importer

    def load(self) -> ImportReport:
        """Genera los extractos de ejemplo y los importa como si fueran los de un usuario."""
        folder = Path(tempfile.mkdtemp(prefix="kreix-demo-"))
        try:
            as_of = build(folder)
            return self._importer.import_files(sorted(folder.glob("*.csv")), portfolio_as_of=as_of)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
