import re

import pytest


def test_health_is_the_one_unversioned_endpoint(world):
    r = world.client.get("http://testserver/health")
    assert r.status_code == 200 and r.json(
    ) == {"status": "ok"} and r.headers["x-api-version"] == "1"


@pytest.mark.parametrize("path", ["/providers", "/documents", "/auth/login", "/chat"])
def test_nothing_answers_outside_v1(world, path):
    assert world.client.get("http://testserver" +
                            path).status_code in (404, 405)


def test_provider_list_has_no_secrets_and_safe_headers(world):
    r = world.client.get("/providers")
    assert r.status_code == 200 and set(
        r.json()) == {"llm", "default_llm", "email"}
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method,path", [("get", "/documents"), ("get", "/people"), ("get", "/documents/1/file"),
                                         ("delete", "/documents/1"), ("get", "/auth/me")])
def test_private_get_and_delete_need_a_login(world, method, path):
    assert getattr(world.client, method)(path).status_code == 401


def test_private_posts_need_a_login(world):
    assert world.client.post(
        "/chat", json={"message": "hi"}).status_code == 401
    assert world.client.post("/chat/confirm-email",
                             json={"token": "x" * 20}).status_code == 401
    assert world.client.post(
        "/documents", files={"file": ("a.pdf", b"%PDF", "application/pdf")}).status_code == 401
    assert world.client.post("/people", json={"name": "x"}).status_code == 401


def test_a_made_up_token_is_refused(world):
    assert world.client.get(
        "/documents", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_metrics_page_has_route_templates_and_no_personal_data(world, alice):
    world.client.get(f"/documents/{alice.doc.id}/file", headers=alice.headers)
    r = world.client.get("http://testserver/metrics")
    assert r.status_code == 200 and "http_requests_total" in r.text
    # the health check is not counted
    assert 'handler="/health"' not in r.text
    # templates only, never real ids
    assert not re.search(r"/documents/\d", r.text)
    for secret in (alice.token, alice.name, alice.doc.number, alice.doc.number.replace(" ", ""), "Bearer"):
        assert secret not in r.text
