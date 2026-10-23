"""Pasar los datos al movil por QR animado: el codigo fuente reconstruye los datos aunque se pierdan fotogramas."""
from __future__ import annotations

import os
import random

import pytest

from core.qr_transfer import BLOCK_SIZE, Decoder, Encoder, indices, mulberry32, pack, unpack


def test_mulberry32_matches_the_javascript_reference():
    # valores de mulberry32(1) calculados con la implementacion de pwa/web/js/qr.js
    rng = mulberry32(1)
    assert [rng() for _ in range(3)] == [2693262067, 11749833, 2265367787]


def test_pack_round_trip_and_rejects_garbage():
    data = os.urandom(5000)
    assert unpack(pack(data)) == data
    with pytest.raises(ValueError):
        unpack(b"no es kreix")


def test_even_frames_carry_one_block_in_order_and_odd_frames_mix_several():
    assert indices(7, 0, 10) == [0]
    assert indices(7, 4, 10) == [2]
    assert indices(7, 20, 10) == [0]                 # da la vuelta
    mixed = [indices(7, seq, 10) for seq in range(1, 200, 2)]
    assert all(1 <= len(c) <= 8 and len(set(c)) == len(c) for c in mixed)
    assert any(len(c) > 1 for c in mixed)


def test_decodes_in_order():
    data = os.urandom(BLOCK_SIZE * 7 + 123)
    enc, dec = Encoder(data), Decoder()
    for frame in enc.frames():
        dec.add(frame)
        if dec.done:
            break
    assert dec.result() == data


def test_decodes_with_lost_frames_and_a_late_start():
    data = os.urandom(BLOCK_SIZE * 40 + 7)
    enc, dec = Encoder(data, transfer_id=1234), Decoder()
    chance = random.Random(5)
    used = 0
    for frame in enc.frames(start=55):              # el movil empieza a mirar a mitad de la secuencia
        if chance.random() < 0.3:                   # y pierde un 30 % de los fotogramas
            continue
        used += 1
        dec.add(frame)
        if dec.done:
            break
    assert dec.result() == data
    assert used < enc.k * 2.2                       # sin necesitar mucho mas que los bloques que hay


def test_a_frame_from_another_transfer_starts_over():
    first, second = Encoder(b"a" * 1000), Encoder(b"b" * 1000)
    dec = Decoder()
    dec.add(first.frame(0))
    dec.add(second.frame(0))
    assert dec.transfer_id == second.transfer_id and len(dec.known) == 1
    assert not dec.add(b"basura")


def test_export_view_shows_an_animated_qr_that_carries_the_whole_export(window, monkeypatch):
    from ui import qr_dialog

    shown = []
    monkeypatch.setattr(qr_dialog.QrTransferDialog, "exec", lambda self: shown.append(self) or 0)
    view = window.export_view
    view.show_qr()
    assert not shown                                   # sin datos no hay nada que pasar
    window._svc.demo.load()
    view.show_qr()
    dialog = shown[0]
    first = [row[:] for row in dialog.code._matrix]
    dialog.advance()
    assert dialog.code._matrix != first                 # cada fotograma es un codigo distinto
    dec = Decoder()
    for frame in dialog.encoder.frames():
        dec.add(frame)
        if dec.done:
            break
    assert unpack(dec.result())[:2] == b"PK"           # lo que viaja es un .kreix (zip) completo
    dialog.done(0)
    assert not dialog.timer.isActive()
