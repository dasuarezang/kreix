# -*- mode: python ; coding: utf-8 -*-
"""Empaqueta Kreix como programa de Windows (carpeta dist/Kreix con Kreix.exe). Se lanza con packaging/build.ps1."""
import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
VERSION = re.search(r'VERSION = "([\d.]+)"', (ROOT / "ui" / "whats_new.py").read_text(encoding="utf-8")).group(1)
NUMBERS = tuple((int(n) for n in (VERSION.split(".") + ["0", "0", "0"])[:3])) + (0,)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMBERS, prodvers=NUMBERS, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "Kreix"),
            StringStruct("FileDescription", "Kreix: tus finanzas personales, en tu equipo"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "Kreix"),
            StringStruct("OriginalFilename", "Kreix.exe"),
            StringStruct("ProductName", "Kreix"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "assets" / "fonts"), "assets/fonts"),
        (str(ROOT / "assets" / "dogs"), "assets/dogs"),
        (str(ROOT / "logo-mejorado"), "logo-mejorado"),
    ],
    # Los idiomas se cargan por nombre (importlib): hay que decirselo a PyInstaller.
    hiddenimports=["core.locales.ca", "core.locales.en", "ui.help_texts.ca", "ui.help_texts.en"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "pytest", "tkinter", "unittest", "pydoc", "doctest", "test",
        "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL",
        "PySide6.QtDBus", "PySide6.QtTest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Kreix",
    debug=False,
    strip=False,
    upx=False,
    console=False,                                          # programa de ventanas: sin consola negra detras
    icon=str(ROOT / "logo-mejorado" / "favicon.ico"),
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Kreix")
