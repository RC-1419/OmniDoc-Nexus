import pytest

from tests.helpers import PASSWORD


def test_signup_returns_only_public_fields(world):
    name = f"test_signup_{world.tag}"
    r = world.client.post(
        "/auth/signup", json={"username": name, "password": PASSWORD, "email": "s@example.com"})
    world.created.append(name)
    assert r.status_code == 201
    assert set(r.json()) == {"id", "username", "email"} and r.json()[
        "username"] == name   # never a password hash


def test_duplicate_username_is_a_conflict(world, alice):
    r = world.client.post(
        "/auth/signup", json={"username": alice.name, "password": PASSWORD})
    assert r.status_code == 409


@pytest.mark.parametrize("body", [
    {"username": "valid_name", "password": "short"},
    {"username": "valid_name", "password": PASSWORD, "email": "not-an-email"},
    {"username": "bad name!", "password": PASSWORD},
    {"username": "ab", "password": PASSWORD},
    {"password": PASSWORD},
])
def test_signup_checks_its_input(world, body):
    assert world.client.post("/auth/signup", json=body).status_code == 422


def test_login_gives_a_token_that_identifies_the_user(world, alice):
    me = world.client.get("/auth/me", headers=alice.headers)
    assert me.status_code == 200 and me.json()["username"] == alice.name


def test_wrong_password_and_unknown_user_look_the_same(world, alice):
    wrong = world.client.post(
        "/auth/login", data={"username": alice.name, "password": "wrong-password"})
    unknown = world.client.post(
        "/auth/login", data={"username": f"nobody_{world.tag}", "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_repeated_failed_logins_lock_the_address_out(world, alice):
    limit = world.settings.login_failures_per_15min
    codes = [world.client.post("/auth/login", data={"username": f"nobody_{world.tag}", "password": "x" * 10}).status_code
             for _ in range(limit + 2)]
    assert codes[0] == 401 and codes[-1] == 429
    # even the right password
    r = world.client.post(
        "/auth/login", data={"username": alice.name, "password": PASSWORD})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_successful_logins_are_never_slowed_down(world, alice):
    for _ in range(world.settings.login_failures_per_15min + 3):
        assert world.client.post(
            "/auth/login", data={"username": alice.name, "password": PASSWORD}).status_code == 200


def test_signup_is_limited_per_address(world, monkeypatch):
    monkeypatch.setattr(world.settings, "signup_per_hour_per_ip", 2)
    codes = []
    for i in range(3):
        name = f"test_limit{i}_{world.tag}"
        codes.append(world.client.post(
            "/auth/signup", json={"username": name, "password": PASSWORD}).status_code)
        world.created.append(name)
    assert codes == [201, 201, 429]
