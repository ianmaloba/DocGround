"""All release tests use injected model responses and package-index answers."""

import pytest


@pytest.fixture(autouse=True)
def forbid_unmocked_http(monkeypatch):
    def reject_request(*args, **kwargs):
        pytest.fail("Tests must inject HTTP responses; live network requests are disabled")

    monkeypatch.setattr("requests.sessions.Session.request", reject_request)
