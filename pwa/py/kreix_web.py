"""Puente entre la app movil (HTML/JS) y la logica de Kreix, que corre tal cual en Pyodide.

La interfaz del movil no calcula ni formatea nada: llama a estas funciones y recibe JSON con los textos ya traducidos y
formateados (con `ui.format` y `ui.headlines`, los mismos del escritorio), asi el movil dice exactamente lo mismo que el PC.
Cada funcion publica replica lo que hace la vista equivalente de `ui/` al pintarse.

El almacen cifrado es el mismo `.krx` del escritorio: vive en el sistema de archivos virtual (`/data`) y el worker de JS lo
copia a IndexedDB cada vez que se guarda.
"""
from __future__ import annotations

import json
import traceback
from dataclasses import asdict, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from core import i18n
from core.greeting import greeting
from core.i18n import tr, trn
from data.vault import MIN_PASSWORD, CorruptVaultError, WrongPasswordError

import qt_texts          # constantes de texto de los modulos de Qt, extraidas al construir (tools/build_pwa.py)

DATA = Path("/data")
VAULT = DATA / "kreix.krx"

_store = None            # SecureStore abierto
_svc: SimpleNamespace | None = None
_settings = None         # AppSettings vigentes
_state: dict[str, str] = {}
_undo: Path | None = None


# ----------------------------------------------------------------------------- utilidades
def _num(value) -> float | None:
    return None if value is None else float(value)


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def call(name: str, args_json: str = "{}") -> str:
    """Punto de entrada unico desde JS: ejecuta `name(**args)` y devuelve {"ok": ...} o {"error": ...} en JSON."""
    try:
        fn = _PUBLIC[name]
        result = fn(**json.loads(args_json or "{}"))
        return json.dumps({"ok": result, "dirty": bool(_store is not None and _store.dirty)}, default=str)
    except Exception as exc:                                # noqa: BLE001 - el error se ensena en la interfaz
        return json.dumps({"error": str(exc) or exc.__class__.__name__, "trace": traceback.format_exc()})


def flush() -> bool:
    """Guarda cifrado en /data si hubo cambios (el worker lo copia despues a IndexedDB)."""
    return bool(_store is not None and _store.flush())


# ----------------------------------------------------------------------------- arranque y bloqueo
def boot(language: str = "es") -> dict:
    """Estado inicial, antes de pedir la contrasena: si ya hay datos cifrados y el idioma de la pantalla de bloqueo."""
    i18n.set_language(language)
    return {"exists": VAULT.is_file(), "min_password": MIN_PASSWORD, "texts": lock_texts()}


def lock_texts() -> dict:
    return {
        "create_title": tr("Crea tu contraseña maestra"),
        "unlock_title": tr("Kreix está bloqueado"),
        "create_body": tr("Cifraremos todos tus datos con ella. Solo tú podrás abrirlos y no hay forma de recuperarla: si la olvidas, los datos no se pueden recuperar."),
        "unlock_body": tr("Tus datos están cifrados en este equipo. Escribe la contraseña maestra para abrirlos."),
        "password": tr("Contraseña maestra"),
        "confirm": tr("Repite la contraseña"),
        "create": tr("Crear y abrir"),
        "unlock": tr("Desbloquear"),
        "opening": tr("Abriendo Kreix…"),
        "forgot": tr("He olvidado la contraseña"),
        "footer": tr("Todo se queda en este equipo, cifrado. Kreix no envía nada a ningún servidor."),
        "too_short": tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD),
        "mismatch": tr("Las contraseñas no coinciden."),
        "empty": tr("Escribe la contraseña maestra."),
        "reset_title": tr("Borrar todos los datos"),
        "reset_body": tr("Sin la contraseña maestra no hay forma de recuperar tus datos. Si sigues, se borrarán para siempre "
                         "los movimientos, cuentas e inversiones guardados y podrás empezar de cero con una contraseña nueva "
                         "e importar de nuevo tus extractos. ¿Quieres borrarlos?"),
    }


def password_strength(password: str) -> dict:
    """Lo que ensena `ui.widgets.strength_meter` bajo el campo de la contrasena."""
    from core.password_strength import assess

    result = assess(password)
    return {"level": result.level, "filled": 0 if not password else max(1, result.level),
            "word": tr("Seguridad: {level}").format(level=tr(result.label)) if password else tr("Seguridad de la contraseña"),
            "hint": tr(result.hint) if result.hint else ""}


def create(password: str) -> dict:
    from data.secure_store import SecureStore

    if len(password) < MIN_PASSWORD:
        return {"error": tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD)}
    store = SecureStore.create(VAULT, password)
    SecureStore.open(VAULT, password)                       # se comprueba que el archivo cifrado se abre
    _open(store)
    return {"ready": True}


def unlock(password: str) -> dict:
    from data.secure_store import SecureStore

    if _store is not None:                                  # bloqueo automatico: la base sigue en memoria
        return {"ready": True} if _store.verify_password(password) else {"error": tr("Contraseña incorrecta. Inténtalo de nuevo.")}
    try:
        store = SecureStore.open(VAULT, password)
    except WrongPasswordError:
        return {"error": tr("Contraseña incorrecta. Inténtalo de nuevo.")}
    except CorruptVaultError:
        return {"error": tr("Este archivo de datos no es válido o está dañado.")}
    _open(store)
    return {"ready": True}


def reset() -> dict:
    """"He olvidado la contrasena": se borra todo y se empieza de cero."""
    global _store, _svc
    from data.secure_store import erase_vault

    _store = _svc = None
    erase_vault(VAULT)
    return {"exists": False}


def _open(store) -> None:
    global _store, _svc, _settings, _state
    from data.database import make_session_factory
    from services.accounts_service import AccountsService
    from services.category_service import CategoryService
    from services.dashboard_service import DashboardService
    from services.data_service import DataService
    from services.demo_service import DemoService
    from services.goals_service import GoalsService
    from services.import_service import ImportService
    from services.investment_service import InvestmentService
    from services.settings_service import SettingsService
    from services.transfer_service import TransferService
    from ui import format as formatting

    factory = make_session_factory(store.engine)
    importer = ImportService(factory)
    _store = store
    _svc = SimpleNamespace(
        importer=importer, dashboard=DashboardService(factory), settings=SettingsService(factory), data=DataService(factory),
        accounts=AccountsService(factory), investment=InvestmentService(factory), transfer=TransferService(store.engine, factory),
        category=CategoryService(factory), demo=DemoService(importer), goals=GoalsService(factory),
    )
    _settings = _svc.settings.load()
    _state = _svc.settings.load_state()
    i18n.set_language(_settings.language)
    formatting.set_private(_settings.privacy_mode)


# ----------------------------------------------------------------------------- ajustes y estado de la app
def app_state() -> dict:
    """Lo que la interfaz necesita para montarse: ajustes, si toca la bienvenida y si hay datos de ejemplo."""
    s = _settings
    demo = _state.get("demo") == "1" and not _svc.transfer.summary().is_empty
    return {
        "settings": asdict(s),
        "needs_welcome": not s.name_asked,
        "demo": demo,
        "setup_hidden": _state.get("setup_hidden") == "1",
        "is_empty": _svc.transfer.summary().is_empty,
        "languages": [{"code": c, "name": i18n.NAMES[c]} for c in i18n.LANGUAGES],
    }


def save_settings(**changes) -> dict:
    global _settings
    from ui import format as formatting

    _settings = replace(_settings, **changes)
    _svc.settings.save(_settings)
    i18n.set_language(_settings.language)
    formatting.set_private(_settings.privacy_mode)
    return app_state()


def welcome_texts(language: str) -> dict:
    """La bienvenida de la primera vez, en el idioma que se este eligiendo (cambia al instante, como en el escritorio)."""
    previous = i18n.language()
    i18n.set_language(language)
    try:
        return {
            "title": tr("Bienvenido a Kreix"),
            "intro": tr("Tres preguntas rápidas para dejarlo a tu medida. Todo se queda en tu ordenador, viaja con tus datos "
                        "cuando los exportas y puedes cambiarlo cuando quieras en Ajustes."),
            "ask_language": tr("¿En qué idioma quieres Kreix?"),
            "ask_name": tr("¿Cómo te llamas?"),
            "name_placeholder": tr("Tu nombre (Kreix te saludará con él)"),
            "ask_interest": tr("¿Qué quieres gestionar?"),
            "ok": tr("Empezar"),
            "cancel": tr("Ahora no"),
            "accounts_title": tr(qt_texts.ACCOUNTS_TITLE), "accounts_text": tr(qt_texts.ACCOUNTS_TEXT),
            "investments_title": tr(qt_texts.INVESTMENTS_TITLE), "investments_text": tr(qt_texts.INVESTMENTS_TEXT),
            "at_least_one": tr(qt_texts.AT_LEAST_ONE),
        }
    finally:
        i18n.set_language(previous)


def finish_welcome(accepted: bool, name: str = "", language: str = "es", accounts: bool = True, investments: bool = True) -> dict:
    from core.greeting import clean_name

    changes = {"name_asked": True, "language": language}
    if accepted:
        changes.update(user_name=clean_name(name), interest_accounts=accounts or not investments, interest_investments=investments)
    return save_settings(**changes)


def ui_texts(keys: list[str]) -> dict:
    """Traduce los textos fijos de la interfaz (los que no dependen de datos)."""
    return {k: tr(k) for k in keys}


def catalog() -> dict:
    """El catalogo entero del idioma activo (clave en castellano -> traduccion), para los textos fijos de la interfaz."""
    return {**i18n.catalog(i18n.language()), **MOBILE.get(i18n.language(), {})}


# ----------------------------------------------------------------------------- deshacer
def _snapshot() -> None:
    global _undo
    _discard_undo()
    try:
        _undo = _svc.transfer.snapshot()
    except Exception:                                       # noqa: BLE001 - deshacer es un extra
        _undo = None


def _discard_undo() -> None:
    global _undo
    if _undo is not None:
        for suffix in ("", "-wal", "-shm"):
            try:
                Path(str(_undo) + suffix).unlink()
            except OSError:
                pass
    _undo = None


def undo() -> dict:
    global _undo, _settings, _state
    snapshot, _undo = _undo, None
    if snapshot is None:
        return {"message": ""}
    try:
        _svc.transfer.restore_snapshot(snapshot)
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                Path(str(snapshot) + suffix).unlink()
            except OSError:
                pass
    _settings = _svc.settings.load()
    _state = _svc.settings.load_state()
    return {"message": tr("Cambio deshecho")}


def _told(message: str, undoable: bool = False) -> dict:
    if not undoable:
        _discard_undo()
    return {"message": message, "undoable": undoable and _undo is not None}


# ----------------------------------------------------------------------------- datos de ejemplo y primeros pasos
def start_demo() -> dict:
    global _state
    if not _svc.transfer.summary().is_empty:
        return {"message": ""}
    _svc.demo.load()
    _svc.settings.save_state(demo=1)
    _state = _svc.settings.load_state()
    return _told(tr("Datos de ejemplo cargados. Explora con calma: se quitan con «Empezar con mis datos»."))


def end_demo() -> dict:
    global _state
    _snapshot()
    _svc.data.reset_all()
    _svc.settings.clear_state("demo")
    _state = _svc.settings.load_state()
    return _told(tr("Datos de ejemplo eliminados. Importa tus extractos para empezar."), undoable=True)


def hide_setup() -> dict:
    global _state
    _svc.settings.save_state(setup_hidden=1)
    _state = _svc.settings.load_state()
    return _told(tr("Lista de primeros pasos oculta."))


# ----------------------------------------------------------------------------- reloj de Inicio
def clock(now: str) -> dict:
    """Saludo y fecha larga para la hora del movil (`now` en ISO, hora local)."""
    from ui.format import fmt_datetime_long

    moment = datetime.fromisoformat(now)
    day = 6 <= moment.hour < 21
    return {"greeting": greeting(moment, _settings.user_name if _settings else ""), "date": fmt_datetime_long(moment),
            "hour": moment.hour + moment.minute / 60,
            "sky": tr("Es de día: sol, con Blitzen y Black") if day else tr("Es de noche: luna, con Blitzen y Black durmiendo")}


# ----------------------------------------------------------------------------- Inicio
def inicio(today: str | None = None) -> dict:
    """Lo mismo que pinta `ui.views.dashboard_view.DashboardView._render`, como datos."""
    from core.metrics import WealthPoint
    from ui.format import category_label, fmt_date, fmt_eur, fmt_pct
    from ui.headlines import allocation_headline, flow_headline, wealth_headline

    d = _svc.dashboard.load(_settings.flow_options)
    accounts, investments = _settings.interest_accounts, _settings.interest_investments
    out: dict = {"has_data": d.has_data, "interests": {"accounts": accounts, "investments": investments}}
    if not d.has_data:
        out["onboarding"] = onboarding_texts()
        return out
    zero = Decimal(0)

    # lo que se muestra segun lo que interesa (los datos no cambian: lo que no interesa deja de contar)
    cash = (d.cash or zero) if accounts else zero
    invested = d.portfolio_value if investments else zero
    points = [WealthPoint(w.date, w.cash if accounts else zero, w.invested_value if investments else zero,
                          w.contributions if investments else zero,
                          (w.cash if accounts else zero) + (w.invested_value if investments else zero)) for w in d.wealth]
    flows = [f if investments else replace(f, contributions=zero) for f in d.flows]
    change = points[-1].net_worth - points[-2].net_worth if len(points) >= 2 else None
    net_worth = cash + invested

    reliable = not d.warnings and d.xirr is not None and d.twr is not None
    chips: list[dict] = []
    if d.simple_return is not None:
        chips.append({"text": tr("{signed} rendimiento").format(signed=fmt_pct(d.simple_return, 2, signed=True)),
                      "tone": "negative" if d.simple_return < 0 else "positive"})
    if reliable:
        chips.append({"text": tr("TIR {xirr} anual").format(xirr=fmt_pct(d.xirr)), "tone": ""})
    if not investments:
        chips = []
    if change is not None and change != 0:
        chips.insert(0, {"text": tr("{amount} frente al mes pasado").format(amount=signed_eur(change)),
                         "tone": "negative" if change < 0 else "positive"})
    total = float(net_worth) or 1.0
    parts = [
        {"label": tr("Liquidez"), "value": f"{fmt_eur(cash)}  ·  {fmt_pct(float(cash) / total)}", "share": max(float(cash), 0) / total, "tone": "neutral", "keep": accounts},
        {"label": tr("Inversión"), "value": f"{fmt_eur(invested)}  ·  {fmt_pct(float(invested) / total)}", "share": float(invested) / total, "tone": "accent", "keep": investments},
    ]
    out["subtitle"] = tr("Fecha de última actualización de datos: {date}").format(date=fmt_date(d.last_update)) if d.last_update else ""
    out["net"] = {
        "title": tr("Patrimonio neto"), "help": "Patrimonio neto", "value": fmt_eur(net_worth),
        "caption": {(True, True): tr("Todo lo que tienes: cuentas más inversiones"), (True, False): tr("Lo que tienes en tus cuentas"),
                    (False, True): tr("Lo que tienes invertido")}[(accounts, investments)],
        "chips": chips, "trend": [float(w.net_worth) for w in points], "split": [p for p in parts if p["keep"]],
    }

    if d.simple_return is None:
        ret = {"value": "—", "sub": tr("Importa el extracto de cartera de MyInvestor"), "tone": ""}
    else:
        sub = tr("TIR {xirr} anual  ·  TWR {twr}").format(xirr=fmt_pct(d.xirr), twr=fmt_pct(d.twr)) if reliable else tr("Sobre el capital invertido")
        ret = {"value": fmt_pct(d.simple_return, 2, signed=True), "sub": sub, "tone": _tone(d.simple_return)}
    out["return"] = {"title": tr("Rendimiento global"), "help": "Rentabilidad global", "visible": investments, **ret}

    if d.month_savings_rate is None:
        sav = {"value": "—", "sub": tr("Este mes aún no hay ingresos registrados"), "tone": ""}
    else:
        sav = {"value": fmt_pct(d.month_savings_rate, 0), "tone": _tone(d.month_savings_rate),
               "sub": tr("Ingresos {month_income}  ·  Gastos {month_expenses}").format(month_income=fmt_eur(d.month_income), month_expenses=fmt_eur(d.month_expenses))}
    out["savings"] = {"title": tr("Tasa de ahorro del mes"), "help": "Tasa de ahorro", "visible": accounts, **sav}

    f = d.forecast
    out["forecast"] = None
    if f and accounts:
        parts_f = [tr("Pagos fijos que quedan: {fixed}").format(fixed=fmt_eur(f.fixed_due))] if f.fixed_due else [tr("Sin pagos fijos pendientes")]
        if f.income_due:
            parts_f.append(tr("ingresos fijos: {income}").format(income=fmt_eur(f.income_due)))
        if f.reliable_variable:
            parts_f.append(tr("gasto diario habitual: {daily}").format(daily=fmt_eur(f.daily_spend)))
        out["forecast"] = {"title": tr("Previsión a fin de mes"), "help": "Previsión a fin de mes", "value": fmt_eur(f.projected),
                           "sub": "  ·  ".join(parts_f) + "  ·  " + tr("con datos hasta el {date}").format(date=fmt_date(f.as_of)),
                           "tone": "negative" if f.projected < 0 else ""}

    out["banner"] = None
    if d.warnings:
        extra = len(d.warnings) - 1
        more = trn(" Hay {extra} aviso más en Importar.", " Hay {extra} avisos más en Importar.", extra).format(extra=extra) if extra else ""
        out["banner"] = {"html": tr("<b>La cartera no cuadra con las operaciones importadas.</b> {warnings}{more} La TIR y el TWR no se muestran hasta que cuadre.").format(warnings=_esc(d.warnings[0]), more=more),
                         "button": tr("Ir a Importar")}

    steps = []
    if accounts:
        steps.append({"text": tr("Importa el extracto de tu cuenta"), "done": d.has_transactions, "target": "import"})
    if investments:
        steps += [{"text": tr("Importa tus operaciones de MyInvestor"), "done": d.has_operations, "target": "import"},
                  {"text": tr("Importa la cartera de MyInvestor"), "done": d.has_portfolio, "target": "import"}]
    if accounts:
        steps.append({"text": tr("Define un presupuesto mensual en Cuentas"), "done": d.has_budgets, "target": "accounts"})
    done = sum(1 for s in steps if s["done"])
    out["setup"] = None
    if _state.get("setup_hidden") != "1" and done < len(steps):
        out["setup"] = {"title": tr("Primeros pasos"), "caption": tr("Lo que te falta para tener Kreix al completo"),
                        "subtitle": tr("{done_count} de {steps} hechos").format(done_count=done, steps=len(steps)),
                        "steps": steps, "go": tr("Hacerlo"), "hide": tr("Ocultar")}

    out["review"] = None
    if accounts and d.uncategorized_count > 0:
        out["review"] = {
            "title": tr("Por clasificar"),
            "subtitle": trn("{n} movimiento sin categoría · {total}", "{n} movimientos sin categoría · {total}", d.uncategorized_count).format(n=d.uncategorized_count, total=fmt_eur(d.uncategorized_total)),
            "button": tr("Ver los movimientos"),
            "hint": tr("Cuando un mismo comercio se repita sin categoría, te propondré una regla para clasificarlo de una vez.") if not d.suggestions else "",
            "suggestions": [_suggestion(s) for s in d.suggestions],
        }

    total_upcoming = sum((r.amount for r in d.upcoming), zero)
    out["upcoming"] = {
        "visible": accounts, "title": tr("Próximos pagos"),
        "subtitle": tr("{items} en los próximos pagos (fechas estimadas)").format(items=fmt_eur(total_upcoming)) if d.upcoming else tr("Sin pagos recurrentes a la vista"),
        "columns": [tr("PAGO"), tr("IMPORTE"), tr("FECHA")],
        "rows": [{"name": r.name, "amount": fmt_eur(r.amount), "date": fmt_date(r.next_date)} for r in d.upcoming],
        "empty": tr("Cuando Kreix detecte suscripciones o recibos mensuales, verás aquí cuándo toca el siguiente."),
        "remove": tr("Quitar de pagos recurrentes"),
    }
    out["budgets"] = _budget_carousel(d.budgets, d.has_budgets)
    out["budgets"]["visible"] = accounts
    out["goals"] = _goals(d.goals, date.fromisoformat(today) if today else date.today())
    out["goals"]["visible"] = accounts

    out["allocation"] = {"visible": accounts and investments, "title": tr("Distribución de activos"),
                         "caption": tr("Liquidez en Imagin frente a inversión en MyInvestor"),
                         "headline": allocation_headline(d.cash, d.portfolio_value, d.net_worth),
                         "total": fmt_eur(sum((s.value for s in d.allocation if s.value > 0), zero), 0),
                         "slices": [{"key": s.label, "label": tr(s.label), "value": float(s.value), "weight": float(s.weight),
                                     "text": fmt_eur(s.value), "pct": fmt_pct(s.weight)} for s in d.allocation if s.value > 0]}
    out["flow"] = {"visible": accounts, "title": tr("Flujo de caja mensual"), "caption": tr("Ingresos, gastos y aportaciones a MyInvestor"),
                   "headline": flow_headline(flows), "contributions": investments, **_flows(flows)}
    out["wealth"] = {"title": tr("Evolución patrimonial"),
                     "caption": tr("Lo aportado frente a lo que vale hoy: la diferencia es el efecto de la rentabilidad compuesta"),
                     "headline": wealth_headline(points), "value_line": accounts and investments, "contributions": investments,
                     **_wealth(points)}
    return out


def _tone(value) -> str:
    return "negative" if value < 0 else ("positive" if value > 0 else "")


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def signed_eur(value: Decimal) -> str:
    from ui.format import fmt_eur

    return ("+" if value > 0 else "") + fmt_eur(value)


def _suggestion(s) -> dict:
    from ui.format import fmt_eur

    text = trn("{n} movimiento · {total}", "{n} movimientos · {total}", s.count).format(n=s.count, total=fmt_eur(s.total))
    text += "  ·  " + tr("La regla usará «{word}»").format(word=s.keyword)
    if s.variants > 1:
        text += "  ·  " + tr("{n} conceptos parecidos").format(n=s.variants)
    return {"title": s.example, "text": text, "keyword": s.keyword, "button": tr("Crear regla…")}


def _budget_carousel(lines, has_budgets: bool) -> dict:
    from ui.format import category_label, fmt_eur, fmt_pct

    over = sum(1 for line in lines if line.state == "over")
    near = sum(1 for line in lines if line.state == "warn")
    if lines:
        parts = [trn("{n} presupuesto", "{n} presupuestos", len(lines)).format(n=len(lines))]
        if over:
            parts.append(trn("{n} superado", "{n} superados", over).format(n=over))
        if near:
            parts.append(tr("{near} cerca del tope").format(near=near))
        subtitle = "  ·  ".join(parts)
    else:
        subtitle = tr("Sin presupuestos todavía") if not has_budgets else tr("Sin gasto este mes")
    items = []
    for line in lines:
        share = float(line.spent / line.budget) if line.budget else 0.0
        items.append({
            "category": line.category.value, "label": category_label(line.category), "state": line.state,
            "state_text": tr(qt_texts.STATE_TEXT[line.state]), "spent": fmt_eur(line.spent),
            "of": tr("de {budget}").format(budget=fmt_eur(line.budget)), "pct": fmt_pct(share, 0), "share": share,
            "note": tr("Te has pasado {remaining}").format(remaining=fmt_eur(-line.remaining)) if line.state == "over"
            else tr("Te quedan {remaining} este mes").format(remaining=fmt_eur(line.remaining)),
        })
    return {"title": tr("Presupuestos del mes"), "subtitle": subtitle, "items": items,
            "counter": tr("{n} de {total}"),
            "empty": tr("Define un tope mensual por categoría en la pestaña Cuentas y aquí los verás pasar uno a uno.")
            if not has_budgets else tr("Todavía no hay gastos este mes en las categorías con presupuesto."),
            "prev": tr("Presupuesto anterior"), "next": tr("Presupuesto siguiente")}


def _goals(goals, today: date) -> dict:
    from core.goals import monthly_needed
    from ui.format import fmt_date, fmt_eur

    done = sum(1 for g in goals if g.reached)
    items = []
    for g in goals:
        if g.reached:
            note = tr("Meta alcanzada")
        else:
            parts = [tr("Faltan {amount}").format(amount=fmt_eur(g.remaining))]
            if g.deadline:
                if g.deadline < today:
                    parts.append(tr("Venció el {date}").format(date=fmt_date(g.deadline)))
                else:
                    parts.append(tr("Para el {date}").format(date=fmt_date(g.deadline)))
                    need = monthly_needed(g, today)
                    if need:
                        parts.append(tr("{amount} al mes").format(amount=fmt_eur(need)))
            note = "  ·  ".join(parts)
        items.append({"id": g.id, "name": g.name, "progress": float(g.fraction),
                      "amount": tr("{spent} de {budget}").format(spent=fmt_eur(g.saved), budget=fmt_eur(g.target)),
                      "note": note, "reached": g.reached})
    if goals:
        subtitle = trn("{n} meta", "{n} metas", len(goals)).format(n=len(goals)) + (
            "  ·  " + trn("{n} alcanzada", "{n} alcanzadas", done).format(n=done) if done else "")
    else:
        subtitle = tr("Sin metas todavía")
    return {"title": tr("Metas de ahorro"), "subtitle": subtitle, "items": items,
            "button": tr("Gestionar metas") if goals else tr("Crear una meta"),
            "empty": tr("Ponte un objetivo, por ejemplo «1.000 € para vacaciones», y ve cómo avanzas.")}


def _flows(flows) -> dict:
    from ui.format import fmt_eur, month_long, month_short

    return {"months": [month_short(f.month)[:3] for f in flows], "months_long": [month_long(f.month).capitalize() for f in flows],
            "income": [float(f.income) for f in flows], "expenses": [float(f.expenses) for f in flows],
            "contrib": [float(f.contributions) for f in flows],
            "income_text": [fmt_eur(f.income) for f in flows], "expenses_text": [fmt_eur(f.expenses) for f in flows],
            "contrib_text": [fmt_eur(f.contributions) for f in flows],
            "legend": [tr("Ingresos"), tr("Gastos"), tr("Aportaciones")]}


def _wealth(points) -> dict:
    from ui.format import fmt_date, fmt_eur, month_short

    return {"dates": [month_short(p.date) for p in points], "dates_long": [fmt_date(p.date) for p in points],
            "net": [float(p.net_worth) for p in points], "value": [float(p.invested_value) for p in points],
            "contrib": [float(p.contributions) for p in points],
            "net_text": [fmt_eur(p.net_worth) for p in points], "value_text": [fmt_eur(p.invested_value) for p in points],
            "contrib_text": [fmt_eur(p.contributions) for p in points],
            "legend": [tr("Patrimonio neto"), tr("Valor de la cartera"), tr("Aportado")]}


def onboarding_texts() -> dict:
    """La bienvenida de Inicio sin datos (`ui.widgets.onboarding.Onboarding`), con los pasos segun lo que interesa."""
    accounts, investments = _settings.interest_accounts, _settings.interest_investments
    first, third = tr(qt_texts.WELCOME_STEPS[0][1]), tr(qt_texts.WELCOME_STEPS[2][1])
    if accounts and not investments:
        first = tr("En Imagin: tus movimientos, en CSV o Excel.")
        third = tr("Inicio y Cuentas se rellenan solos. Si reimportas un extracto, no se duplica nada.")
    elif investments and not accounts:
        first = tr("En MyInvestor: tus operaciones y tu cartera, también en CSV o Excel.")
        third = tr("Inicio e Inversiones se rellenan solos. Si reimportas un extracto, no se duplica nada.")
    bodies = (first, tr(qt_texts.WELCOME_STEPS[1][1]), third)
    return {"title": tr("Bienvenido a Kreix"),
            "intro": tr("Bienvenido a Kreix: tus finanzas, en tu equipo y sin conexión. Así se empieza:"),
            "steps": [{"title": tr(head), "text": body} for (head, _), body in zip(qt_texts.WELCOME_STEPS, bodies)],
            "import": tr("Importar mis extractos"), "demo": tr("Probar con datos de ejemplo"),
            "demo_tip": tr("Carga datos inventados para explorar la app. Se quitan con un clic."),
            "privacy": tr("Todo se queda en tu ordenador: Kreix no envía datos a ningún sitio.")}


def set_recurring(name: str, include: bool | None) -> dict:
    """Marca o quita un pago recurrente (como `AccountsView.set_recurring`, con su aviso y Deshacer)."""
    from core.recurring import merchant_key

    _snapshot()
    if not _svc.accounts.set_recurring(name, include):
        return _told("")
    message = {True: tr("«{name}» cuenta ahora como pago recurrente."),
               False: tr("«{name}» ya no cuenta como pago recurrente."),
               None: tr("Kreix vuelve a decidir solo sobre «{name}».")}[include]
    return _told(message.format(name=merchant_key(name)), undoable=True)


# ----------------------------------------------------------------------------- textos propios del movil
# Casi todo lo que dice la app movil son los textos del escritorio (y sus traducciones). Estos pocos solo existen aqui
# porque el gesto o el aparato es otro (mantener pulsado en vez de clic derecho, la camara, instalar la app...).
MOBILE = {
    "ca": {
        "Mantén pulsado un movimiento para cambiar su categoría o crear una regla.": "Mantén premut un moviment per canviar-ne la categoria o crear una regla.",
        "Ver más": "Veure'n més",
        "Elegir archivos": "Triar fitxers",
        "Los extractos de tu banco en CSV o Excel (también un archivo .kreix). Los encontrarás en Descargas o en Archivos.": "Els extractes del teu banc en CSV o Excel (també un fitxer .kreix). Els trobaràs a Baixades o a Fitxers.",
        "Recibir datos del ordenador": "Rebre dades de l'ordinador",
        "En el ordenador, abre Kreix y ve a Datos > Exportar > Pasar al móvil. Aparecerá un código QR que cambia: apunta la cámara a la pantalla hasta que se complete.": "A l'ordinador, obre Kreix i ves a Dades > Exportar > Passar al mòbil. Apareixerà un codi QR que canvia: apunta la càmera a la pantalla fins que es completi.",
        "Escanear el código QR": "Escanejar el codi QR",
        "Lo que recibas reemplazará los datos que haya en este móvil.": "El que rebis substituirà les dades que hi hagi en aquest mòbil.",
        "Guarda todos tus datos en un único archivo para hacer una copia o llevarlos a otro equipo.": "Desa totes les teves dades en un únic fitxer per fer-ne una còpia o portar-les a un altre equip.",
        "Para abrirlo, en este u otro equipo, hará falta la contraseña maestra que tienes ahora.": "Per obrir-lo, en aquest o en un altre equip, caldrà la contrasenya mestra que tens ara.",
        "Exportado: {name} ({size_kb} KB).": "Exportat: {name} ({size_kb} KB).",
        "Reemplazar los datos de este móvil": "Substituir les dades d'aquest mòbil",
        "El archivo contiene {transactions} movimientos, {operations} operaciones y {accounts} cuentas.\n\nAl importarlo se reemplazarán TODOS los datos que hay ahora en Kreix. Esta acción no se puede deshacer.\n\n¿Quieres continuar?": "El fitxer conté {transactions} moviments, {operations} operacions i {accounts} comptes.\n\nEn importar-lo se substituiran TOTES les dades que hi ha ara a Kreix. Aquesta acció no es pot desfer.\n\nVols continuar?",
        "Lo recibido está incompleto o dañado. Vuelve a escanear el código.": "El que s'ha rebut està incomplet o malmès. Torna a escanejar el codi.",
        "Apunta la cámara al código QR de la pantalla del ordenador.": "Apunta la càmera al codi QR de la pantalla de l'ordinador.",
        "Recibiendo… {pct} %": "Rebent… {pct} %",
        "No se puede usar la cámara. Revisa el permiso de la cámara para Kreix en los ajustes del móvil.": "No es pot fer servir la càmera. Revisa el permís de la càmera per a Kreix als ajustos del mòbil.",
        'Al cambiar de app o apagar la pantalla, Kreix vuelve a pedir la contraseña maestra antes de mostrar tus datos.': "En canviar d'app o apagar la pantalla, Kreix torna a demanar la contrasenya mestra abans de mostrar les teves dades.",
        'Aún no tienes reglas propias. Crea una desde aquí o manteniendo pulsado un movimiento.': "Encara no tens regles pròpies. Crea'n una des d'aquí o mantenint premut un moviment.",
        'Bloquear al salir de la app': "Bloquejar en sortir de l'app",
        'En el móvil, las copias se hacen desde Datos > Exportar: guarda el archivo .kreix en tu nube o envíatelo. Kreix guarda además la versión anterior de tus datos cifrada por si algo falla al guardar.': "Al mòbil, les còpies es fan des de Dades > Exportar: desa el fitxer .kreix al teu núvol o envia-te'l. A més, Kreix desa la versió anterior de les teves dades xifrada per si alguna cosa falla en desar.",
        'Hace más grande la letra de toda la aplicación. Se aplica al momento.': "Fa més gran la lletra de tota l'aplicació. S'aplica al moment.",
        'Si no usas Kreix durante este tiempo, esconde tus datos y vuelve a pedir la contraseña.': 'Si no fas servir Kreix durant aquest temps, amaga les teves dades i torna a demanar la contrasenya.',
        'Todo se guarda solo en este móvil, cifrado. Kreix no envía datos a ningún servidor.': 'Tot es desa només en aquest mòbil, xifrat. Kreix no envia dades a cap servidor.',
        'Modo claro y oscuro': 'Mode clar i fosc',
    },
    "en": {
        "Mantén pulsado un movimiento para cambiar su categoría o crear una regla.": "Press and hold a transaction to change its category or create a rule.",
        "Ver más": "Show more",
        "Elegir archivos": "Choose files",
        "Los extractos de tu banco en CSV o Excel (también un archivo .kreix). Los encontrarás en Descargas o en Archivos.": "Your bank statements in CSV or Excel (or a .kreix file). You'll find them in Downloads or Files.",
        "Recibir datos del ordenador": "Receive data from the computer",
        "En el ordenador, abre Kreix y ve a Datos > Exportar > Pasar al móvil. Aparecerá un código QR que cambia: apunta la cámara a la pantalla hasta que se complete.": "On the computer, open Kreix and go to Data > Export > Send to phone. A changing QR code will appear: point the camera at the screen until it completes.",
        "Escanear el código QR": "Scan the QR code",
        "Lo que recibas reemplazará los datos que haya en este móvil.": "What you receive will replace the data on this phone.",
        "Guarda todos tus datos en un único archivo para hacer una copia o llevarlos a otro equipo.": "Save all your data in a single file to keep a copy or move it to another device.",
        "Para abrirlo, en este u otro equipo, hará falta la contraseña maestra que tienes ahora.": "To open it, on this or another device, you'll need your current master password.",
        "Exportado: {name} ({size_kb} KB).": "Exported: {name} ({size_kb} KB).",
        "Reemplazar los datos de este móvil": "Replace the data on this phone",
        "El archivo contiene {transactions} movimientos, {operations} operaciones y {accounts} cuentas.\n\nAl importarlo se reemplazarán TODOS los datos que hay ahora en Kreix. Esta acción no se puede deshacer.\n\n¿Quieres continuar?": "The file contains {transactions} transactions, {operations} operations and {accounts} accounts.\n\nImporting it will replace ALL the data currently in Kreix. This cannot be undone.\n\nDo you want to continue?",
        "Lo recibido está incompleto o dañado. Vuelve a escanear el código.": "What was received is incomplete or damaged. Scan the code again.",
        "Apunta la cámara al código QR de la pantalla del ordenador.": "Point the camera at the QR code on the computer screen.",
        "Recibiendo… {pct} %": "Receiving… {pct}%",
        "No se puede usar la cámara. Revisa el permiso de la cámara para Kreix en los ajustes del móvil.": "The camera can't be used. Check Kreix's camera permission in your phone settings.",
        'Al cambiar de app o apagar la pantalla, Kreix vuelve a pedir la contraseña maestra antes de mostrar tus datos.': 'When you switch apps or turn off the screen, Kreix asks for the master password again before showing your data.',
        'Aún no tienes reglas propias. Crea una desde aquí o manteniendo pulsado un movimiento.': "You don't have any rules of your own yet. Create one here or by pressing and holding a transaction.",
        'Bloquear al salir de la app': 'Lock when leaving the app',
        'En el móvil, las copias se hacen desde Datos > Exportar: guarda el archivo .kreix en tu nube o envíatelo. Kreix guarda además la versión anterior de tus datos cifrada por si algo falla al guardar.': 'On the phone, backups are made from Data > Export: save the .kreix file to your cloud or send it to yourself. Kreix also keeps the previous version of your data, encrypted, in case something goes wrong while saving.',
        'Hace más grande la letra de toda la aplicación. Se aplica al momento.': 'Makes the text bigger throughout the app. Applies instantly.',
        'Si no usas Kreix durante este tiempo, esconde tus datos y vuelve a pedir la contraseña.': "If you don't use Kreix for this long, it hides your data and asks for the password again.",
        'Todo se guarda solo en este móvil, cifrado. Kreix no envía datos a ningún servidor.': "Everything is stored only on this phone, encrypted. Kreix doesn't send data to any server.",
        'Modo claro y oscuro': 'Light and dark mode',
    },
}


def m(text: str) -> str:
    """`tr` para los textos propios del movil."""
    return MOBILE.get(i18n.language(), {}).get(text, text)


# ----------------------------------------------------------------------------- piezas comunes de Cuentas e Inversiones
def _month(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _period(months: list[date], current: date | None) -> dict:
    """El selector de periodo (`ui.widgets.period_bar.PeriodBar`): todo el historial o un mes."""
    from ui.format import month_long

    return {"current": _iso(current), "label": tr(qt_texts.GLOBAL_LABEL),
            "months": [{"value": mo.isoformat(), "label": month_long(mo).capitalize()} for mo in months],
            "older": tr("Mes anterior"), "newer": tr("Mes siguiente"), "aria": tr("Periodo")}


def _card(title: str, value: str, sub: str = "", tone: str = "", help_term: str | None = None) -> dict:
    return {"title": title, "value": value, "sub": sub, "tone": tone, "help": help_term}


def _line_labels(dates: list[date], daily: bool) -> tuple[list[str], list[str]]:
    from ui.format import fmt_date, month_short

    return ([f"{d.day:02d}/{d.month:02d}" if daily else month_short(d) for d in dates], [fmt_date(d) for d in dates])


def _series(label: str, color: str, values, width: float, fill: bool = False, dashed: bool = False) -> dict:
    from ui.format import fmt_eur

    values = list(values)
    return {"label": label, "color": color, "width": width, "fill": fill, "dashed": dashed,
            "values": [float(v) for v in values], "texts": [fmt_eur(v) for v in values]}


def _empty_state(title: str, will_show: str, needs: str, button: str | None = None) -> dict:
    return {"title": title, "text": will_show, "needs_title": tr("QUÉ NECESITAS"), "needs": needs,
            "button": button or tr("Importar extractos")}


def _off_state(title: str, text: str, button: str) -> dict:
    return {"title": title, "text": text, "button": button,
            "note": tr("También puedes cambiarlo en Ajustes, en «Lo que te interesa».")}


def categories() -> list[dict]:
    """Todas las categorias, en el orden del escritorio (`ui.dialogs.ALL_CATEGORIES`)."""
    from core.enums import TxCategory
    from ui.format import category_label

    return [{"value": c.value, "label": category_label(c)} for c in TxCategory]


def _cat(value: str):
    from core.enums import TxCategory

    return TxCategory(value)


# ----------------------------------------------------------------------------- Cuentas
def cuentas(accounts: list[int] | None = None, month: str | None = None) -> dict:
    """Lo que pinta `ui.views.accounts_view.AccountsView._render`, como datos."""
    from ui.format import category_label, fmt_date, fmt_eur, fmt_pct, month_long, movement_category
    from ui.headlines import balance_headline, category_headline, monthly_headline

    if not _settings.interest_accounts:
        return {"off": _off_state(
            tr("Las cuentas bancarias están desactivadas"),
            tr("Dijiste que no te interesaba gestionar tus cuentas. Si has cambiado de idea, actívalas y verás aquí tu saldo, "
               "tus ingresos y gastos, tus presupuestos y todos tus movimientos."),
            tr("Activar cuentas bancarias")), "target": "accounts"}
    options = _settings.flow_options
    current = _month(month)
    d = _svc.accounts.view(accounts, current, options)
    if current is not None and current not in d.months:                 # ese mes ya no existe
        current = None
        d = _svc.accounts.view(accounts, None, options)
    names = {a.id: a.name for a in d.accounts}
    single = len(d.selected) == 1
    if accounts is None or set(d.selected) == set(names):
        picker_label = tr("Todas las cuentas")
        description = names[d.selected[0]] if single else trn("{n} cuenta", "{n} cuentas", len(d.accounts)).format(n=len(d.accounts))
    elif single:
        picker_label = description = names.get(d.selected[0], "")
    else:
        picker_label = tr("{n} de {total} cuentas").format(n=len(d.selected), total=len(d.accounts))
        description = trn("{n} cuenta", "{n} cuentas", len(d.selected)).format(n=len(d.selected))
    out: dict = {
        "eyebrow": tr("Tus cuentas"), "title": tr("Cuentas"),
        "subtitle": f"{month_long(current).capitalize()}  ·  {description}" if current else description,
        "accounts": [{"id": a.id, "name": a.name, "selected": a.id in d.selected} for a in d.accounts],
        "picker": {"label": picker_label, "all": tr("Todas las cuentas")},
        "manage": {"title": tr("Gestionar cuentas"), "add": tr("Añadir cuenta…"), "rename": tr("Renombrar cuenta…"),
                   "delete": tr("Eliminar cuenta…"), "single": single, "single_id": d.selected[0] if single else None,
                   "single_name": names.get(d.selected[0], "") if single else ""},
        "period": _period(d.months, current),
        "has_movements": d.has_movements and d.summary is not None,
    }
    if not out["has_movements"]:
        out["empty"] = _empty_state(
            tr("Aún no hay movimientos") if d.accounts else tr("Aún no tienes ninguna cuenta"),
            tr("Aquí verás tu saldo, tus ingresos y gastos, a dónde se va el dinero, tus presupuestos y tus pagos "
               "recurrentes, con todos tus movimientos para buscar y ordenar."),
            tr("El extracto de movimientos de tu cuenta de Imagin, en CSV o Excel. Arrástralo a Importar: Kreix lo "
               "reconoce solo y te enseña lo que ha leído antes de guardar nada."))
        return out

    s = d.summary
    scope = tr("al cierre de {month}").format(month=month_long(current)) if current else tr("saldo actual")
    if options.include_p2p and options.transfers_in_as_income:
        income_note = tr("Incluye Bizum y traspasos entrantes")
    elif options.include_p2p:
        income_note = tr("Incluye Bizum")
    elif options.transfers_in_as_income:
        income_note = tr("Incluye traspasos entrantes")
    else:
        income_note = tr("Sin Bizum ni traspasos")
    avg = ""
    if s.avg_daily_expense is not None:
        avg = (tr("Media {avg_daily_expense} al día").format(avg_daily_expense=fmt_eur(s.avg_daily_expense)) if current
               else tr("Media {avg_monthly_expense} al mes").format(avg_monthly_expense=fmt_eur(s.avg_monthly_expense)))
    if d.previous is not None and d.previous_month is not None:
        income_delta = _delta(s.income, d.previous.income, d.previous_month)
        expense_delta = _delta(s.expenses, d.previous.expenses, d.previous_month)
        income_note = f"{income_delta}\n{income_note}" if income_delta else income_note
        avg = f"{expense_delta}\n{avg}" if expense_delta and avg else (expense_delta or avg)
    rate = s.savings_rate
    ups = sum(1 for t in d.movements if t.amount > 0)
    big = s.largest_expense
    top = s.top_category
    out["cards"] = [
        _card(tr("Saldo"), fmt_eur(s.balance), scope, "negative" if s.balance is not None and s.balance < 0 else "", "Saldo"),
        _card(tr("Ingresos"), fmt_eur(s.income), income_note, "", "Ingresos"),
        _card(tr("Gastos"), fmt_eur(s.expenses), avg, "", "Gastos"),
        _card(tr("Tasa de ahorro"), fmt_pct(rate, 0) if rate is not None else "—",
              tr("Flujo neto {net}").format(net=signed_eur(s.net)) if rate is not None else tr("Sin ingresos en el periodo"),
              _tone(rate) if rate is not None else "", "Tasa de ahorro"),
    ]
    out["minis"] = [
        _card(tr("Movimientos"), str(s.movements), tr("{ups} entradas · {ups2} salidas").format(ups=ups, ups2=s.movements - ups)),
        _card(tr("Mayor gasto"), fmt_eur(-big.amount), f"{big.description} · {fmt_date(big.booking_date)}") if big
        else _card(tr("Mayor gasto"), "—", tr("Sin gastos")),
        _card(tr("Categoría principal"), category_label(top.category),
              tr("{amount} · {share} del gasto").format(amount=fmt_eur(top.amount), share=fmt_pct(top.share, 0))) if top
        else _card(tr("Categoría principal"), "—", tr("Sin gastos")),
        _card(tr("Gasto medio diario"), fmt_eur(s.avg_daily_expense)) if current else
        _card(tr("Gasto medio mensual"), fmt_eur(s.avg_monthly_expense),
              tr("{avg_daily_expense} al día").format(avg_daily_expense=fmt_eur(s.avg_daily_expense)) if s.avg_daily_expense is not None else ""),
    ]
    out["categories"] = {"title": tr("Gastos por categoría"), "caption": tr("Dónde se va el dinero en el periodo. Pulsa una para ver sus movimientos"),
                         "headline": category_headline(d.categories), "empty": tr("Sin gastos en este periodo"),
                         "items": [{"value": c.category.value, "label": category_label(c.category), "amount": fmt_eur(c.amount),
                                    "share": float(c.share), "pct": fmt_pct(c.share, 0)} for c in d.categories]}
    labels, tips = _line_labels([day for day, _ in d.balance_series], current is not None)
    out["balance"] = {"title": tr("Evolución del saldo"), "caption": tr("Saldo al cierre de cada día con movimientos"),
                      "headline": balance_headline(d.balance_series, current is not None), "labels": labels, "tips": tips,
                      "series": [_series(tr("Saldo"), "accent", [v for _, v in d.balance_series], 1.9, fill=True)]}
    monthly = d.monthly[-12:]
    out["monthly"] = {"title": tr("Ingresos y gastos por mes"), "caption": tr("Los últimos 12 meses de las cuentas seleccionadas"),
                      "headline": monthly_headline(monthly), **_flows(monthly), "contributions": False, "grouped": True}
    out["budgets"] = _budget_panel(d.budgets, current is not None)
    out["recurring"] = _recurring_panel(d.recurring)
    out["movements"] = {
        "title": tr("Movimientos"), "search": tr("Buscar por concepto…"), "all": tr(qt_texts.ALL_CATEGORIES),
        "count": tr("{total} movimientos"), "count_filtered": tr("{shown} de {total} movimientos"),
        "hint": m("Mantén pulsado un movimiento para cambiar su categoría o crear una regla."),
        "export": tr("Exportar"), "show_account": not single and len(d.accounts) > 1,
        "rows": [[t.tx_hash, fmt_date(t.booking_date), names.get(t.account_id, ""), t.description, t.category.value,
                  movement_category(t), signed_eur(t.amount), 1 if t.amount > 0 else -1 if t.amount < 0 else 0,
                  fmt_eur(t.balance_after)] for t in d.movements],
        "category_shown": trn("Mostrando {n} movimiento de «{category}». Quita el filtro en el selector de categorías de la tabla.",
                              "Mostrando {n} movimientos de «{category}». Quita el filtro en el selector de categorías de la tabla.", 2),
        "category_shown_one": trn("Mostrando {n} movimiento de «{category}». Quita el filtro en el selector de categorías de la tabla.",
                                  "Mostrando {n} movimientos de «{category}». Quita el filtro en el selector de categorías de la tabla.", 1),
    }
    return out


def _delta(current: Decimal, previous: Decimal, month: date) -> str:
    """Como `ui.views.accounts_view.delta_text`: '+12 % frente a ago 26'."""
    from ui.format import fmt_pct, month_short

    if previous <= 0:
        return ""
    change = (current - previous) / previous
    if round(change * 100) == 0:
        return tr("Igual que en {month}").format(month=month_short(month))
    return tr("{signed} frente a {month}").format(signed=fmt_pct(change, 0, signed=True), month=month_short(month))


def _budget_panel(lines, monthly: bool) -> dict:
    """`ui.widgets.panels.BudgetPanel`: cada presupuesto frente a lo gastado."""
    from ui.format import category_label, fmt_eur

    over = sum(1 for line in lines if line.state == "over")
    if lines:
        scope = tr("Gasto del mes frente a tu tope") if monthly else tr("Gasto medio mensual frente a tu tope")
        subtitle = f"{scope}  ·  " + trn("{n} superado", "{n} superados", over).format(n=over) if over else scope
    else:
        subtitle = tr("Sin presupuestos todavía")
    return {"title": tr("Presupuestos"), "subtitle": subtitle, "button": tr("Editar") if lines else tr("Definir presupuestos"),
            "empty": tr("Fija un tope mensual por categoría y Kreix te avisa cuando te acercas a él."),
            "items": [{"value": line.category.value, "label": category_label(line.category), "state": line.state,
                       "amount": tr("{spent} de {budget}").format(spent=fmt_eur(line.spent), budget=fmt_eur(line.budget)),
                       "share": float(line.spent / line.budget) if line.budget else 0.0,
                       "note": tr("Te has pasado {remaining}").format(remaining=fmt_eur(-line.remaining)) if line.state == "over"
                       else tr("Quedan {remaining}").format(remaining=fmt_eur(line.remaining))} for line in lines]}


def _recurring_panel(items) -> dict:
    """`ui.widgets.panels.RecurringPanel`: suscripciones y recibos que se repiten."""
    from core.recurring import monthly_cost
    from ui.format import fmt_date, fmt_eur

    if items:
        total = monthly_cost(items)
        subtitle = trn("{n} pago  ·  {month} al mes, {year} al año", "{n} pagos  ·  {month} al mes, {year} al año",
                       len(items)).format(n=len(items), month=fmt_eur(total), year=fmt_eur(total * 12))
    else:
        subtitle = tr("Suscripciones y recibos que se repiten")
    return {"title": tr("Pagos recurrentes"), "subtitle": subtitle, "columns": [tr("PAGO"), tr("IMPORTE"), tr("PRÓXIMO")],
            "rows": [{"name": r.name, "amount": fmt_eur(r.amount), "date": fmt_date(r.next_date)} for r in items],
            "empty": tr("Aún no hay pagos que se repitan cada mes. Aparecerán cuando haya al menos tres cargos "
                        "seguidos por un importe parecido."),
            "remove": tr("Quitar de pagos recurrentes")}


def _transaction(tx_hash: str):
    from services.mappers import cached_transactions

    return next((t for t in cached_transactions(_svc.accounts._factory) if t.tx_hash == tx_hash), None)


def movement_menu(tx_hash: str) -> dict:
    """Las opciones del menu de un movimiento (`AccountsView._show_row_menu` y `recurring_action`)."""
    from core.recurring import merchant_key

    tx = _transaction(tx_hash)
    if tx is None:
        return {}
    key = merchant_key(tx.description)
    recurring = None
    if tx.amount < 0 and key:
        mark = _svc.accounts.recurring_marks().get(key)
        if mark is True:
            recurring = {"label": tr("«{name}» no es un pago recurrente").format(name=key), "include": False}
        elif mark is False:
            recurring = {"label": tr("Volver a detectar «{name}» automáticamente").format(name=key), "include": None}
        elif any(merchant_key(r.name) == key for r in _svc.accounts.view(None, None, _settings.flow_options).recurring):
            recurring = {"label": tr("«{name}» no es un pago recurrente").format(name=key), "include": False}
        else:
            recurring = {"label": tr("Marcar «{name}» como pago recurrente").format(name=key), "include": True}
    return {"description": tx.description, "category": tx.category.value, "manual": tx.is_manual,
            "change": tr("Cambiar categoría"), "reset": tr("Volver a la categoría automática"),
            "rule": tr("Crear regla para «{description}»…").format(description=key or tx.description), "keyword": key or tx.description,
            "recurring": recurring, "copy": tr("Copiar concepto"), "categories": categories()}


def change_category(tx_hash: str, category: str | None) -> dict:
    from ui.format import category_label

    _snapshot()
    cat = _cat(category) if category else None
    _svc.category.set_category(tx_hash, cat)
    return _told(tr("Categoría cambiada a «{category}».").format(category=category_label(cat)) if cat is not None
                 else tr("Vuelve a la categoría automática."), undoable=True)


def rule_texts(keyword: str = "", category: str | None = None) -> dict:
    """`ui.dialogs.RuleDialog`."""
    return {"title": tr("Nueva regla de categoría"),
            "text": tr("Todos los movimientos cuyo concepto contenga esta palabra irán a la categoría elegida, también los que "
                       "importes en el futuro. Los que hayas clasificado tú a mano no se tocan."),
            "keyword_label": tr("Si el concepto contiene"), "placeholder": tr("p. ej. MERCADONA"),
            "category_label": tr("Va a la categoría"), "save": tr("Guardar regla"), "cancel": tr("Cancelar"),
            "keyword": keyword, "category": category, "categories": categories()}


def add_rule(keyword: str, category: str) -> dict:
    from data.repositories import RuleError
    from ui.format import category_label

    _snapshot()
    cat = _cat(category)
    try:
        changed = _svc.category.add_rule(keyword, cat)
    except RuleError as exc:
        _discard_undo()
        return {"error": str(exc), "error_title": tr("No se pudo guardar la regla")}
    return _told(trn("Regla creada: {changed} movimiento cambiado a «{category}».",
                     "Regla creada: {changed} movimientos cambiados a «{category}».", changed).format(changed=changed, category=category_label(cat)),
                 undoable=True)


def budget_texts() -> dict:
    """`ui.dialogs.BudgetDialog`: un tope por categoria (0 = sin vigilar)."""
    from core.budget import BUDGETABLE
    from ui.format import category_label

    current = _svc.category.budgets()
    return {"title": tr("Presupuestos mensuales"),
            "text": tr("Cuánto quieres gastar como máximo al mes en cada categoría. Deja a 0 las que no quieras vigilar."),
            "save": tr("Guardar"), "cancel": tr("Cancelar"),
            "items": [{"value": c.value, "label": category_label(c), "amount": float(current.get(c, 0))} for c in BUDGETABLE]}


def save_budgets(budgets: dict[str, float]) -> dict:
    _snapshot()
    clean = {_cat(k): Decimal(str(v)).quantize(Decimal("0.01")) for k, v in budgets.items() if v and float(v) > 0}
    _svc.category.save_budgets(clean)
    return _told(tr("Presupuestos guardados.") if clean else tr("Presupuestos eliminados."), undoable=True)


def add_account(name: str) -> dict:
    from data.repositories import AccountError

    try:
        info = _svc.accounts.add(name)
    except AccountError as exc:
        return {"error": str(exc), "error_title": tr("No se pudo añadir la cuenta")}
    return {**_told(tr("Cuenta «{name}» añadida. Elígela al importar tus extractos.").format(name=info.name)), "id": info.id}


def rename_account(account_id: int, name: str) -> dict:
    from data.repositories import AccountError

    try:
        _svc.accounts.rename(account_id, name)
    except AccountError as exc:
        return {"error": str(exc), "error_title": tr("No se pudo renombrar")}
    return _told("")


def delete_account(account_id: int) -> dict:
    name = next((a.name for a in _svc.accounts.accounts() if a.id == account_id), "")
    _snapshot()
    _svc.accounts.delete(account_id)
    return _told(tr("Cuenta «{name}» eliminada.").format(name=name), undoable=True)


def account_texts() -> dict:
    return {"add_title": tr("Añadir cuenta"), "add_label": tr("Nombre de la cuenta:"), "rename_title": tr("Renombrar cuenta"),
            "rename_label": tr("Nuevo nombre:"), "delete_title": tr("Eliminar cuenta"),
            "delete_text": tr("Se eliminará la cuenta «{currentText}» y todos sus movimientos.\nEsta acción no se puede deshacer.\n\n¿Quieres continuar?"),
            "ok": tr("Aceptar"), "cancel": tr("Cancelar")}


def export_movements(hashes: list[str], fmt: str = "xlsx") -> dict:
    """Guarda en CSV o Excel los movimientos que se ven (en el orden de la lista). El worker entrega el archivo al movil."""
    from services.mappers import cached_transactions
    from services.movements_export import ExportError, write_movements
    from ui.format import category_label

    by_hash = {t.tx_hash: t for t in cached_transactions(_svc.accounts._factory)}
    rows = [by_hash[h] for h in hashes if h in by_hash]
    if not rows:
        return {"error": tr("No hay movimientos con el filtro actual."), "error_title": tr("Nada que exportar")}
    name = f"movimientos.{'csv' if fmt == 'csv' else 'xlsx'}"
    path = Path("/tmp") / name
    names = {a.id: a.name for a in _svc.accounts.accounts()}
    try:
        count = write_movements(path, rows, names, category_label)
    except ExportError as exc:
        return {"error": str(exc), "error_title": tr("No se pudo exportar")}
    return {"__file__": str(path), "name": name, "message": tr("{count} movimientos exportados a «{name}».").format(count=count, name=name)}


# ----------------------------------------------------------------------------- Inversiones
def inversiones(month: str | None = None, fund: str | None = None) -> dict:
    """Lo que pinta `ui.views.investment_view.InvestmentView._render`, como datos."""
    from ui.format import EMPTY, fmt_date, fmt_eur, fmt_pct, fmt_units, month_long, operation_label
    from ui.headlines import evolution_headline, fund_headline

    if not _settings.interest_investments:
        return {"off": _off_state(
            tr("Las inversiones están desactivadas"),
            tr("Dijiste que no te interesaba gestionar tus inversiones. Si has cambiado de idea, actívalas y verás aquí el valor "
               "de tu cartera, lo que has aportado, tu plusvalía y tu rentabilidad."),
            tr("Activar inversiones")), "target": "investments"}
    current = _month(month)
    d = _svc.investment.view(current)
    if current is not None and current not in d.months:
        current = None
        d = _svc.investment.view(None)
    out: dict = {"eyebrow": tr("Tu cartera"), "title": tr("Inversiones"), "period": _period(d.months, current),
                 "has_data": d.has_data and d.summary is not None}
    if not out["has_data"]:
        out["empty"] = _empty_state(
            tr("Aún no hay datos de inversión"),
            tr("Aquí verás el valor de tu cartera, lo que has aportado, tu plusvalía y tu rentabilidad (TWR y TIR), "
               "con todas tus posiciones y operaciones."),
            tr("Dos archivos de MyInvestor, en CSV o Excel: tus operaciones (el historial de compras) y tu cartera "
               "(las posiciones de hoy). Arrástralos a Importar; la cartera te pedirá a qué día corresponde."))
        return out
    s = d.summary
    out["banner"] = None
    if d.warnings:
        extra = len(d.warnings) - 1
        more = trn(" Hay {extra} aviso más en Importar.", " Hay {extra} avisos más en Importar.", extra).format(extra=extra) if extra else ""
        out["banner"] = {"html": tr("<b>La cartera no cuadra con las operaciones importadas.</b> {warnings}{more} La rentabilidad (TIR y TWR) no se muestra hasta que cuadre.").format(warnings=_esc(d.warnings[0]), more=more),
                         "button": tr("Ir a Importar")}
    reliable = not d.warnings
    twr = s.twr if reliable else None
    twr_text = fmt_pct(twr, 2, signed=True) if twr is not None else EMPTY
    if current:
        gain = s.period_gain
        out["cards"] = [
            _card(tr("Valor de la cartera"), fmt_eur(s.value), tr("al cierre de {month} (estimado)").format(month=month_long(current)), "", "Valor de la cartera"),
            _card(tr("Aportado"), signed_eur(s.contributions_period), tr("Acumulado: {contributions_total}").format(contributions_total=fmt_eur(s.contributions_total)), "", "Aportado (capital invertido)"),
            _card(tr("Variación del mes"), signed_eur(gain) if gain is not None else EMPTY, tr("Sin contar las aportaciones"), _tone(gain) if gain is not None else "", "Plusvalía y minusvalía"),
            _card(tr("Rentabilidad del mes"), twr_text, tr("Ponderada en el tiempo") if reliable else tr("No disponible: la cartera no cuadra"),
                  _tone(twr) if twr is not None else "", "TWR (rentabilidad ponderada en el tiempo)"),
        ]
    else:
        sub = (tr("TIR {xirr} anual").format(xirr=fmt_pct(s.xirr)) if s.xirr is not None else tr("Ponderada en el tiempo")) if reliable \
            else tr("No disponible: la cartera no cuadra")
        out["cards"] = [
            _card(tr("Valor de la cartera"), fmt_eur(s.value), tr("Valor de mercado actual"), "", "Valor de la cartera"),
            _card(tr("Aportado"), fmt_eur(s.contributions_total), tr("Compras menos ventas"), "", "Aportado (capital invertido)"),
            _card(tr("Plusvalía"), signed_eur(s.gain) if s.gain is not None else EMPTY,
                  tr("Rentabilidad {signed}").format(signed=fmt_pct(s.simple_return, 2, signed=True)) if s.simple_return is not None else tr("Importa la cartera de MyInvestor"),
                  _tone(s.gain) if s.gain is not None else "", "Plusvalía y minusvalía"),
            _card(tr("Rentabilidad (TWR)"), twr_text, sub, _tone(twr) if twr is not None else "", "TWR (rentabilidad ponderada en el tiempo)"),
        ]
    lp = s.largest_position
    out["minis"] = [
        _card(tr("Operaciones"), str(s.operations), tr("{buys} compras · {sells} ventas").format(buys=s.buys, sells=s.sells)),
        _card(tr("Aportación media mensual"), fmt_eur(s.avg_monthly_contribution) if s.avg_monthly_contribution is not None else EMPTY),
        _card(tr("Fondos en cartera"), str(s.positions)),
        _card(tr("Posición mayor"), lp.label if lp else EMPTY, tr("{weight} de la cartera").format(weight=fmt_pct(lp.weight, 1)) if lp else ""),
    ]
    zero = Decimal(0)
    out["allocation"] = {"title": tr("Distribución por fondo"), "caption": tr("Cartera actual"), "headline": fund_headline(d.allocation),
                         "empty": tr("Importa la cartera de MyInvestor"),
                         "total": fmt_eur(sum((a.value for a in d.allocation if a.value > 0), zero), 0),
                         "slices": [{"key": a.label, "label": a.label, "value": float(a.value), "text": fmt_eur(a.value), "pct": fmt_pct(a.weight)}
                                    for a in d.allocation if a.value > 0]}
    labels, tips = _line_labels([w.date for w in d.evolution], False)
    out["evolution"] = {"title": tr("Aportado frente a valor"), "caption": tr("La diferencia es lo que ha aportado la rentabilidad"),
                        "headline": evolution_headline(d.evolution), "labels": labels, "tips": tips,
                        "series": [_series(tr("Valor de la cartera"), "accent", [w.invested_value for w in d.evolution], 1.9, fill=True),
                                   _series(tr("Aportado"), "neutral", [w.contributions for w in d.evolution], 1.2, dashed=True)]}
    out["funds"] = None
    if d.funds:
        fund = fund if any(f.isin == fund for f in d.funds) else None
        shown = [f for f in d.funds if fund in (None, f.isin)]
        labels, tips = _line_labels([w.date for w in shown[0].points], False)
        if len(shown) == 1:
            f = shown[0]
            series = [_series(f.name, "accent", [w.invested_value for w in f.points], 1.9, fill=True),
                      _series(tr("Aportado"), "neutral", [w.contributions for w in f.points], 1.2, dashed=True)]
        else:
            series = [_series(f.name, f"series{i}", [w.invested_value for w in f.points], 1.7) for i, f in enumerate(shown)]
        out["funds"] = {"title": tr("Evolución de cada fondo"),
                        "caption": tr("Valor de cada fondo al cierre de cada mes, según tus extractos. Entre extractos es una estimación."),
                        "all": tr("Todos los fondos"), "aria": tr("Fondo"), "current": fund,
                        "options": [{"value": f.isin, "label": f.name} for f in d.funds],
                        "labels": labels, "tips": tips, "series": series}

    def gain_of(p):
        return p.market_value - p.invested

    out["positions"] = {
        "title": tr("Posiciones actuales"), "caption": tr("Según el último extracto de cartera importado"),
        "labels": {"units": tr("PARTIC."), "avg": tr("P. MEDIO"), "price": tr("VL ACTUAL"), "invested": tr("INVERTIDO"),
                   "value": tr("VALOR"), "gain": tr("PLUSVALÍA"), "ret": tr("RENTAB.")},
        "rows": [{"name": p.product_name, "isin": p.isin, "units": fmt_units(p.units), "avg": fmt_eur(p.avg_cost), "price": fmt_eur(p.unit_price),
                  "invested": fmt_eur(p.invested), "value": fmt_eur(p.market_value), "gain": signed_eur(gain_of(p)), "tone": _tone(gain_of(p)),
                  "ret": fmt_pct(gain_of(p) / p.invested, 2, signed=True) if p.invested else EMPTY} for p in d.positions]}
    out["operations"] = {
        "title": tr("Operaciones"), "count": tr("{operations} operaciones").format(operations=len(d.operations)),
        "labels": {"units": tr("PARTIC."), "price": tr("VL"), "amount": tr("IMPORTE")},
        "rows": [{"date": fmt_date(o.trade_date), "name": o.product_name, "isin": o.isin, "type": operation_label(o.op_type),
                  "units": fmt_units(o.units), "price": fmt_eur(o.unit_price), "amount": fmt_eur(abs(o.amount))} for o in d.operations]}
    return out


def set_interest(accounts: bool | None = None, investments: bool | None = None) -> dict:
    """"Activar cuentas / inversiones" desde una pestana desactivada (sin tocar la otra)."""
    changes = {}
    if accounts is not None:
        changes["interest_accounts"] = accounts
    if investments is not None:
        changes["interest_investments"] = investments
    return save_settings(**changes)


# ----------------------------------------------------------------------------- Datos: importar extractos
# Los archivos que elige el usuario los escribe el worker en /tmp/in (ver `put_files` en worker.js); aqui se leen con el
# mismo ImportService del escritorio.
def datos() -> dict:
    """La pagina Datos: Importar (`ui.views.import_view`), recibir del ordenador, Exportar (`ui.views.export_view`)."""
    from services.transfer_service import EXTENSION

    accounts = _svc.accounts.accounts()
    funds = _svc.importer.funds()
    s = _svc.transfer.summary()
    return {
        "import": {
            "eyebrow": tr("Entrada de datos"), "title": tr("Importar extractos"),
            "subtitle": tr("Los archivos se procesan en tu equipo. Reimportar un extracto no duplica movimientos."),
            "choose": m("Elegir archivos"),
            "choose_hint": m("Los extractos de tu banco en CSV o Excel (también un archivo .kreix). Los encontrarás en Descargas o en Archivos."),
            "account_label": tr("Cuenta de destino"),
            "account_hint": tr("A qué cuenta bancaria pertenecen los extractos que importes (Imagin u otro banco)."),
            "accounts": [{"id": a.id, "name": a.name} for a in accounts] or [{"id": None, "name": tr("Cuenta nueva (se creará al importar)")}],
            "as_of_label": tr("Fecha de la cartera"),
            "as_of_hint": tr("El extracto de cartera de MyInvestor no incluye fecha: indica a qué día corresponde."),
            "fund_label": tr("Fondo del histórico"),
            "fund_hint": tr("Si importas el histórico de precios de un fondo y el archivo no lleva su ISIN, indica a qué fondo pertenece."),
            "funds": [{"isin": None, "name": tr("Detectarlo por el archivo")}] + [{"isin": i, "name": n} for i, n in funds] if funds else [],
            "preview_title": tr("Revisa antes de importar"),
            "preview_hint": tr("Esto es lo que Kreix ha leído. Todavía no se ha guardado nada."),
            "cancel": tr("Cancelar"), "results": tr("Resultado"),
        },
        "formats": _formats(),
        "receive": {
            "title": m("Recibir datos del ordenador"),
            "text": m("En el ordenador, abre Kreix y ve a Datos > Exportar > Pasar al móvil. Aparecerá un código QR que cambia: apunta la cámara a la pantalla hasta que se complete."),
            "button": m("Escanear el código QR"),
            "replace": m("Lo que recibas reemplazará los datos que haya en este móvil."),
        },
        "export": {
            "eyebrow": tr("Copia de seguridad"), "title": tr("Exportar"),
            "subtitle": m("Guarda todos tus datos en un único archivo para hacer una copia o llevarlos a otro equipo."),
            "button": tr("Exportar datos…"), "encrypt": tr("Cifrar el archivo con mi contraseña maestra"),
            "encrypt_note": m("Para abrirlo, en este u otro equipo, hará falta la contraseña maestra que tienes ahora."),
            "what": tr("Qué se exporta"),
            "what_text": tr("Cuentas, movimientos, categorías, operaciones, cartera y ajustes. Todo tal cual está ahora."),
            "contents": _summary_text(s),
            "warn_title": tr("<b>El archivo no está cifrado</b>"),
            "warn_text": tr("Contiene tu información financiera. Guárdalo en un sitio seguro y no lo compartas."),
            "extension": EXTENSION,
        },
    }


def _summary_text(s) -> str:
    if s.is_empty:
        return tr("Todavía no hay nada guardado.")

    def plural(n: int, one: str, many: str) -> str:
        return f"{n} {one if n == 1 else many}"

    return "  ·  ".join([
        plural(s.accounts, tr("cuenta"), tr("cuentas")),
        plural(s.transactions, tr("movimiento bancario"), tr("movimientos bancarios")),
        plural(s.operations, tr("operación de inversión"), tr("operaciones de inversión")),
        plural(s.investments, tr("fondo"), tr("fondos")),
    ])


def _formats() -> dict:
    """Los bancos que el usuario enseno a leer (`ImportView.refresh_formats`)."""
    items = []
    for mapping in _svc.importer.formats():
        if mapping.uses_two_columns:
            money = tr("ingresos «{income}» y gastos «{expense}»").format(income=mapping.income, expense=mapping.expense)
        else:
            money = tr("importe «{amount}»").format(amount=mapping.amount)
        items.append({"name": mapping.name, "detail": tr("fecha «{date}», concepto «{description}», {money}").format(
            date=mapping.date, description=mapping.description, money=money)})
    return {"title": tr("Bancos que ya conozco"), "hint": tr("Formatos que definiste tú: los archivos con esas columnas se leen solos."),
            "forget": tr("Olvidar"), "items": items}


def _plural_rows(n: int, kind) -> str:
    from core.entities import FileKind

    names = {
        FileKind.IMAGIN_STATEMENT: (tr("movimiento"), tr("movimientos")),
        FileKind.BANK_STATEMENT: (tr("movimiento"), tr("movimientos")),
        FileKind.MYINVESTOR_OPERATIONS: (tr("operación"), tr("operaciones")),
        FileKind.MYINVESTOR_PORTFOLIO: (tr("posición"), tr("posiciones")),
    }
    one, many = names.get(kind, (tr("fila"), tr("filas")))
    return f"{n} {one if n == 1 else many}"


def _split_backups(paths: list[str]) -> tuple[list[str], list[str]]:
    from services.transfer_service import EXTENSION

    backups = [p for p in paths if p.lower().endswith(EXTENSION)]
    return [p for p in paths if p not in backups], backups


def import_preview(paths: list[str], as_of: str, account_id: int | None = None, fund: str | None = None) -> dict:
    """`ImportView.preview_paths`: lo que se leeria de cada archivo, sin guardar nada."""
    from ui.format import fmt_date

    paths, backups = _split_backups(paths)
    out: dict = {"backup": backups[0] if backups else None, "rows": [], "ready": False}
    if not paths:
        return out
    previews = _svc.importer.preview(paths, date.fromisoformat(as_of), account_id, fund)
    for p in previews:
        if not p.ok:
            state, label = "error", tr("No se puede importar")
        elif not p.changes_data:
            state, label = "warn", tr("Nada nuevo")
        else:
            state, label = "ok", tr("Listo para importar")
        lines = []
        if p.ok:
            read = f"{p.kind_label}  ·  {_plural_rows(p.rows, p.kind)}"
            if p.first and p.last:
                read += (tr("  ·  del {first} al {last}").format(first=fmt_date(p.first), last=fmt_date(p.last))
                         if p.first != p.last else f"  ·  {fmt_date(p.first)}")
            lines.append(read)
            parts = [tr("{new} nuevos").format(new=p.new)]
            if p.updated:
                parts.append(tr("{updated} se actualizarán").format(updated=p.updated))
            if p.existing:
                parts.append(tr("{existing} ya estaban importados y se ignoran").format(existing=p.existing))
            lines.append("  ·  ".join(parts))
        else:
            lines.append(p.explanation)
        out["rows"].append({"name": p.file_name, "state": state, "label": label, "lines": lines, "warnings": list(p.warnings),
                            "path": p.path, "map": tr("Asignar las columnas…") if p.unknown_format and p.path else None})
    ready = [p for p in previews if p.changes_data]
    out["pending"] = [path for path, p in zip(paths, previews) if p.ok]
    out["ready"] = bool(ready)
    total = sum(p.new + p.updated for p in ready)
    out["confirm"] = ((tr("Importar {total} filas nuevas").format(total=total) if total != 1 else tr("Importar 1 fila nueva"))
                      if ready else tr("No hay nada nuevo que importar"))
    return out


def import_confirm(paths: list[str], as_of: str, account_id: int | None = None, fund: str | None = None) -> dict:
    """`ImportView.import_paths`: guarda lo leido (antes quita los datos de ejemplo, si los habia)."""
    global _state
    if _state.get("demo") == "1":                                # ImportView.before_import -> MainWindow.leave_demo
        _svc.data.reset_all()
        _svc.settings.clear_state("demo")
        _state = _svc.settings.load_state()
        account_id = None                                         # la cuenta de ejemplo ya no existe
    _snapshot()
    report = _svc.importer.import_files(paths, date.fromisoformat(as_of), account_id, fund)
    rows = []
    for f in report.files:
        if not f.ok:
            state, label, detail = "error", tr("Error"), f.explanation
        else:
            state, label = ("warn", tr("Con avisos")) if f.warnings else ("ok", tr("Importado"))
            detail = tr("{kind_label}  ·  {inserted} nuevos").format(kind_label=f.kind_label, inserted=f.inserted)
            if f.updated:
                detail += tr("  ·  {updated} actualizados").format(updated=f.updated)
            if f.skipped:
                detail += tr("  ·  {skipped} ya existían").format(skipped=f.skipped)
        rows.append({"name": f.file_name, "state": state, "label": label, "detail": detail, "warnings": list(f.warnings)})
    reconcile = None
    if report.reconciliation_warnings:
        reconcile = {"title": tr("<b>La cartera no cuadra con las operaciones importadas</b>"), "items": report.reconciliation_warnings,
                     "tip": tr("Exporta desde MyInvestor el historial completo de operaciones y vuelve a importarlo.")}
    if report.total_changed:
        added = sum(f.inserted for f in report.files)
        changed = sum(f.updated for f in report.files)
        text = tr("Importado: {added} nuevos").format(added=added) + (tr(" y {changed} actualizados").format(changed=changed) if changed else "") + "."
        told = _told(text, undoable=True)
    else:
        told = _told(tr("No había nada nuevo que importar.") if any(f.ok for f in report.files) else tr("No se ha podido importar ningún archivo."))
    _clean_inbox(paths)
    return {**told, "rows": rows, "reconcile": reconcile}


def _clean_inbox(paths: list[str]) -> None:
    for p in paths:
        try:
            Path(p).unlink()
        except OSError:
            pass


def forget_format(name: str) -> dict:
    _snapshot()
    if _svc.importer.delete_format(name):
        return _told(tr("Formato «{name}» olvidado. Los movimientos ya importados no cambian.").format(name=name), undoable=True)
    return _told("")


# ----------------------------------------------------------------------------- asistente de otro banco (ui/mapping_dialog.py)
def mapping_open(path: str, header_index: int | None = None, name: str = "") -> dict:
    """Las primeras filas del archivo y las columnas que Kreix propone."""
    from etl.common import ParseError
    from etl.mapping import MAX_PREAMBLE_ROWS, SAMPLE_ROWS

    try:
        sample = _svc.importer.sample(path, header_index)
    except (ParseError, OSError) as exc:
        return {"error": str(exc), "error_title": tr("No se puede leer el archivo")}
    guess = _svc.importer.suggest_mapping(sample, name)
    return {
        "title": tr("Importar de otro banco"),
        "text": tr("Kreix no conoce este archivo todavía. Dime qué columna es cada cosa y lo recordaré: la próxima "
                   "vez que llegue un archivo con las mismas columnas se leerá solo."),
        "header_label": tr("Fila de los títulos"), "header_index": sample.header_index,
        "header_rows": list(range(1, max(1, min(MAX_PREAMBLE_ROWS, len(sample.rows))) + 1)),
        "headers": sample.headers, "keys": sample.keys,
        "rows": [["" if v is None else str(v) for v in r] for r in sample.body(SAMPLE_ROWS)],
        "labels": {"date": tr("Fecha"), "description": tr("Concepto"), "mode": tr("El importe viene en"), "amount": tr("Importe"),
                   "income": tr("Ingresos"), "expense": tr("Gastos"), "balance": tr("Saldo (opcional)"), "decimals": tr("Decimales"),
                   "order": tr("Orden de la fecha"), "name": tr("Nombre del formato"), "table": tr("Primeras filas del archivo")},
        "choose": tr("— Elige una columna —"), "unused": tr("— No usar —"),
        "modes": [{"value": "one", "label": tr("Una columna, con el signo (negativo = gasto)")},
                  {"value": "two", "label": tr("Dos columnas: ingresos y gastos")}],
        "decimal_options": [{"value": True, "label": tr("Con coma: 1.234,56")}, {"value": False, "label": tr("Con punto: 1,234.56")}],
        "order_options": [{"value": True, "label": tr("Día / mes / año")}, {"value": False, "label": tr("Mes / día / año")}],
        "invert": tr("En este archivo los gastos aparecen como números positivos"),
        "placeholder": tr("p. ej. Mi banco"), "save": tr("Guardar y usar"), "cancel": tr("Cancelar"),
        "guess": {"date": guess.date, "description": guess.description, "amount": guess.amount, "income": guess.income,
                  "expense": guess.expense, "balance": guess.balance, "decimal_comma": guess.decimal_comma, "day_first": guess.day_first,
                  "mode": "two" if guess.uses_two_columns and (guess.income or guess.expense) else "one",
                  "name": name or tr("Mi banco")},
    }


def _mapping(fields: dict):
    from etl.mapping import ColumnMapping

    two = fields.get("mode") == "two"
    return ColumnMapping(
        name=(fields.get("name") or "").strip(), date=fields.get("date") or "", description=fields.get("description") or "",
        amount="" if two else (fields.get("amount") or ""), income=(fields.get("income") or "") if two else "",
        expense=(fields.get("expense") or "") if two else "", balance=fields.get("balance") or "",
        day_first=bool(fields.get("day_first", True)), decimal_comma=bool(fields.get("decimal_comma", True)),
        invert_sign=bool(fields.get("invert_sign", False)))


def mapping_try(path: str, header_index: int, fields: dict) -> dict:
    """`MappingDialog._refresh`: lo que se leeria con estas columnas."""
    from etl.common import ParseError
    from ui.format import fmt_date, fmt_eur

    sample = _svc.importer.sample(path, header_index)
    mapping = _mapping(fields)
    problem = mapping.problem() or (tr("Ponle un nombre al formato.") if not mapping.name else None)
    parsed = None
    if mapping.problem() is None:
        try:
            parsed = _svc.importer.try_mapping(path, sample, mapping)
        except ParseError as exc:
            problem = str(exc)
    if parsed is None:
        return {"ok": False, "result": problem or "", "lines": [], "error": ""}
    dates = [t.booking_date for t in parsed.transactions]
    count = len(parsed.transactions)
    text = trn("Se lee {n} movimiento, del {first} al {last}.", "Se leen {n} movimientos, del {first} al {last}.", count)
    lines = [f"{fmt_date(t.booking_date)}  ·  {t.description[:48]}  ·  {fmt_eur(t.amount)}" for t in parsed.transactions[:3]]
    if parsed.ignored_rows:
        lines.append(trn("{n} fila se ha ignorado (por ejemplo, un total al final).",
                         "{n} filas se han ignorado (por ejemplo, totales al final).", parsed.ignored_rows).format(n=parsed.ignored_rows))
    return {"ok": problem is None, "result": text.format(n=count, first=fmt_date(min(dates)), last=fmt_date(max(dates))) if dates else "",
            "lines": lines, "error": problem or ""}


def mapping_save(fields: dict) -> dict:
    from etl.common import ParseError

    _snapshot()
    try:
        _svc.importer.save_format(_mapping(fields))
    except ParseError as exc:
        _discard_undo()
        return {"error": str(exc)}
    return _told(tr("Formato guardado: Kreix ya sabe leer este banco."), undoable=True)


# ----------------------------------------------------------------------------- restaurar un .kreix (MainWindow.restore_from)
def restore_check(path: str, password: str | None = None) -> dict:
    """Lee el archivo sin restaurarlo: pide la contrasena si esta cifrado y avisa de que reemplaza los datos."""
    from services.transfer_service import PasswordRequired, TransferError, WrongImportPassword

    try:
        info = _svc.transfer.inspect(path, password)
    except (PasswordRequired, WrongImportPassword) as exc:
        return {"password": True, "wrong": str(exc) if isinstance(exc, WrongImportPassword) else "",
                "title": tr("Archivo cifrado"), "label": tr("Escribe la contraseña maestra con la que se exportó este archivo:"),
                "error_title": tr("No se puede importar el archivo")}
    except TransferError as exc:
        return {"error": str(exc), "error_title": tr("No se puede importar el archivo")}
    s = info.summary
    confirm = None
    if not _svc.transfer.summary().is_empty:
        confirm = {"title": m("Reemplazar los datos de este móvil"),
                   "text": m("El archivo contiene {transactions} movimientos, {operations} operaciones y {accounts} cuentas.\n\nAl importarlo se reemplazarán TODOS los datos que hay ahora en Kreix. Esta acción no se puede deshacer.\n\n¿Quieres continuar?").format(
                       transactions=s.transactions, operations=s.operations, accounts=s.accounts)}
    return {"ok": True, "confirm": confirm}


def restore_apply(path: str, password: str | None = None) -> dict:
    global _settings, _state
    from services.transfer_service import TransferError
    from ui import format as formatting

    _snapshot()
    try:
        _svc.transfer.restore(path, password)
    except TransferError as exc:
        _discard_undo()
        return {"error": str(exc), "error_title": tr("No se pudo importar el archivo")}
    finally:
        _clean_inbox([path])
    _svc.settings.clear_state("demo")                               # lo restaurado es de verdad
    _settings = _svc.settings.load()                                # los ajustes viajan con los datos
    _state = _svc.settings.load_state()
    _svc.importer.reload_formats()
    i18n.set_language(_settings.language)
    formatting.set_private(_settings.privacy_mode)
    return _told(tr("Datos importados desde el archivo .kreix."), undoable=True)


def export_kreix(encrypt: bool = True) -> dict:
    """`ExportView.export_to`: todos los datos en un .kreix (cifrado con la contrasena maestra si se pide)."""
    from services.transfer_service import EXTENSION

    name = f"kreix-datos-{date.today().isoformat()}{EXTENSION}"
    path = Path("/tmp") / name
    _svc.transfer.export_to(path, _store.seal_export if encrypt else None)
    size_kb = max(path.stat().st_size // 1024, 1)
    return {"__file__": str(path), "name": name, "message": m("Exportado: {name} ({size_kb} KB).").format(name=name, size_kb=size_kb)}


def receive_transfer(path: str) -> dict:
    """Lo recibido por QR (el .kreix comprimido, ver `core/qr_transfer.py`): se descomprime y se trata como un .kreix."""
    from core.qr_transfer import unpack

    target = Path("/tmp/in/recibido.kreix")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(unpack(Path(path).read_bytes()))
    except ValueError:
        return {"error": m("Lo recibido está incompleto o dañado. Vuelve a escanear el código."), "error_title": tr("No se puede importar el archivo")}
    finally:
        _clean_inbox([path])
    return {"path": str(target)}


# ----------------------------------------------------------------------------- Ajustes (ui/views/settings_view.py)
def ajustes() -> dict:
    from services.settings_service import LOCK_MINUTES, TEXT_SCALES
    from ui.format import category_label

    s = _settings
    return {
        "eyebrow": tr("Preferencias"), "title": tr("Ajustes"), "settings": asdict(s),
        "groups": {"you": tr("Tú"), "look": tr("Aspecto y cálculos"), "security": tr("Seguridad"), "backups": tr("Copias de seguridad"),
                   "app": tr("Datos y aplicación")},
        "name": {"title": tr("Tu nombre"), "hint": tr("Kreix te saluda por tu nombre en Inicio. Se guarda con tus datos y viaja con ellos al exportar "
                                                      "e importar."), "placeholder": tr("Tu nombre"), "save": tr("Guardar")},
        "language": {"title": tr("Idioma"), "hint": tr("Cambia el idioma de toda la aplicación al instante. Se guarda con tus datos."),
                     "options": [{"code": c, "name": i18n.NAMES[c]} for c in i18n.LANGUAGES]},
        "interests": {"title": tr("Lo que te interesa"),
                      "hint": tr("Elige qué quieres gestionar. Lo que desactives no desaparece: sus pestañas siguen ahí y "
                                 "puedes activarlo cuando quieras, aquí o desde la propia pestaña."),
                      "accounts_title": tr(qt_texts.ACCOUNTS_TITLE), "accounts_text": tr(qt_texts.ACCOUNTS_TEXT),
                      "investments_title": tr(qt_texts.INVESTMENTS_TITLE), "investments_text": tr(qt_texts.INVESTMENTS_TEXT),
                      "at_least_one": tr(qt_texts.AT_LEAST_ONE)},
        "text": {"title": tr("Tamaño del texto"), "hint": m("Hace más grande la letra de toda la aplicación. Se aplica al momento."),
                 "options": [{"value": p, "label": f"{label} ({p} %)"} for p, label in zip(TEXT_SCALES, (tr("Normal"), tr("Grande"), tr("Muy grande")))]},
        "switches": [
            {"key": "ambient", "title": tr("Cielo animado y luz según la hora"),
             "text": tr("Anima el sol, la luna y a Blitzen y Black en Inicio, y baja muy ligeramente el brillo por la tarde y por la noche. No cambia el tema.")},
            {"key": "include_p2p", "title": tr("Contar Bizum como ingresos y gastos"),
             "text": tr("Si lo desactivas, los Bizum no entran en el cálculo de la tasa de ahorro.")},
            {"key": "transfers_in_as_income", "title": tr("Contar traspasos entrantes como ingresos"),
             "text": tr("Útil si tu dinero llega por traspasos desde otra cuenta. Los traspasos salientes nunca cuentan.")},
        ],
        "rules": {"title": tr("Reglas de categorías"),
                  "intro": tr("Las reglas mandan sobre las que trae Kreix: si el concepto de un movimiento contiene "
                              "la palabra clave, va a la categoría que elijas. Los movimientos que clasifiques a mano nunca cambian."),
                  "empty": m("Aún no tienes reglas propias. Crea una desde aquí o manteniendo pulsado un movimiento."),
                  "add": tr("Añadir regla…"), "remove": tr("Eliminar"),
                  "items": [{"id": r.id, "keyword": r.keyword, "category": category_label(r.category)} for r in _svc.category.rules()]},
        "security": {"title": tr("Seguridad"), "hint": tr("Tus datos están cifrados con tu contraseña maestra. Puedes cambiarla cuando quieras."),
                     "change": tr("Cambiar contraseña maestra…"), "lock": tr("Bloquear ahora"),
                     "auto_title": tr("Bloqueo automático"),
                     "auto_hint": m("Si no usas Kreix durante este tiempo, esconde tus datos y vuelve a pedir la contraseña."),
                     "auto_options": [{"value": mi, "label": tr("Nunca") if mi == 0 else trn("{n} minuto", "{n} minutos", mi).format(n=mi)} for mi in LOCK_MINUTES],
                     "leave_title": m("Bloquear al salir de la app"),
                     "leave_text": m("Al cambiar de app o apagar la pantalla, Kreix vuelve a pedir la contraseña maestra antes de mostrar tus datos.")},
        "backups": {"text": m("En el móvil, las copias se hacen desde Datos > Exportar: guarda el archivo .kreix en tu nube o envíatelo. "
                              "Kreix guarda además la versión anterior de tus datos cifrada por si algo falla al guardar."),
                    "button": tr("Exportar datos…")},
        "data": {"title": tr("Tus datos"), "hint": m("Todo se guarda solo en este móvil, cifrado. Kreix no envía datos a ningún servidor."),
                 "reset": tr("Borrar todos los datos"), "reset_title": tr("Borrar todos los datos"),
                 "reset_text": tr("Se eliminarán todos los movimientos, operaciones y la cartera importados.\n"
                                  "Tus ajustes se conservan. Esta acción no se puede deshacer.\n\n"
                                  "¿Quieres continuar?")},
        "about": {"title": tr("Acerca de"), "version": tr("Kreix {VERSION}").format(VERSION=qt_texts.VERSION),
                  "whats_new": tr("Ver las novedades"), "help": tr("Ayuda")},
    }


def save_name(name: str) -> dict:
    from core.greeting import clean_name

    name = clean_name(name)
    state = save_settings(user_name=name, name_asked=True)
    return {**state, "message": tr("Nombre guardado: {name}.").format(name=name) if name else tr("Nombre quitado: Kreix te saludará sin nombre.")}


def delete_rule(rule_id: int) -> dict:
    _snapshot()
    changed = _svc.category.delete_rule(rule_id)
    return _told(trn("Regla eliminada: {changed} movimiento vuelve a su categoría automática.",
                     "Regla eliminada: {changed} movimientos vuelven a su categoría automática.", changed).format(changed=changed), undoable=True)


def password_texts() -> dict:
    """`ui.password_dialog.ChangePasswordDialog`."""
    return {"title": tr("Cambiar contraseña maestra"),
            "text": tr("Tus datos se vuelven a cifrar con la contraseña nueva. Si la olvidas, no hay forma de recuperarlos."),
            "current": tr("Contraseña actual"), "new": tr("Contraseña nueva"), "again": tr("Repite la contraseña nueva"),
            "ok": tr("Cambiar contraseña"), "cancel": tr("Cancelar"), "empty": tr("Escribe la contraseña actual."),
            "short": tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD), "mismatch": tr("Las contraseñas no coinciden."),
            "min": MIN_PASSWORD}


def change_password(old: str, new: str) -> dict:
    if len(new) < MIN_PASSWORD:
        return {"error": tr("Usa al menos {n} caracteres.").format(n=MIN_PASSWORD)}
    try:
        _store.change_password(old, new)
    except WrongPasswordError:
        return {"error": tr("La contraseña actual no es correcta.")}
    return _told(tr("Contraseña maestra cambiada."))


def reset_data() -> dict:
    global _state
    _snapshot()
    _svc.data.reset_all()
    _svc.settings.clear_state("demo")
    _state = _svc.settings.load_state()
    return _told(tr("Datos borrados."), undoable=True)


def whats_new() -> dict:
    version = qt_texts.VERSION
    return {"title": tr("Novedades de Kreix {version}").format(version=version),
            "items": [{"title": tr(h), "text": tr(t)} for h, t in qt_texts.RELEASES.get(version, ())]}


# ----------------------------------------------------------------------------- Ayuda (ui/views/help_view.py)
def ayuda(query: str = "", section: str | None = None) -> dict:
    from ui.help_content import ENTRIES, SECTION_INFO, SECTIONS, localized_entries, search

    shown = localized_entries()
    pairs = list(zip(ENTRIES, shown))
    out: dict = {"eyebrow": tr("Glosario"), "title": tr("Ayuda"),
                 "subtitle": tr("Qué significa cada cifra y cada gráfico de Kreix, explicado sin tecnicismos. Elige un tema."),
                 "search": tr("O busca un término: TIR, patrimonio neto, tasa de ahorro…"), "search_label": tr("Buscar en la ayuda"),
                 "back": tr("Volver al menú de Ayuda"), "query": query, "section": section}
    out["sections"] = [{"key": s, "title": tr(s), "icon": SECTION_INFO[s][0],
                        "text": tr("{description}  ·  {count} términos").format(description=tr(SECTION_INFO[s][1]),
                                                                                count=sum(1 for o, _ in pairs if o.section == s))}
                       for s in SECTIONS]
    if query.strip():
        found = search(shown, query)
        keys = {id(e) for e in found}
        out["entries"] = [_entry(o, e) for o, e in pairs if id(e) in keys]
        order = {id(e): i for i, e in enumerate(found)}
        out["entries"].sort(key=lambda x: next(order[id(e)] for o, e in pairs if o.term == x["key"]))
        out["summary"] = tr("{found} de {total} términos").format(found=len(found), total=len(shown))
        out["empty"] = tr("No hay resultados para «{query}». Prueba con otra palabra.").format(query=query) if not found else ""
    elif section:
        out["entries"] = [_entry(o, e) for o, e in pairs if o.section == section]
        info = SECTION_INFO.get(section)
        out["section_title"] = tr(section)
        out["section_text"] = tr("{description}  ·  {count} términos").format(description=tr(info[1]), count=len(out["entries"])) if info else ""
    return out


# ----------------------------------------------------------------------------- metas de ahorro (ui/goals_dialog.py)
# Como en el escritorio, todo lo que se cambia en el cuadro de metas se deshace de una vez desde el aviso al cerrarlo.
_goals_snapshot: Path | None = None


def goals_open() -> dict:
    """Abre el cuadro: guarda la foto para "Deshacer" y devuelve lo que ensena."""
    global _goals_snapshot
    _snapshot()
    _goals_snapshot = _undo
    return goals_list()


def goals_list() -> dict:
    from ui.format import fmt_date, fmt_eur

    goals = _svc.goals.goals()
    return {
        "title": tr("Metas de ahorro"), "text": tr("Apunta lo que vas guardando para cada meta. Kreix no mueve dinero: solo lleva la cuenta."),
        "add": tr("Nueva meta…"), "done": tr("Hecho"), "empty": tr("Aún no tienes metas. Crea la primera."),
        "contribute": tr("Apuntar ahorro"), "edit": tr("Editar"), "delete": tr("Eliminar"),
        "contribute_text": tr("Importe que has guardado para «{name}» (usa un número negativo para restar):"),
        "delete_title": tr("Eliminar meta"), "delete_text": tr("¿Eliminar la meta «{name}»?"),
        "form": {"new": tr("Nueva meta"), "edit": tr("Editar meta"),
                 "text": tr("Un objetivo con nombre, el importe al que quieres llegar y, si quieres, una fecha."),
                 "name": tr("Nombre"), "placeholder": tr("Por ejemplo: Vacaciones"), "target": tr("Quiero llegar a"),
                 "saved": tr("Llevo ahorrado"), "deadline": tr("Quiero ponerle una fecha"), "save": tr("Guardar"), "cancel": tr("Cancelar"),
                 "no_name": tr("Ponle un nombre a la meta."), "no_target": tr("El importe objetivo debe ser mayor que cero.")},
        "items": [{"id": g.id, "name": g.name, "target": float(g.target), "saved": float(g.saved), "deadline": _iso(g.deadline),
                   "amount": tr("{spent} de {budget}").format(spent=fmt_eur(g.saved), budget=fmt_eur(g.target)),
                   "progress": float(g.fraction), "reached": g.reached,
                   "date": fmt_date(g.deadline) if g.deadline else ""} for g in goals],
    }


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def goal_save(name: str, target: float, saved: float = 0, deadline: str | None = None, goal_id: int | None = None) -> dict:
    from services.goals_service import GoalError

    try:
        _svc.goals.save(name, _money(target), _money(saved), date.fromisoformat(deadline) if deadline else None, goal_id)
    except GoalError as exc:
        return {"error": tr("Ponle un nombre a la meta.") if str(exc) == "name" else tr("El importe objetivo debe ser mayor que cero.")}
    return goals_list()


def goal_contribute(goal_id: int, amount: float) -> dict:
    if amount:
        _svc.goals.contribute(goal_id, _money(amount))
    return goals_list()


def goal_delete(goal_id: int) -> dict:
    _svc.goals.delete(goal_id)
    return goals_list()


def goals_close(changed: bool) -> dict:
    """Al cerrar: si algo cambio, el aviso con Deshacer (que vuelve a como estaba al abrir el cuadro)."""
    global _goals_snapshot, _undo
    snapshot, _goals_snapshot = _goals_snapshot, None
    if not changed:
        _discard_undo()
        return {"message": ""}
    _undo = snapshot
    return {"message": tr("Metas de ahorro actualizadas."), "undoable": _undo is not None}


# ----------------------------------------------------------------------------- ayuda
def _entry(original, shown) -> dict:
    parts = [{"label": label, "text": text, "tone": tone} for label, text, tone in (
        (tr("Cómo lo calcula"), shown.how, ""), (tr("Ejemplo"), shown.example, ""),
        (tr("Ojo"), shown.note, "alert"), (tr("Qué hacer"), shown.todo, "tip")) if text]
    return {"key": original.term, "section": tr(original.section), "term": shown.term, "plain": shown.plain, "parts": parts}


def help_entry(term: str) -> dict | None:
    """La explicacion de una cifra (el «?» junto a su titulo), como la ensena la Ayuda del escritorio."""
    from ui.help_content import ENTRIES, localized_entries

    for original, shown in zip(ENTRIES, localized_entries()):
        if original.term == term:
            return _entry(original, shown)
    return None


def demo_banner() -> dict:
    return {"text": tr("Estás viendo datos de ejemplo inventados. Nada de esto es tuyo."), "button": tr("Empezar con mis datos")}


_PUBLIC = {fn.__name__: fn for fn in (
    boot, lock_texts, password_strength, create, unlock, reset, app_state, save_settings, welcome_texts, finish_welcome,
    ui_texts, catalog, undo, start_demo, end_demo, hide_setup, clock, inicio, demo_banner, set_recurring, help_entry, categories, cuentas, movement_menu, change_category, rule_texts, add_rule,
    budget_texts, save_budgets, add_account, rename_account, delete_account, account_texts, export_movements, inversiones, set_interest, datos, import_preview, import_confirm,
    forget_format, mapping_open, mapping_try, mapping_save, restore_check, restore_apply, export_kreix, receive_transfer,
    ajustes, save_name, delete_rule, password_texts, change_password, reset_data, whats_new, ayuda,
    goals_open, goals_list, goal_save, goal_contribute, goal_delete, goals_close,
)}
