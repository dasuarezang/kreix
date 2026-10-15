"""Genera extractos de demostracion 100 % inventados (para el modo "datos de ejemplo", capturas y pruebas).

Uso por linea de comandos:  python tools/demo_data.py carpeta_destino
Crea: imagin.csv, myinvestor_operaciones.csv y myinvestor_cartera.csv
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


def eur(v: Decimal) -> str:
    return f"{v:.2f}".replace(".", ",")


def units4(v: Decimal) -> str:
    return f"{v:.4f}".replace(".", ",")


def build(out: Path) -> date:
    out.mkdir(parents=True, exist_ok=True)

    # ---- Imagin: 6 meses, saldo consistente fila a fila
    template = [  # (dia, concepto, importe)
        (1, "TRASPASO", "900.00"), (3, "MERCADONA CL DEMO", "-45.30"), (6, "ESSELUNGA DEMO", "-62.10"),
        (9, "NETFLIX.COM", "-12.99"), (12, "SPOTIFY AB", "-10.99"), (15, "URBAN CLIMBING DEMO", "-35.00"),
        (18, "BIZUM RECIBIDO", "20.00"), (22, "PIZZERIA DEMO", "-28.50"), (25, "RENFE DEMO", "-40.00"),
    ]
    rows: list[tuple[date, str, Decimal, Decimal]] = []
    balance = Decimal("150.00")
    for month in range(4, 10):
        for day, concept, amount in template:
            tweak = Decimal(month % 3) * Decimal("3.10") if Decimal(amount) < 0 and concept != "NETFLIX.COM" else 0
            value = Decimal(amount) - tweak
            balance += value
            rows.append((date(2026, month, day), concept, value, balance))
    lines = ["Concepto;Fecha;Importe;Saldo"] + [
        f"{c};{d:%d/%m/%Y};{eur(a)}EUR;{eur(b)}EUR" for d, c, a, b in reversed(rows)
    ]
    (out / "imagin.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- MyInvestor: compra mensual en dos fondos ficticios
    funds = [("Fondo Demo Mundial", "IE00DEMO0001", Decimal(100), Decimal("1.5")),
             ("Fondo Demo EEUU", "IE00DEMO0002", Decimal(50), Decimal("0.6"))]
    ops = ["Fecha Operación;Fecha Valor;Producto;ISIN;Tipo Operación;Participaciones;Valor Liquidativo;Importe (€);Estado"]
    held: dict[str, Decimal] = {f[1]: Decimal(0) for f in funds}
    spent: dict[str, Decimal] = {f[1]: Decimal(0) for f in funds}
    last_price: dict[str, Decimal] = {}
    for month in range(1, 10):
        for name, isin, base, slope in funds:
            price = base + slope * month
            amount = Decimal(300) if isin.endswith("1") else Decimal(150)
            units = (amount / price).quantize(Decimal("0.0001"))
            amount = (units * price).quantize(Decimal("0.01"))
            held[isin] += units
            spent[isin] += amount
            last_price[isin] = price
            ops.append(f"05/{month:02d}/2026;07/{month:02d}/2026;{name};{isin};Suscripción;"
                       f"{units4(units)};{eur(price)};{eur(amount)};Ejecutada")
    (out / "myinvestor_operaciones.csv").write_text("\n".join(ops) + "\n", encoding="utf-8")

    head = ("Producto;ISIN;Participaciones Totales;Precio Medio Compra (€);Valor Liquidativo Actual (€);"
            "Capital Invertido (€);Valor de Mercado (€);Plusvalía / Minusvalía (€);Rentabilidad (%)")
    port = [head]
    for name, isin, base, slope in funds:
        now = (last_price[isin] * Decimal("1.04")).quantize(Decimal("0.01"))  # el fondo cierra un 4 % por encima de la ultima compra
        market = (held[isin] * now).quantize(Decimal("0.01"))
        gain = market - spent[isin]
        port.append(f"{name};{isin};{units4(held[isin])};{eur(spent[isin] / held[isin])};{eur(now)};"
                    f"{eur(spent[isin])};{eur(market)};{eur(gain)};{eur(gain / spent[isin] * 100)}")
    (out / "myinvestor_cartera.csv").write_text("\n".join(port) + "\n", encoding="utf-8")
    return date(2026, 9, 30)


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "demo")
    print(f"Datos de demostracion en {folder} (fecha de cartera sugerida: {build(folder)})")
