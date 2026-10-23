"""Construye la app movil de Kreix (PWA) en la web publica: `../kreix-web/app/` por defecto.

Uso:  .venv/Scripts/python tools/build_pwa.py [CARPETA_DE_SALIDA]

La PWA ejecuta en el navegador, con Pyodide, la misma logica que el escritorio (`core`, `data`, `etl`, `services` y los
modulos de `ui` que no usan Qt); la interfaz es HTML/JS (`pwa/web/`) y habla con esa logica a traves de `pwa/py/kreix_web.py`.
Este script junta todo en una carpeta estatica lista para GitHub Pages:

- `kreix.zip`: el codigo Python. Lo de `ui` que depende de Qt no va: de `ui/blur.py` solo se copian las marcas de las
  cantidades ocultas, y las constantes de texto de los widgets (`N_(...)`) se extraen a `qt_texts.py`.
- `wheels/`: openpyxl y et_xmlfile (no vienen con Pyodide), para leer Excel sin conexion.
- las fuentes, los iconos (renderizados desde los SVG del logotipo), el manifest y el service worker con la lista de
  archivos y una version que cambia con el contenido (asi el movil se actualiza solo).
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PWA = ROOT / "pwa"
DEFAULT_OUT = ROOT.parent / "kreix-web" / "app"
CACHE = ROOT / "build" / "pwa-cache"

PYODIDE = "0.29.5"        # 314.x rompe cryptography (panico de Rust al importarla); 0.29 trae Python 3.13 y funciona
WHEELS = {                # Python puro, desde PyPI: (paquete, version)
    "openpyxl": "3.1.5",
    "et_xmlfile": "2.0.0",
}
VENDOR = {                # JS de terceros, desde npm: (version, archivo dentro del paquete)
    "jsqr": ("1.4.0", "package/dist/jsQR.js"),
}
PACKAGES = ("core", "data", "etl", "services")
UI_MODULES = ("ui/__init__.py", "ui/format.py", "ui/headlines.py", "ui/help_content.py", "ui/help_texts/__init__.py",
              "ui/help_texts/ca.py", "ui/help_texts/en.py")
BLUR_NAMES = ("START", "END", "mark", "has_mark", "split", "clean_text")
QT_TEXTS = {              # modulo con Qt -> constantes de texto que la PWA necesita
    "ui/widgets/onboarding.py": ("WELCOME_STEPS",),
    "ui/widgets/budget_carousel.py": ("STATE_TEXT",),
    "ui/widgets/interests.py": ("ACCOUNTS_TITLE", "ACCOUNTS_TEXT", "INVESTMENTS_TITLE", "INVESTMENTS_TEXT", "AT_LEAST_ONE"),
    "ui/widgets/period_bar.py": ("GLOBAL_LABEL",),
    "ui/views/accounts_view.py": ("ALL_CATEGORIES",),
    "ui/whats_new.py": ("VERSION", "RELEASES"),
}
BG = "#101418"            # fondo de la app (modo oscuro), tambien el de la pantalla de arranque del movil
ICON_BG = "#1F2429"       # el cuadrado del icono


# ----------------------------------------------------------------------------- codigo Python
def tracked(*patterns: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", *patterns], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.endswith(".py")]


def _strip_n(node: ast.AST) -> ast.AST:
    """`N_("x")` -> `"x"`, para poder evaluar la constante como literal."""
    class Strip(ast.NodeTransformer):
        def visit_Call(self, call: ast.Call) -> ast.AST:
            self.generic_visit(call)
            if isinstance(call.func, ast.Name) and call.func.id == "N_" and len(call.args) == 1:
                return call.args[0]
            return call
    return Strip().visit(node)


def qt_texts() -> str:
    lines = ['"""Constantes de texto de los modulos de Qt de `ui/` (generado por tools/build_pwa.py: no editar)."""', ""]
    for module, names in QT_TEXTS.items():
        tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
        found = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target, value = node.target, node.value
            else:
                continue
            if isinstance(target, ast.Name) and target.id in names:
                found[target.id] = ast.literal_eval(_strip_n(value))
        missing = set(names) - set(found)
        if missing:
            raise SystemExit(f"{module}: no encuentro {', '.join(sorted(missing))}")
        lines.append(f"# {module}")
        lines += [f"{name} = {found[name]!r}" for name in names]
        lines.append("")
    return "\n".join(lines)


def blur_markers() -> str:
    """De `ui/blur.py`, solo las marcas de texto (sin Qt): `ui/format.py` las usa en modo privacidad."""
    source = (ROOT / "ui/blur.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    keep = []
    for node in tree.body:
        name = (node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                else node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None)
        if name in BLUR_NAMES:
            keep.append(ast.get_source_segment(source, node))
    head = '"""Marcas de las cantidades ocultas (de ui/blur.py, sin Qt; generado por tools/build_pwa.py)."""\nfrom __future__ import annotations\n\n'
    return head + "\n\n\n".join(keep) + "\n"


def python_bundle() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for path in tracked(*(f"{p}/*" for p in PACKAGES)) + list(UI_MODULES):
            z.write(ROOT / path, path)
        z.writestr("ui/blur.py", blur_markers())
        z.writestr("qt_texts.py", qt_texts())
        for path in (PWA / "py").glob("*.py"):
            z.write(path, path.name)
    return buffer.getvalue()


def wheels() -> dict[str, bytes]:
    """Descarga (una vez, se guardan en build/) las ruedas puras que Pyodide no trae."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for package, version in WHEELS.items():
        cached = next(CACHE.glob(f"{package}-{version}-*.whl"), None)
        if cached is None:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/{version}/json") as response:
                info = json.load(response)
            wheel = next(u for u in info["urls"] if u["packagetype"] == "bdist_wheel" and u["filename"].endswith("none-any.whl"))
            with urllib.request.urlopen(wheel["url"]) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
                raise SystemExit(f"{wheel['filename']}: la suma de comprobacion no coincide")
            cached = CACHE / wheel["filename"]
            cached.write_bytes(data)
        out[cached.name] = cached.read_bytes()
    return out


PYODIDE_CORE = ("pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json")
PYODIDE_PACKAGES = ("sqlalchemy", "cryptography", "xlrd", "sqlite3")      # y sus dependencias, segun el lock


def pyodide_files() -> dict[str, bytes]:
    """Pyodide alojado junto a la app (nada se pide a terceros): el nucleo sale del paquete npm (comprobado con su firma de
    integridad) y los paquetes, de la CDN oficial, comprobados con el sha256 de pyodide-lock.json. Se guardan en build/."""
    import base64
    import tarfile

    folder = CACHE / f"pyodide-{PYODIDE}"
    folder.mkdir(parents=True, exist_ok=True)
    if not all((folder / name).exists() for name in PYODIDE_CORE):
        with urllib.request.urlopen(f"https://registry.npmjs.org/pyodide/{PYODIDE}") as response:
            dist = json.load(response)["dist"]
        with urllib.request.urlopen(dist["tarball"]) as response:
            tarball = response.read()
        algo, expected = dist["integrity"].split("-", 1)
        if base64.b64encode(hashlib.new(algo, tarball).digest()).decode() != expected:
            raise SystemExit("pyodide: la suma de comprobacion del paquete npm no coincide")
        with tarfile.open(fileobj=io.BytesIO(tarball)) as tar:
            for name in PYODIDE_CORE:
                (folder / name).write_bytes(tar.extractfile(f"package/{name}").read())
    lock = json.loads((folder / "pyodide-lock.json").read_text(encoding="utf-8"))["packages"]
    needed, todo = set(), list(PYODIDE_PACKAGES)
    while todo:
        name = todo.pop()
        if name not in needed:
            needed.add(name)
            todo += lock[name]["depends"]
    out = {f"pyodide/{name}": (folder / name).read_bytes() for name in PYODIDE_CORE}
    for name in sorted(needed):
        info = lock[name]
        wheel = folder / info["file_name"]
        if not wheel.exists():
            with urllib.request.urlopen(f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full/{info['file_name']}") as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != info["sha256"]:
                raise SystemExit(f"{info['file_name']}: la suma de comprobacion no coincide")
            wheel.write_bytes(data)
        out[f"pyodide/{info['file_name']}"] = wheel.read_bytes()
    return out


def vendor_js() -> dict[str, bytes]:
    """Bibliotecas JS de terceros, desde npm (una vez; se guardan en build/): jsQR lee los QR con la camara."""
    import base64
    import tarfile

    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for package, (version, member) in VENDOR.items():
        cached = CACHE / f"{package}-{version}.js"
        if not cached.exists():
            with urllib.request.urlopen(f"https://registry.npmjs.org/{package}/{version}") as response:
                dist = json.load(response)["dist"]
            with urllib.request.urlopen(dist["tarball"]) as response:
                tarball = response.read()
            algo, expected = dist["integrity"].split("-", 1)
            if base64.b64encode(hashlib.new(algo, tarball).digest()).decode() != expected:
                raise SystemExit(f"{package}: la suma de comprobacion no coincide")
            with tarfile.open(fileobj=io.BytesIO(tarball)) as tar:
                cached.write_bytes(tar.extractfile(member).read())
        out[f"vendor/{Path(member).name}"] = cached.read_bytes()
    return out


# ----------------------------------------------------------------------------- iconos
def icons_js() -> bytes:
    """Los iconos de trazo de `ui/icons.py` (los mismos SVG del escritorio) como modulo JS."""
    sys.path.insert(0, str(ROOT))
    from ui.icons import _SHAPES

    body = json.dumps(_SHAPES, ensure_ascii=False, indent=1)
    return f"// Iconos de ui/icons.py (generado por tools/build_pwa.py: no editar).\nexport const SHAPES = {body};\n".encode()


def logo_js() -> bytes:
    """El logotipo (icono + KREIX) para la barra superior: el texto toma el color del tema y la caja se ajusta al dibujo."""
    svg = (ROOT / "logo-mejorado" / "kreix-logotipo-transparente.svg").read_text(encoding="utf-8")
    svg = (svg.replace('viewBox="0 0 1400 480" width="1400" height="480"', 'viewBox="120 80 1020 320" class="wordmark" role="img" aria-label="Kreix"')
              .replace('fill="#7F7F7F"', 'fill="currentColor"').replace('id="g"', 'id="kreix-g"').replace("url(#g)", "url(#kreix-g)"))
    return f"// Logotipo de Kreix (generado por tools/build_pwa.py: no editar).\nexport const WORDMARK = {json.dumps(svg)};\n".encode()


def icon(size: int, scale: float = 1.0, square: bool = False) -> bytes:
    """El icono de Kreix a `size` px. `square` rellena las esquinas (iOS y Android recortan el suyo); `scale` < 1 deja el
    margen de seguridad de los iconos adaptables (maskable)."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(ICON_BG) if square else Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    side = size * scale
    offset = (size - side) / 2
    svg = (ROOT / "logo-mejorado" / "kreix-icono-oscuro.svg").read_bytes()
    QSvgRenderer(QByteArray(svg)).render(painter, QRectF(offset, offset, side, side))
    painter.end()
    data = QByteArray()
    from PySide6.QtCore import QBuffer, QIODevice

    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


DOGS = {                  # capas de Blitzen y Black de la web (tools/web_dogs.py), con la misma animacion CSS
    "black-cola.webp": "perretes/black-cola.webp", "black-ojos.webp": "perretes/black-ojos.webp", "black.webp": "perretes/black.webp",
    "blitzen-lengua.webp": "perretes/blitzen-lengua.webp", "blitzen-ojos.webp": "perretes/blitzen-ojos.webp",
    "blitzen.webp": "perretes/blitzen.webp", "durmiendo.webp": "perretes-durmiendo.webp",
}


def dog_layers() -> dict[str, bytes]:
    assets = ROOT.parent / "kreix-web" / "assets"
    missing = [src for src in DOGS.values() if not (assets / src).is_file()]
    if missing:
        raise SystemExit(f"faltan las capas de los perros en {assets}: {', '.join(missing)} (tools/web_dogs.py)")
    return {f"img/dogs/{name}": (assets / src).read_bytes() for name, src in DOGS.items()}


# ----------------------------------------------------------------------------- salida
def build(out: Path) -> None:
    QGuiApplication.instance() or QGuiApplication([])
    files: dict[str, bytes] = {}
    for path in sorted((PWA / "web").rglob("*")):
        if path.is_file() and path.name != "sw.js":
            files[path.relative_to(PWA / "web").as_posix()] = path.read_bytes()
    files["kreix.zip"] = python_bundle()
    files["js/icons.js"] = icons_js()
    files["js/logo.js"] = logo_js()
    files.update(vendor_js())
    pyodide = pyodide_files()
    for name, data in wheels().items():
        files[f"wheels/{name}"] = data
    for font in sorted((ROOT / "assets" / "fonts").glob("*.ttf")):
        files[f"fonts/{font.name}"] = font.read_bytes()
    files["fonts/LICENCIAS.txt"] = (ROOT / "assets" / "fonts" / "LICENCIAS.txt").read_bytes()
    for svg in ("kreix-logotipo-oscuro.svg", "kreix-logotipo-claro.svg", "kreix-icono-oscuro.svg"):
        files[f"img/{svg}"] = (ROOT / "logo-mejorado" / svg).read_bytes()
    files["img/icon-192.png"] = icon(192)
    files["img/icon-512.png"] = icon(512)
    files["img/maskable-512.png"] = icon(512, 0.8, square=True)
    files["img/apple-touch-icon.png"] = icon(180, square=True)
    files["img/favicon-32.png"] = icon(32)
    files.update(dog_layers())

    config = {"pyodide": "pyodide/", "wheels": sorted(n for n in files if n.startswith("wheels/"))}
    files["config.json"] = json.dumps(config, indent=2).encode()

    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode() + b"\0" + files[name])
    version = digest.hexdigest()[:12]
    template = (PWA / "web" / "sw.js").read_text(encoding="utf-8")
    shell = sorted(n for n in files if not n.endswith(".txt"))
    files["sw.js"] = (template.replace("__VERSION__", version).replace("__PYODIDE__", PYODIDE)
                      .replace('["__FILES__"]', json.dumps(["./"] + shell, indent=1))
                      .replace('["__PYODIDE_FILES__"]', json.dumps(sorted(pyodide), indent=1))).encode()
    files.update(pyodide)                    # en su propia cache del service worker (ver sw.js)

    if out.exists():
        shutil.rmtree(out)
    for name, data in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    size = sum(len(d) for d in files.values())
    print(f"PWA {version}: {len(files)} archivos, {size / 1024:.0f} KB en {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUT)
