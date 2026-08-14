from __future__ import annotations

import pytest

from seatspy.types import Csrf, Iata, Password, Query


def test_password_redacts_repr_and_str() -> None:
    password = Password("hunter2-secret")
    assert "hunter2-secret" not in repr(password)
    assert "hunter2-secret" not in str(password)
    assert password.reveal() == "hunter2-secret"


def test_csrf_redacts_repr_and_str() -> None:
    csrf = Csrf("csrf-token-value")
    assert "csrf-token-value" not in repr(csrf)
    assert "csrf-token-value" not in str(csrf)
    assert csrf.reveal() == "csrf-token-value"


def test_query_parse_accepts_ba_lhr_jfk() -> None:
    query = Query.parse(
        airline="ba",
        origin="lhr",
        destination="jfk",
        direction="one-way",
        cabin="business",
        from_date="2026-09-01",
        to_date="2026-09-30",
    )
    assert query.airline.code == "BA"
    assert query.origin.code == "LHR"
    assert query.destination.code == "JFK"


def test_query_parse_rejects_same_airports() -> None:
    with pytest.raises(ValueError, match="must differ"):
        Query.parse(
            airline="BA",
            origin="LHR",
            destination="LHR",
            direction="one-way",
            cabin="business",
            from_date="2026-09-01",
            to_date="2026-09-30",
        )


def test_query_parse_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match="on or before"):
        Query.parse(
            airline="BA",
            origin="LHR",
            destination="JFK",
            direction="one-way",
            cabin="business",
            from_date="2026-09-30",
            to_date="2026-09-01",
        )


def test_iata_parse_rejects_short_code() -> None:
    with pytest.raises(ValueError, match="three uppercase"):
        Iata.parse("LH")
