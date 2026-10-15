"""Busca en el codigo todos los textos traducibles (tr, trn, N_) y dice a cuales les falta traduccion.

Uso:  python tools/i18n_keys.py            # resumen de lo que falta en catalan e ingles
      python tools/i18n_keys.py --list     # todas las claves, en el orden en que aparecen
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ("ui", "services", "core", "etl", "data", "main.py")
SKIP = ("core/locales", "ui/help_texts", "core/i18n.py")
MARKERS = {"tr", "N_"}


def collect() -> dict[str, list[tuple[str, int]]]:
    """texto original -> donde aparece. Incluye tr("..."), N_("...") y las dos formas de trn(uno, varios, n)."""
    found: dict[str, list[tuple[str, int]]] = {}
    files: list[Path] = []
    for entry in SCAN:
        target = ROOT / entry
        files += [target] if target.is_file() else sorted(target.rglob("*.py"))
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(s) for s in SKIP):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name in MARKERS and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.setdefault(node.args[0].value, []).append((rel, node.lineno))
            elif name == "trn":
                for arg in node.args[:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.setdefault(arg.value, []).append((rel, node.lineno))
    return found


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{([A-Za-z_][A-Za-z_0-9]*)(?:[:!][^}]*)?\}", text))


def missing(language: str) -> list[str]:
    from importlib import import_module

    sys.path.insert(0, str(ROOT))
    texts = import_module(f"core.locales.{language}").TEXTS
    return [k for k in collect() if k not in texts]


if __name__ == "__main__":
    keys = collect()
    if "--list" in sys.argv:
        for key in keys:
            print(repr(key))
    else:
        print(f"{len(keys)} textos traducibles")
        for lang in ("ca", "en"):
            print(f"  {lang}: faltan {len(missing(lang))}")
