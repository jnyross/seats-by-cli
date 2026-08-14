from pathlib import Path

from seatspy.site import HomePage, Site


def test_home_without_logged_in_marker_uses_signed_in_navigation(monkeypatch) -> None:
    html = (
        b'<html><input name="csrf_token" value="tok">'
        b'<a href="/user/account/">Account</a>'
        b'<form action="/reward-seat-availability" method="post"></form></html>'
    )
    site = Site(Path("unused-cookies"))
    monkeypatch.setattr(site, "_request", lambda *args, **kwargs: (200, html, "https://www.seatspy.com/"))

    home = site.home()

    assert isinstance(home, HomePage)
    assert home.logged_in is True
