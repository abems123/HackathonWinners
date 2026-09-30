"""Semantic regression checks for all eight teammate evaluation scenarios.

The assertions inspect the application's actual effective passage set, not answers
copied from the evaluation file. The app deliberately has no free-text question box.
"""
import json
from pathlib import Path

import pytest

from core.domain.effective import effective_pins
from core.models import Client, Pin, User

QUESTIONS = json.loads((Path(__file__).resolve().parent.parent / "data/eval_questions.json").read_text(encoding="utf-8"))["questions"]
pytestmark = pytest.mark.django_db
TOPICS = {"Q1": "payroll-input", "Q2": "payroll-input", "Q3": "payroll-input", "Q4": "handover",
          "Q5": "payslips", "Q6": "expenses", "Q7": "payroll-input", "Q8": "payroll-input"}


@pytest.mark.parametrize("question", QUESTIONS, ids=[row["id"] for row in QUESTIONS])
def test_evaluation_scenario(seeded, question):
    qid = question["id"]
    name = "Bakkerij Janssens"
    if qid == "Q2":
        name = "Brouwerij De Kroon"
    elif qid == "Q7":
        name = "Maison Laurent"
    elif qid == "Q8":
        name = "Garage Verhaeghe"
    client = Client.objects.get(name=name)
    active, excluded, _ = effective_pins(list(Pin.objects.filter(topic__slug=TOPICS[qid])), client.pk, client.profile)
    text = "\n".join(pin.quote for pin in active)
    if qid in {"Q1", "Q3", "Q8"}:
        assert "17:00 on the 5th working day" in text
        assert "Wed 7 Oct 2026" in text
        assert any(pin.source.external_id == "BE-PAY-CHK-2022" and pin.status == "NEEDS_REVIEW" for pin in active)
        assert any(pin.source.external_id == "NL-PAY-PROC-001" for pin in excluded)
        assert not any(pin.source.external_id.startswith("TEAMS-") for pin in active)
    elif qid == "Q2":
        exception = next(pin for pin in active if pin.base_id)
        assert "7th working day" in exception.quote and "December 2026" in exception.quote
        assert exception.status == "NEEDS_REVIEW"
        assert exception.base.source.external_id == "BE-PAY-PROC-001"
        assert any(pin.source.external_id == "CLIENT-DEKROON" and pin.status == "NEEDS_REVIEW" for pin in active)
    elif qid == "Q4":
        current = next(pin for pin in active if pin.source.external_id == "BE-HANDOVER-2026")
        assert "Shadow one full payroll run" in current.quote and "Teams threads" in current.quote
        assert current.status == "CONFIRMED"
        assert next(pin for pin in active if pin.source.external_id == "BE-HANDOVER-2019").status == "NEEDS_REVIEW"
    elif qid == "Q5":
        assert "10th working day" in text and "Wed 14 Oct 2026" in text
        assert all(pin.status == "CONFIRMED" for pin in active)
    elif qid == "Q6":
        assert "20th of the month following the expense" in text and "manager approval" in text
        assert all(pin.status == "CONFIRMED" for pin in active)
    elif qid == "Q7":
        assert not active
        assert {"BE-PAY-PROC-001", "NL-PAY-PROC-001"}.issubset({pin.source.external_id for pin in excluded})
        assert User.objects.get(username="anne").is_active
