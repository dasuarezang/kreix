"""Errores de importacion con palabras claras: que ha pasado y que hacer para arreglarlo."""
from __future__ import annotations

HINTS: tuple[tuple[str, str, str], ...] = (
    # (fragmento del mensaje original, mensaje claro, que hacer)
    ("solo importa extractos en csv o excel", "Kreix no importa PDF.",
     "Descarga el extracto en CSV o Excel desde la web o la app de tu banco."),
    ("formato no reconocido", "No reconozco este archivo como un extracto de Imagin ni de MyInvestor.",
     "Comprueba que es el extracto de movimientos de Imagin, o las operaciones o la cartera de MyInvestor, "
     "descargado en CSV o Excel y sin editar."),
    ("faltan columnas", "Al archivo le faltan columnas que Kreix necesita.",
     "Suele pasar si se ha editado o si es de otro tipo. Descárgalo otra vez desde tu banco sin modificarlo."),
    ("no se pudo decodificar", "No he podido leer el texto del archivo.",
     "Ábrelo y guárdalo como CSV (UTF-8) o como Excel, y vuelve a intentarlo."),
    ("fecha no valida", "Hay una fecha que no entiendo.",
     "Descarga el extracto otra vez sin editarlo. Las fechas deben tener formato día/mes/año."),
    ("importe no valido", "Hay un importe que no entiendo.",
     "Descarga el extracto otra vez sin editarlo; no cambies los números ni añadas texto en esas columnas."),
    ("cuenta de destino", "La cuenta elegida ya no existe.", "Elige otra cuenta de destino y vuelve a importar."),
)
GENERIC = ("No he podido leer este archivo.",
           "Comprueba que no está abierto en otro programa (por ejemplo Excel) y que es un extracto en CSV o Excel.")


def friendly_error(original: str) -> tuple[str, str]:
    """(mensaje claro, que hacer) para un error de lectura. El texto original no se pierde: ver `detail`."""
    text = original.lower()
    for fragment, message, todo in HINTS:
        if fragment in text:
            return message, todo
    return GENERIC


# Errores cuyo texto original aporta algo (que fila, que dato): se conserva como detalle.
_KEEP_DETAIL = ("faltan columnas", "fecha no valida", "importe no valido")


def describe(original: str) -> str:
    """Mensaje completo para mostrar: lo que pasa, lo que hacer y, si ayuda, el detalle tecnico."""
    message, todo = friendly_error(original)
    keep = not original or any(f in original.lower() for f in _KEEP_DETAIL) or (message, todo) == GENERIC
    detail = f" (Detalle: {original})" if original and keep else ""
    return f"{message} {todo}{detail}"
