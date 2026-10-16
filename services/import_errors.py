"""Errores de importacion con palabras claras: que ha pasado y que hacer para arreglarlo.

Los mensajes tecnicos de lectura (`ParseError`) ya vienen en el idioma activo; para reconocerlos se busca un fragmento
caracteristico tanto en castellano como en su traduccion (por eso cada fragmento tambien esta en los catalogos).
"""
from __future__ import annotations

from core.i18n import N_, tr

HINTS: tuple[tuple[str, str, str], ...] = (
    # (fragmento del mensaje original, mensaje claro, que hacer)
    (N_("solo importa extractos en csv o excel"), N_("Kreix no importa PDF."),
     N_("Descarga el extracto en CSV o Excel desde la web o la app de tu banco.")),
    (N_("formato no reconocido"), N_("No reconozco este archivo como un extracto de Imagin ni de MyInvestor."),
     N_("Si es el extracto de otro banco en CSV o Excel, pulsa «Asignar las columnas» y dime qué es cada una: lo recordaré. "
        "Si es de Imagin o MyInvestor, descárgalo otra vez sin editarlo.")),
    (N_("faltan columnas"), N_("Al archivo le faltan columnas que Kreix necesita."),
     N_("Suele pasar si se ha editado o si es de otro tipo. Descárgalo otra vez desde tu banco sin modificarlo.")),
    (N_("no se pudo decodificar"), N_("No he podido leer el texto del archivo."),
     N_("Ábrelo y guárdalo como CSV (UTF-8) o como Excel, y vuelve a intentarlo.")),
    (N_("fecha no valida"), N_("Hay una fecha que no entiendo."),
     N_("Descarga el extracto otra vez sin editarlo. Las fechas deben tener formato día/mes/año.")),
    (N_("importe no valido"), N_("Hay un importe que no entiendo."),
     N_("Descarga el extracto otra vez sin editarlo; no cambies los números ni añadas texto en esas columnas.")),
    (N_("no indica a qué fondo pertenece"), N_("Este histórico de precios no dice a qué fondo corresponde."),
     N_("Elige el fondo en «Fondo del histórico», en esta misma página, y vuelve a soltar el archivo.")),
    (N_("ningún precio"), N_("No he encontrado precios en el archivo."),
     N_("Comprueba que tiene una columna de fecha y otra de precio (valor liquidativo, cierre...) y que no está vacío.")),
    (N_("ningún movimiento"), N_("Con esas columnas no he podido leer ningún movimiento."),
     N_("Revisa en el asistente qué columna es la fecha y cuál el importe, y el orden de la fecha y los decimales.")),
    (N_("cuenta de destino"), N_("La cuenta elegida ya no existe."), N_("Elige otra cuenta de destino y vuelve a importar.")),
)
GENERIC = (N_("No he podido leer este archivo."),
           N_("Comprueba que no está abierto en otro programa (por ejemplo Excel) y que es un extracto en CSV o Excel."))
# Errores cuyo texto original aporta algo (que fila, que dato): se conserva como detalle.
_KEEP_DETAIL = (N_("faltan columnas"), N_("fecha no valida"), N_("importe no valido"))


def _contains(text: str, fragment: str) -> bool:
    return fragment in text or tr(fragment).lower() in text


def friendly_error(original: str) -> tuple[str, str]:
    """(mensaje claro, que hacer) para un error de lectura."""
    text = original.lower()
    for fragment, message, todo in HINTS:
        if _contains(text, fragment):
            return tr(message), tr(todo)
    return tr(GENERIC[0]), tr(GENERIC[1])


def describe(original: str) -> str:
    """Mensaje completo para mostrar: lo que pasa, lo que hacer y, si ayuda, el detalle tecnico."""
    message, todo = friendly_error(original)
    text = original.lower()
    keep = not original or any(_contains(text, f) for f in _KEEP_DETAIL) or (message, todo) == (tr(GENERIC[0]), tr(GENERIC[1]))
    detail = " " + tr("(Detalle: {original})").format(original=original) if original and keep else ""
    return f"{message} {todo}{detail}"
