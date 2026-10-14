"""Enumeraciones del dominio. Sin dependencias: las usan core, etl, data y ui."""
from __future__ import annotations

import enum


class Bank(str, enum.Enum):
    IMAGIN = "imagin"
    MYINVESTOR = "myinvestor"


class AccountKind(str, enum.Enum):
    CHECKING = "checking"        # liquidez (Imagin)
    INVESTMENT = "investment"    # cartera (MyInvestor)


class TxCategory(str, enum.Enum):
    INCOME = "ingresos"
    GROCERIES = "supermercado"
    DINING = "restaurantes"
    SUBSCRIPTIONS = "suscripciones"
    LEISURE = "ocio"
    TRANSPORT = "transporte"
    HOUSING = "vivienda"
    HEALTH = "salud"
    P2P = "bizum"                                 # pagos entre personas
    TRANSFER = "traspaso"                         # movimiento entre cuentas propias (neutro)
    INVESTMENT_TRANSFER = "aportacion_inversion"  # traspaso hacia MyInvestor
    OTHER = "otros"
    UNCATEGORIZED = "sin_categoria"


class OperationType(str, enum.Enum):
    BUY = "compra"
    SELL = "venta"
    DIVIDEND = "dividendo"
    FEE = "comision"
    DEPOSIT = "ingreso_efectivo"
    WITHDRAWAL = "retirada_efectivo"
