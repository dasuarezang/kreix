"""Ayuda: cada termino es un desplegable; la explicacion solo se ve al pulsarlo (y el «?» abre el suyo ya desplegado)."""
from __future__ import annotations

from ui.help_content import SECTIONS


def test_section_terms_start_folded_and_open_on_click(window):
    view = window.help_view
    view.open_section(SECTIONS[0])
    assert view.items and not any(item.expanded for item in view.items)
    assert all(item.body.isHidden() for item in view.items)
    first = view.items[0]
    first.toggle.click()
    assert first.expanded and not first.body.isHidden()
    assert not view.items[1].expanded                 # solo se abre el pulsado
    first.toggle.click()
    assert not first.expanded and first.body.isHidden()


def test_question_mark_opens_its_term_already_unfolded(window):
    window.open_help_term("Patrimonio neto")
    open_terms = [item.entry.term for item in window.help_view.items if item.expanded]
    assert open_terms == ["Patrimonio neto"]
