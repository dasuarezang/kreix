"""Metas de ahorro: calculo, servicio, Inicio y gestion."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from core.goals import Goal, monthly_needed, months_left
from data.database import init_db, make_engine, make_session_factory
from services.dashboard_service import DashboardService
from services.goals_service import GoalError, GoalsService
from services.import_service import ImportService
from ui.goals_dialog import GoalsDialog

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 15)


@pytest.fixture()
def factory():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return make_session_factory(engine)


def test_goal_progress_and_monthly_need():
    g = Goal(1, "Vacaciones", D(1000), D(250), date(2027, 2, 20))
    assert g.fraction == 0.25 and g.remaining == D(750) and not g.reached
    assert months_left(g.deadline, TODAY) == 4
    assert monthly_needed(g, TODAY) == D("187.50")
    assert Goal(2, "x", D(100), D(150)).fraction == 1.0 and Goal(2, "x", D(100), D(150)).reached
    assert monthly_needed(Goal(3, "x", D(100), D(0), date(2026, 1, 1)), TODAY) is None          # ya vencio
    assert monthly_needed(Goal(4, "x", D(100), D(0)), TODAY) is None                              # sin fecha


def test_goals_service_crud(factory):
    svc = GoalsService(factory)
    gid = svc.save("  Vacaciones  ", D(1000), D(100), date(2027, 1, 1))
    assert [(g.name, g.target, g.saved) for g in svc.goals()] == [("Vacaciones", D(1000), D(100))]
    svc.contribute(gid, D(250))
    assert svc.goals()[0].saved == D(350)
    svc.contribute(gid, D(-9999))
    assert svc.goals()[0].saved == D(0)                                   # nunca baja de cero
    svc.save("Vacaciones", D(2000), D(5), None, goal_id=gid)
    assert svc.goals()[0].target == D(2000) and svc.goals()[0].deadline is None
    with pytest.raises(GoalError):
        svc.save("", D(100))
    with pytest.raises(GoalError):
        svc.save("Algo", D(0))
    svc.delete(gid)
    assert svc.goals() == []


def test_dashboard_carries_the_goals(factory):
    ImportService(factory).import_files([FIX / "imagin_sample.csv"], TODAY)
    GoalsService(factory).save("Coche", D(5000), D(500))
    data = DashboardService(factory).load()
    assert [g.name for g in data.goals] == ["Coche"]


def test_goals_dialog_actions_and_home_panel(window):
    window.start_demo()
    panel = window.dashboard.goals
    dialog = GoalsDialog(window._svc.goals, window)
    assert dialog.add_goal("Vacaciones", D(1000), D(250), date(2027, 6, 1))
    assert not dialog.add_goal("", D(10))
    goal = window._svc.goals.goals()[0]
    dialog.contribute(goal.id, D(100))
    assert window._svc.goals.goals()[0].saved == D(350) and dialog.did_change
    window.refresh()
    window.dashboard.set_data(window._svc.dashboard.load())
    assert [g.name for g in panel.bars._goals] == ["Vacaciones"]
    assert "Faltan" in panel.bars.note(panel.bars._goals[0]) and panel.subtitle.text() == "1 meta"
    dialog.delete_goal(goal.id)
    window.dashboard.set_data(window._svc.dashboard.load())
    assert panel.bars._goals == [] and panel.manage_button.text() == "Crear una meta"
    dialog.close()
