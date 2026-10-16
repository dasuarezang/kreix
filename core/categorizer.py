"""Categorizacion por reglas (diccionario de palabras clave). Logica pura.

Las reglas se evaluan en orden: la primera que coincide gana. Una palabra clave
coincide si aparece al inicio de una palabra del concepto (sin acentos, en mayusculas),
asi "SUPERMERC" casa con "PROXIM SUPERMERCA" pero "DIA" no casa con "MEDIAMARKT".
"""
from __future__ import annotations

import re
from functools import lru_cache
import unicodedata
from collections.abc import Sequence
from decimal import Decimal

from core.enums import TxCategory

Rules = list[tuple[TxCategory, tuple[str, ...]]]

DEFAULT_RULES: Rules = [
    (TxCategory.INVESTMENT_TRANSFER, ("MYINVESTOR",)),
    (TxCategory.TRANSFER, ("TRASPASO",)),
    (TxCategory.P2P, ("BIZUM", "TRANSFERENCIA A FAVOR", "TRANSFERENCIA EMITIDA")),
    (TxCategory.SALARY, ("NOMINA", "SALARIO", "SALARI", "SUELDO", "PAYROLL", "SALARY", "RETRIBUCION", "PAGA EXTRA", "PAGA DE JUNIO")),
    (TxCategory.INCOME, (
        "PENSION", "PRESTACION", "SEPE$", "TRANSFERENCIA RECIBIDA",
        "TRANSFERENCIA DE", "INTERESES", "RENDIMIENTO", "DIVIDENDO", "INGRESO EFECTIVO", "INGRES EFECTIU", "DEVOLUCION AEAT",
        "DEVOLUCION HACIENDA", "AGENCIA TRIBUTARIA DEVOL",
    )),
    (TxCategory.SUBSCRIPTIONS, (
        "APPLE.COM/BILL", "ANTHROPIC", "OPENAI", "CHATGPT", "CLAUDE.AI", "MIDJOURNEY", "SPOTIFY", "NETFLIX", "HBO", "MAX.COM",
        "DISNEY", "YOUTUBE", "AMAZON PRIME", "AMZN PRIME", "PRIME VIDEO", "PARAMOUNT", "FILMIN", "DAZN", "TWITCH", "CRUNCHYROLL",
        "SPLIIIT", "ICLOUD", "ITUNES", "APPLE MUSIC", "GOOGLE ONE", "GOOGLE STORAGE", "GOOGLE YOUTUBE", "DROPBOX", "ADOBE",
        "MICROSOFT 365", "OFFICE 365", "GITHUB", "NOTION", "CANVA", "FIGMA", "PATREON", "AUDIBLE", "KINDLE UNLIMITED", "DUOLINGO",
        "NORDVPN", "EXPRESSVPN", "PROTON", "1PASSWORD", "LASTPASS", "LINKEDIN", "TIDAL", "DEEZER", "WUOLAH", "SKYSHOWTIME",
    )),
    (TxCategory.GROCERIES, (
        "MERCADONA", "ESSELUNGA", "SUPERMERC", "SUPERMERCAT", "SUPERCOR", "HIPERCOR", "CARREFOUR", "LIDL", "ALDI", "BONPREU", "BON AREA",
        "BONAREA", "CONSUM$", "ALCAMPO", "EROSKI", "CAPRABO", "CONAD", "COOP$", "CONDIS", "GADIS", "FROIZ", "AHORRAMAS", "SUPECO",
        "MASYMAS", "MAS Y MAS", "COVIRAN", "DINOSOL", "HIPERDINO", "SORLI", "SPAR$", "ALIMENTACION", "ALIMENTACIO",
        "FRUTERIA", "FRUITERIA", "VERDULERIA", "CARNICERIA", "CARNISSERIA", "PESCADERIA", "PEIXATERIA", "ULTRAMARINOS", "COLMADO",
        "MERCAT$", "MERCADO$", "PASTISSERIA",
    )),
    (TxCategory.DINING, (
        "GLOVO", "UBER EATS", "UBEREATS", "JUST EAT", "JUSTEAT", "DELIVEROO", "TOO GOOD TO GO", "PIZZERIA", "RESTAURA", "MCDONALD",
        "BURGER", "KFC", "TELEPIZZA", "DOMINO", "PAPA JOHN", "FOSTER", "VIPS$", "TGB$", "FIVE GUYS", "SUBWAY", "DUNKIN", "TIM HORTON",
        "100 MONTADITOS", "CAFE", "CAFETERIA", "COFFEE", "STARBUCKS", "TRATTORIA", "BAR$", "TAPAS", "TABERNA", "CERVECERIA", "CERVESERIA",
        "BRASERIA", "HELADERIA", "GELATERIA", "PASTELERIA", "CHURRERIA", "KEBAB", "SUSHI", "RAMEN", "POKE$", "WOK$", "BOCADILL",
        "BOCATA", "XOCOLATERIA", "FORN$",
    )),
    (TxCategory.TRANSPORT, (
        "TRENORD", "RENFE", "OUIGO", "IRYO", "ITALO$", "TRENITALIA", "TRAINLINE", "FGC$", "RODALIES", "CLESS TICKET", "AEROPUERTO",
        "AEROPORT", "AENA", "UBER", "CABIFY", "FREE NOW", "FREENOW", "TAXI", "BOLT$", "BLABLACAR", "BICING", "TMB", "T-MOBILITAT",
        "T-CASUAL", "TRAM$", "EMT$", "METRO$", "AUTOBUS", "FLIXBUS", "ALSA$", "RYANAIR", "VUELING", "IBERIA", "EASYJET", "WIZZ",
        "TRANSAVIA", "NORWEGIAN", "VOLOTEA", "AIR EUROPA", "LUFTHANSA", "GASOLINERA", "GASOLINA", "REPSOL", "CEPSA", "SHELL$",
        "GALP", "PETROPRIX", "BP$", "PLENITUDE", "PARKING", "APARCAMENT", "APARCAMIENTO", "PEAJE", "AUTOPISTA", "ABERTIS", "VIA T",
        "ITV$", "NORAUTO", "LIME$", "DOTT$", "ZITY", "MOTOSHARING",
    )),
    (TxCategory.LEISURE, (
        "CLIMBING", "BOULDER", "ROCODROM", "CINE", "CINESA", "YELMO", "KINEPOLIS", "FILMOTECA", "STEAM", "EPIC GAMES", "PLAYSTATION",
        "XBOX", "NINTENDO", "BLIZZARD", "TICKETMASTER", "TICKETEA", "ENTRADAS", "ENTRADES", "ATRAPALO", "EVENTBRITE", "FEVER$",
        "GYM", "GIMNASIO", "BASIC-FIT", "BASICFIT", "VIVAGYM", "MCFIT", "ONFIT", "DREAMFIT", "FITNESS", "PISCINA", "PADEL", "TENIS",
        "BOWLING", "KARTING", "ESCAPE ROOM", "PORTAVENTURA", "TIBIDABO", "ZOO$", "ACUARIO", "DECATHLON", "MUSEO", "MUSEU", "TEATRO",
        "TEATRE", "DISCOTECA", "LLIBRERIA", "LIBRERIA", "CASA DEL LIBRO", "AIRBNB", "BOOKING", "HOTEL", "HOSTAL", "EDREAMS", "KAYAK",
        "HOSTELWORLD",
    )),
    (TxCategory.HOUSING, (
        "RENTALS", "ALQUILER", "LLOGUER", "FIANZA", "HIPOTECA", "COMUNIDAD", "COMUNITAT", "ENDESA", "IBERDROLA", "NATURGY", "FENOSA",
        "HOLALUZ", "OCTOPUS ENERGY", "SOM ENERGIA", "GAS NATURAL", "AGUAS", "AIGUES", "AGBAR", "CANAL DE ISABEL", "MOVISTAR", "VODAFONE",
        "ORANGE$", "MASMOVIL", "YOIGO", "DIGI$", "PEPEPHONE", "LOWI", "JAZZTEL", "SIMYO", "FINETWORK", "LYCAMOBILE", "TELEFONICA",
        "IKEA", "LEROY MERLIN", "BRICO", "BAUHAUS", "FERRETERIA",
    )),
    (TxCategory.HEALTH, (
        "FARMACIA", "PARAFARMACIA", "CLINICA", "CLINIC$", "DENTAL", "DENTISTA", "ODONTO", "OPTICA", "OPTICO", "MULTIOPTICAS", "AFFLELOU",
        "HOSPITAL", "FISIO", "OSTEO", "PODOLOG", "PSICOLOG", "PSIQUIATR", "DERMATOL", "LABORATORI", "SANITAS", "ADESLAS", "ASISA", "DKV",
        "QUIRON", "MUTUA",
    )),
    (TxCategory.OTHER, (
        "ZARA$", "H&M", "PULL&BEAR", "PULL AND BEAR", "BERSHKA", "STRADIVARIUS", "MASSIMO DUTTI", "UNIQLO", "PRIMARK", "MANGO$", "SHEIN",
        "VINTED", "WALLAPOP", "ZALANDO", "ASOS$", "AMAZON", "AMZN", "ALIEXPRESS", "TEMU$", "EBAY", "MEDIAMARKT", "MEDIA MARKT",
        "PCCOMPONENTES", "PC COMPONENTES", "FNAC", "WORTEN", "CORTE INGLES", "APPLE STORE", "SEPHORA", "DOUGLAS$", "PRIMOR$", "DROGUERIA",
        "PELUQUER", "BARBER", "ESTETICA", "VETERINAR", "KIWOKO", "ZOOPLUS", "TIENDANIMAL", "CORREOS", "SEUR$", "MRW$", "DHL$", "UPS$",
        "PAPELERIA", "COPISTERIA", "FOTOPRIX", "PHOTOMATON", "UNIVERSIDAD", "UNIVERSITAT", "MATRICULA", "ACADEMIA", "UDEMY", "COURSERA",
        "AJUNTAMENT", "AYUNTAMIENTO", "HACIENDA", "AEAT", "AGENCIA TRIBUTARIA", "DGT$", "TRAFICO", "TASA$", "IBI$", "IVTM", "SEGURIDAD SOCIAL",
        "GENERALITAT", "DNI$", "PASAPORT", "NOTARI", "SEGURO", "MAPFRE", "LINEA DIRECTA", "ALLIANZ", "GENERALI", "COMISION", "COMISIO",
        "MANTENIMIENTO CUENTA", "CAJERO", "REINTEGRO", "RETIRADA EFECTIVO", "ATM$",
    )),
]

# Las reglas de serie de estas categorias solo valen para ingresos (una "nomina" negativa es un error que se revisa a mano).
_POSITIVE_ONLY = frozenset({TxCategory.INCOME, TxCategory.SALARY})

# Dos o mas palabras pegadas en CamelCase sin ninguna regla ("AnaGarciaLopez"): el extracto escribe asi el nombre de una persona.
_PERSON_NAME = re.compile(r"^(?:[A-Z\u00c0-\u00dd][a-z\u00df-\u00ff'\u2019]{2,}){3,4}$")


@lru_cache(maxsize=65536)          # funcion pura y los mismos conceptos se repiten mucho (comercios, suscripciones)
def normalize(text: str) -> str:
    """Mayusculas, sin acentos y espacios colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().upper()


_WORD_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def _index(rules: Rules, positive_only: frozenset[TxCategory], first: int) -> dict[str, list[tuple[int, str, bool, TxCategory, bool]]]:
    """Las palabras clave agrupadas por sus dos primeras letras: (orden de la regla, palabra, ha de terminar ahi, categoria, solo ingresos).
    `first` es el numero de orden de la primera regla de la lista."""
    table: dict[str, list[tuple[int, str, bool, TxCategory, bool]]] = {}
    for order, (category, keywords) in enumerate(rules, start=first):
        for keyword in keywords:
            k = keyword.strip()
            exact = k.endswith("$")
            word = k.removesuffix("$")
            if word:
                table.setdefault(word[:2], []).append((order, word, exact, category, category in positive_only))
    return table


class Categorizer:
    """`user_rules` (palabra clave -> categoria) se evaluan antes que las de serie.

    Una palabra clave coincide al principio de una palabra del concepto (un '$' final exige ademas que la palabra acabe ahi).
    En vez de probar cada regla contra el texto (cientos de patrones por movimiento), se mira cada comienzo de palabra y solo
    las palabras clave que empiezan igual: unas 20 veces mas rapido con extractos de miles de conceptos distintos."""

    def __init__(self, rules: Rules | None = None, user_rules: Sequence[tuple[str, TxCategory]] = ()) -> None:
        own: Rules = [(cat, (kw,)) for kw, cat in user_rules]
        self._table = _index(own, frozenset(), 0)
        for key, entries in _index(rules or DEFAULT_RULES, _POSITIVE_ONLY, len(own)).items():
            self._table.setdefault(key, []).extend(entries)
        self._memo: dict[tuple[str, bool], TxCategory] = {}      # el resultado solo depende del concepto y del signo

    def categorize(self, description: str, amount: Decimal) -> TxCategory:
        key = (description, amount > 0)
        found = self._memo.get(key)
        if found is None:
            found = self._memo[key] = self._categorize(description, amount)
        return found

    def _categorize(self, description: str, amount: Decimal) -> TxCategory:
        text = normalize(description)
        best: tuple[int, TxCategory] | None = None
        table, income = self._table, amount > 0
        for start in range(len(text)):
            if start and text[start - 1] in _WORD_CHARS:
                continue                                          # no es el comienzo de una palabra
            for order, word, exact, category, positive_only in table.get(text[start:start + 2], ()):
                if best is not None and order >= best[0]:
                    continue
                if (income or not positive_only) and text.startswith(word, start) and (
                        not exact or text[start + len(word):start + len(word) + 1] not in _WORD_CHARS):
                    best = (order, category)
        if best is not None:
            return best[1]
        if _PERSON_NAME.match(description.strip()):
            return TxCategory.P2P
        # Sin regla: un ingreso desconocido es ingreso; un gasto queda para revision manual.
        return TxCategory.INCOME if amount > 0 else TxCategory.UNCATEGORIZED
