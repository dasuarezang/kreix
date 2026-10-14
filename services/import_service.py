"""Caso de uso: importar extractos (detectar, parsear, guardar sin duplicados, cuadrar)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.entities import FileKind
from core.enums import AccountKind, Bank
from data.database import session_scope
from data.repositories import (
    InsertStats,
    get_or_create_account,
    insert_operations,
    insert_transactions,
    upsert_valuations,
)
from etl.common import ParseError
from etl.dispatcher import parse_file
from etl.reconcile import reconcile_portfolio
from services.mappers import load_operations, load_snapshots

KIND_LABELS = {
    FileKind.IMAGIN_STATEMENT: "Extracto de Imagin",
    FileKind.MYINVESTOR_OPERATIONS: "Operaciones de MyInvestor",
    FileKind.MYINVESTOR_PORTFOLIO: "Cartera de MyInvestor",
}
ACCOUNT_NAMES = {Bank.IMAGIN: "Imagin", Bank.MYINVESTOR: "MyInvestor"}


@dataclass(slots=True)
class FileReport:
    file_name: str
    kind: FileKind | None = None
    inserted: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind] if self.kind else "Formato no reconocido"


@dataclass(slots=True)
class ImportReport:
    files: list[FileReport] = field(default_factory=list)
    reconciliation_warnings: list[str] = field(default_factory=list)

    @property
    def total_inserted(self) -> int:
        return sum(f.inserted for f in self.files)


class ImportService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def import_files(self, paths: Iterable[str | Path], portfolio_as_of: date | None = None) -> ImportReport:
        report = ImportReport()
        for path in map(Path, paths):
            report.files.append(self._import_one(path, portfolio_as_of))
        report.reconciliation_warnings = self.reconciliation_warnings()
        return report

    def _import_one(self, path: Path, portfolio_as_of: date | None) -> FileReport:
        try:
            parsed = parse_file(path, portfolio_as_of)
        except (ParseError, OSError, ValueError) as exc:
            return FileReport(path.name, error=str(exc))
        stats = InsertStats()
        with session_scope(self._factory) as s:  # un fichero = una transaccion
            if parsed.kind is FileKind.IMAGIN_STATEMENT:
                acc = get_or_create_account(s, Bank.IMAGIN, AccountKind.CHECKING, ACCOUNT_NAMES[Bank.IMAGIN])
                stats = insert_transactions(s, acc.id, parsed.transactions)
            elif parsed.kind is FileKind.MYINVESTOR_OPERATIONS:
                acc = get_or_create_account(
                    s, Bank.MYINVESTOR, AccountKind.INVESTMENT, ACCOUNT_NAMES[Bank.MYINVESTOR]
                )
                stats = insert_operations(s, acc.id, parsed.operations)
            else:
                stats = InsertStats(inserted=upsert_valuations(s, parsed.positions))
        return FileReport(path.name, parsed.kind, stats.inserted, stats.skipped, list(parsed.warnings))

    def reconciliation_warnings(self) -> list[str]:
        with session_scope(self._factory) as s:
            ops, snaps = load_operations(s), load_snapshots(s)
        latest = metrics.latest_positions(snaps)
        return reconcile_portfolio(latest, ops) if latest else []
