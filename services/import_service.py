"""Caso de uso: importar extractos (detectar, parsear, guardar sin duplicados, cuadrar)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core import metrics
from core.entities import FileKind, ParseResult
from core.enums import AccountKind, Bank
from data.database import session_scope
from data.hashing import scoped_hash
from data.models import Investment, InvestmentOperation, PricePoint, Transaction, Valuation
from data.repositories import (
    InsertStats,
    get_or_create_account,
    list_accounts,
    list_rules,
    recategorize,
    save_price_points,
    insert_operations,
    insert_transactions,
    upsert_valuations,
)
from etl.common import ParseError
from etl.dispatcher import parse_file
from etl.reconcile import reconcile_portfolio
from services.import_errors import describe
from services.mappers import load_operations, load_snapshots
from core.i18n import tr, N_

KIND_LABELS = {
    FileKind.IMAGIN_STATEMENT: N_("Extracto de Imagin"),
    FileKind.MYINVESTOR_OPERATIONS: N_("Operaciones de MyInvestor"),
    FileKind.MYINVESTOR_PORTFOLIO: N_("Cartera de MyInvestor"),
    FileKind.PRICE_HISTORY: N_("Histórico de precios"),
}
ACCOUNT_NAMES = {Bank.IMAGIN: "Imagin", Bank.MYINVESTOR: "MyInvestor"}


@dataclass(slots=True)
class FileReport:
    file_name: str
    kind: FileKind | None = None
    inserted: int = 0
    skipped: int = 0
    updated: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def explanation(self) -> str:
        """El error con palabras claras y que hacer para arreglarlo."""
        return describe(self.error or "")

    @property
    def kind_label(self) -> str:
        return tr(KIND_LABELS[self.kind]) if self.kind else tr("Formato no reconocido")


@dataclass(slots=True)
class FilePreview:
    """Lo que se ha leido de un archivo y lo que pasaria al importarlo (no se guarda nada)."""

    file_name: str
    kind: FileKind | None = None
    rows: int = 0
    first: date | None = None
    last: date | None = None
    new: int = 0                    # filas que se anadirian
    existing: int = 0               # ya importadas: se ignoran
    updated: int = 0                # valoraciones de cartera que cambian
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def kind_label(self) -> str:
        return tr(KIND_LABELS[self.kind]) if self.kind else tr("Formato no reconocido")

    @property
    def changes_data(self) -> bool:
        return self.ok and (self.new + self.updated) > 0

    @property
    def explanation(self) -> str:
        return describe(self.error or "")


@dataclass(slots=True)
class ImportReport:
    files: list[FileReport] = field(default_factory=list)
    reconciliation_warnings: list[str] = field(default_factory=list)

    @property
    def total_inserted(self) -> int:
        return sum(f.inserted for f in self.files)

    @property
    def total_changed(self) -> int:
        return sum(f.inserted + f.updated for f in self.files)


class ImportService:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory
        self._parsed: dict[tuple, ParseResult] = {}            # lo ultimo leido: la vista previa y la importacion no leen dos veces

    def _parse(self, path: Path, portfolio_as_of: date | None, fund_isin: str | None) -> ParseResult:
        """Lee un archivo; si es el mismo (misma ruta, tamano y fecha de modificacion) que se acaba de leer, reutiliza el resultado."""
        try:
            stat = path.stat()
            key = (str(path), stat.st_size, stat.st_mtime_ns, portfolio_as_of, fund_isin)
        except OSError:
            return parse_file(path, portfolio_as_of, fund_isin)
        found = self._parsed.get(key)
        if found is None:
            found = parse_file(path, portfolio_as_of, fund_isin)       # los errores no se guardan: se vuelven a intentar
            self._parsed[key] = found
            while len(self._parsed) > 4:
                self._parsed.pop(next(iter(self._parsed)))
        return found

    def funds(self) -> list[tuple[str, str]]:
        """(ISIN, nombre) de los fondos que ya conoce Kreix: a cual pertenece un historico de precios sin ISIN."""
        with session_scope(self._factory) as s:
            return [(i.isin, i.name) for i in s.scalars(select(Investment).order_by(Investment.name))]

    def import_files(
        self, paths: Iterable[str | Path], portfolio_as_of: date | None = None, account_id: int | None = None,
        fund_isin: str | None = None,
    ) -> ImportReport:
        """`account_id` es la cuenta destino de los extractos de Imagin; si se omite, la primera
        cuenta (o una llamada 'Imagin' si aun no hay ninguna)."""
        report = ImportReport()
        for path in map(Path, paths):
            report.files.append(self._import_one(path, portfolio_as_of, account_id, fund_isin))
        report.reconciliation_warnings = self.reconciliation_warnings()
        self._parsed.clear()                      # ya importado: no se guarda en memoria lo leido
        return report

    def preview(
        self, paths: Iterable[str | Path], portfolio_as_of: date | None = None, account_id: int | None = None,
        fund_isin: str | None = None,
    ) -> list[FilePreview]:
        """Lee los archivos y cuenta que es nuevo y que ya estaba, sin guardar nada ni crear cuentas."""
        return [self._preview_one(Path(p), portfolio_as_of, account_id, fund_isin) for p in paths]

    def _preview_one(self, path: Path, portfolio_as_of: date | None, account_id: int | None,
                     fund_isin: str | None = None) -> FilePreview:
        try:
            parsed = self._parse(path, portfolio_as_of, fund_isin)
        except (ParseError, OSError, ValueError) as exc:
            return FilePreview(path.name, error=str(exc))
        out = FilePreview(path.name, parsed.kind, warnings=list(parsed.warnings))
        with session_scope(self._factory) as s:
            if parsed.kind is FileKind.IMAGIN_STATEMENT:
                existing_accounts = list_accounts(s, AccountKind.CHECKING)
                target = account_id if account_id is not None else (existing_accounts[0].id if existing_accounts else None)
                if account_id is not None and not any(a.id == account_id for a in existing_accounts):
                    return FilePreview(path.name, parsed.kind, error=tr("La cuenta de destino ya no existe."))
                hashes = {scoped_hash(target, d.tx_hash) for d in parsed.transactions} if target is not None else set()
                known = self._known(s, Transaction.tx_hash, hashes)
                out.rows = len(parsed.transactions)
                dates = [d.booking_date for d in parsed.transactions]
                unique = {scoped_hash(target, d.tx_hash) if target is not None else d.tx_hash for d in parsed.transactions}
                out.new = len(unique - known)
            elif parsed.kind is FileKind.MYINVESTOR_OPERATIONS:
                acc = next(iter(list_accounts(s, AccountKind.INVESTMENT)), None)
                hashes = {scoped_hash(acc.id, d.tx_hash) for d in parsed.operations} if acc else set()
                known = self._known(s, InvestmentOperation.tx_hash, hashes)
                out.rows = len(parsed.operations)
                dates = [d.trade_date for d in parsed.operations]
                unique = {scoped_hash(acc.id, d.tx_hash) if acc else d.tx_hash for d in parsed.operations}
                out.new = len(unique - known)
            elif parsed.kind is FileKind.PRICE_HISTORY:
                wanted = {(p.isin, p.as_of): p.unit_price for p in parsed.prices}
                out.rows = len(wanted)
                dates = [d for _, d in wanted]
                known = {(p.isin, p.as_of): p.unit_price for p in s.scalars(
                    select(PricePoint).where(PricePoint.isin.in_({i for i, _ in wanted})))}
                out.new = sum(1 for k in wanted if k not in known)
                out.updated = sum(1 for k, v in wanted.items() if k in known and known[k] != v)
                if not s.scalar(select(Investment.id).where(Investment.isin.in_({i for i, _ in wanted}))):
                    out.warnings.append(tr("Este fondo aún no está en tu cartera: los precios se guardan y se usarán cuando lo esté."))
            else:
                out.rows = len(parsed.positions)
                dates = [p.as_of for p in parsed.positions]
                for p in parsed.positions:
                    current = s.scalar(
                        select(Valuation).join(Investment, Investment.id == Valuation.investment_id)
                        .where(Investment.isin == p.isin, Valuation.as_of == p.as_of))
                    if current is None:
                        out.new += 1
                    elif (current.unit_price, current.units, current.invested) != (p.unit_price, p.units, p.invested):
                        out.updated += 1
        out.existing = out.rows - out.new - out.updated
        out.first, out.last = (min(dates), max(dates)) if dates else (None, None)
        return out

    @staticmethod
    def _known(session: Session, column, hashes: set[str]) -> set[str]:
        found: set[str] = set()
        listed = list(hashes)
        for i in range(0, len(listed), 500):                  # SQLite limita los parametros de un IN
            found.update(session.scalars(select(column).where(column.in_(listed[i:i + 500]))))
        return found

    def _import_one(self, path: Path, portfolio_as_of: date | None, account_id: int | None,
                    fund_isin: str | None = None) -> FileReport:
        try:
            parsed = self._parse(path, portfolio_as_of, fund_isin)
        except (ParseError, OSError, ValueError) as exc:
            return FileReport(path.name, error=str(exc))
        stats = InsertStats()
        with session_scope(self._factory) as s:  # un fichero = una transaccion
            if parsed.kind is FileKind.IMAGIN_STATEMENT:
                target = self._checking_account_id(s, account_id)
                if target is None:
                    return FileReport(path.name, parsed.kind, error=tr("La cuenta de destino ya no existe."))
                stats = insert_transactions(s, target, parsed.transactions)
                if list_rules(s):                       # los movimientos nuevos tambien siguen las reglas del usuario
                    recategorize(s)
            elif parsed.kind is FileKind.MYINVESTOR_OPERATIONS:
                acc = get_or_create_account(
                    s, Bank.MYINVESTOR, AccountKind.INVESTMENT, ACCOUNT_NAMES[Bank.MYINVESTOR]
                )
                stats = insert_operations(s, acc.id, parsed.operations)
            elif parsed.kind is FileKind.PRICE_HISTORY:
                new, updated = save_price_points(s, [(p.isin, p.as_of, p.unit_price) for p in parsed.prices])
                stats = InsertStats(inserted=new, updated=updated, skipped=len(parsed.prices) - new - updated)
            else:
                stats = upsert_valuations(s, parsed.positions)
        return FileReport(
            path.name, parsed.kind, stats.inserted, stats.skipped, stats.updated, list(parsed.warnings)
        )

    @staticmethod
    def _checking_account_id(session: Session, account_id: int | None) -> int | None:
        existing = list_accounts(session, AccountKind.CHECKING)
        if account_id is not None:
            return account_id if any(a.id == account_id for a in existing) else None
        if existing:
            return existing[0].id
        return get_or_create_account(session, Bank.IMAGIN, AccountKind.CHECKING, ACCOUNT_NAMES[Bank.IMAGIN]).id

    def reconciliation_warnings(self) -> list[str]:
        with session_scope(self._factory) as s:
            ops, snaps = load_operations(s), load_snapshots(s)
        latest = metrics.latest_positions(snaps)
        return reconcile_portfolio(latest, ops) if latest else []
