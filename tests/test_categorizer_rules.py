"""Reglas de serie del categorizador: comercios habituales, ruido del extracto, signo y nombres de persona."""
from datetime import date
from decimal import Decimal as D

import pytest

from core.categorizer import Categorizer
from core.entities import TransactionDraft
from core.enums import Bank, TxCategory as C
from core.suggestions import suggest_rules

cat = Categorizer()


@pytest.mark.parametrize("concept, amount, expected", [
    ("Glovo 11OCT B4GFD", "-35.29", C.DINING),
    ("MERCADONA CL DE T", "-3.30", C.GROCERIES),
    ("CONDIS BARCELONA", "-12", C.GROCERIES),
    ("UBER EATS HELP.UBER", "-14", C.DINING),
    ("UBER *TRIP", "-9", C.TRANSPORT),
    ("PAYPAL *SPOTIFY", "-10.99", C.SUBSCRIPTIONS),
    ("AMAZON PRIME*2K4", "-4.99", C.SUBSCRIPTIONS),
    ("AMZN Mktp ES*1A2B3", "-23", C.OTHER),
    ("T-MOBILITAT RECARREGA", "-20", C.TRANSPORT),
    ("BAR LA ESQUINA", "-3", C.DINING),
    ("FARMACIA LLUIS", "-8", C.HEALTH),
    ("MOVISTAR FUSION", "-60", C.HOUSING),
    ("DNI/PASAPORTE L'H", "-12", C.OTHER),
    ("FOTOPRIX BCN JULI", "-13.98", C.OTHER),
    ("ZARA BARCELONA", "-30", C.OTHER),
])
def test_common_merchants(concept, amount, expected):
    assert cat.categorize(concept, D(amount)) is expected


def test_short_keywords_must_end_the_word():
    assert cat.categorize("BARCELONA CENTRO", D(-5)) is C.UNCATEGORIZED       # BAR$ no casa con BARCELONA
    assert cat.categorize("ZARAGOZA TAPAS", D(-5)) is C.DINING                # por TAPAS, no por ZARA
    assert cat.categorize("METROPOLITAN CLUB", D(-5)) is C.UNCATEGORIZED       # METRO$ no casa con METROPOLITAN
    assert cat.categorize("BP GASOLINERA", D(-5)) is C.TRANSPORT


def test_salary_is_only_recognised_when_it_comes_in():
    assert cat.categorize("NOMINA EMPRESA SL", D(1200)) is C.SALARY
    assert cat.categorize("TRANSFERENCIA NOMINA JUNIO", D(1200)) is C.SALARY
    assert cat.categorize("NOMINA EMPRESA SL", D(-1200)) is C.UNCATEGORIZED     # una nomina negativa se revisa a mano


def test_a_refund_from_the_tax_office_is_income_not_other():
    assert cat.categorize("DEVOLUCION AEAT 2025", D(300)) is C.INCOME
    assert cat.categorize("AEAT MODELO 303", D(-300)) is C.OTHER


def test_unknown_concepts_keep_their_old_fallback():
    assert cat.categorize("WELCOME", D(-68.9)) is C.UNCATEGORIZED
    assert cat.categorize("WELCOME", D(10)) is C.INCOME


def test_names_glued_in_camel_case_are_payments_between_people():
    assert cat.categorize("MariaLopezGarcia", D(-50)) is C.P2P
    assert cat.categorize("MariaLopezGarcia", D(25)) is C.P2P
    assert cat.categorize("MediaMarkt", D(-50)) is C.OTHER                    # una marca no es una persona
    assert cat.categorize("PlayStationStore", D(-50)) is C.LEISURE            # las reglas van antes que el nombre


def test_the_user_can_still_mark_a_concept_as_salary():
    c = Categorizer(user_rules=[("REINT", C.SALARY)])
    assert c.categorize("REINT CORP SA", D(900)) is C.SALARY


def test_a_suggestion_keeps_the_whole_concept_and_counts_variants():
    def tx(desc, day):
        return TransactionDraft(Bank.IMAGIN, date(2026, 9, day), desc, D("-5"), None, C.UNCATEGORIZED, f"h{day}", "t")

    found = suggest_rules([tx("REINT CAJERO 123 BCN", 1), tx("REINT SABADELL 77", 2), tx("REINT SABADELL 99", 3)])
    assert found[0].keyword == "REINT"
    assert found[0].example == "REINT SABADELL 99"
    assert found[0].variants == 3


def _reference(description: str, amount: D, user_rules=()):
    """La definicion de las reglas, escrita de la forma mas simple (una expresion regular por palabra): el categorizador indexado
    tiene que dar siempre lo mismo."""
    import re

    from core.categorizer import _PERSON_NAME, _POSITIVE_ONLY, DEFAULT_RULES, normalize

    def pattern(keyword):
        k = keyword.strip()
        return re.compile(r"(?<![A-Z0-9])" + re.escape(k.removesuffix("$")) + (r"(?![A-Z0-9])" if k.endswith("$") else ""))

    text = normalize(description)
    rules = [(cat, (kw,), False) for kw, cat in user_rules] + [(cat, kws, cat in _POSITIVE_ONLY) for cat, kws in DEFAULT_RULES]
    for cat, kws, positive_only in rules:
        if (amount > 0 or not positive_only) and any(pattern(k).search(text) for k in kws):
            return cat
    if _PERSON_NAME.match(description.strip()):
        return C.P2P
    return C.INCOME if amount > 0 else C.UNCATEGORIZED


def test_the_indexed_categorizer_gives_exactly_what_the_plain_rules_say():
    import random
    import string

    from core.categorizer import DEFAULT_RULES

    rng = random.Random(3)
    keywords = [k.removesuffix("$") for _, kws in DEFAULT_RULES for k in kws]
    pieces = keywords + ["COMPRA", "TARJ", "BCN", "SL", "DE", "LA", "1234", "REF", "BARCELONA", "ZARAGOZA", "METROPOLITAN"]
    user = [("PANADERIA", C.DINING), ("REINT", C.SALARY), ("UBER", C.OTHER)]
    with_user = Categorizer(user_rules=user)
    plain = Categorizer()
    for _ in range(4000):
        words = [rng.choice(pieces) + (rng.choice(["", "", "S", "X", "123"])) for _ in range(rng.randint(1, 4))]
        text = rng.choice([" ", "*", "-", "/"]).join(words) + rng.choice(["", " " + "".join(rng.choices(string.digits, k=5))])
        amount = D(rng.choice([-30, 30]))
        assert plain.categorize(text, amount) is _reference(text, amount), (text, amount)
        assert with_user.categorize(text, amount) is _reference(text, amount, user), (text, amount)
