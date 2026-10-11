"""'Email my document' is two steps: chat prepares it, and nothing is sent until the user confirms."""


def prepare(world, user, to="someone@example.com"):
    r = world.client.post("/chat", headers=user.headers,
                          json={"message": f"Please email my Aadhaar to {to}"})
    assert r.status_code == 200, r.text
    return r.json()["email_action"]


def confirm(world, user, token):
    return world.client.post("/chat/confirm-email", headers=user.headers, json={"token": token})


def test_preparing_sends_nothing(world):
    user = world.user_with_aadhaar("prep")
    before = len(world.sent)
    action = prepare(world, user)
    assert action["to"] == "someone@example.com" and action["document_id"] == user.doc.id
    assert len(world.sent) == before


def test_confirming_sends_once_with_the_document_attached(world):
    user = world.user_with_aadhaar("send")
    action = prepare(world, user)
    before = len(world.sent)
    r = confirm(world, user, action["token"])
    assert r.status_code == 200 and r.json(
    ) == {"sent": True, "provider": "fake"}
    assert len(world.sent) == before + 1
    message = world.sent[-1]
    assert message.to == "someone@example.com" and message.attachment.data == user.doc.pdf


def test_a_confirmation_works_only_once(world):
    user = world.user_with_aadhaar("once")
    action = prepare(world, user)
    assert confirm(world, user, action["token"]).status_code == 200
    before = len(world.sent)
    replay = confirm(world, user, action["token"])
    assert replay.status_code == 400 and "already used" in replay.json()[
        "detail"]
    assert len(world.sent) == before


def test_a_confirmation_cannot_be_used_by_someone_else_or_altered(world, bob):
    user = world.user_with_aadhaar("owner")
    action = prepare(world, user)
    before = len(world.sent)
    assert confirm(world, bob, action["token"]).status_code == 400
    assert confirm(world, user, action["token"]
                   [:-4] + "abcd").status_code == 400
    # a login token is not a confirmation
    assert confirm(world, user, user.token).status_code == 400
    assert len(world.sent) == before


def test_a_confirmation_token_is_not_a_login_token(world):
    user = world.user_with_aadhaar("tok")
    action = prepare(world, user)
    r = world.client.get(
        "/auth/me", headers={"Authorization": f"Bearer {action['token']}"})
    assert r.status_code == 401


def test_email_to_me_uses_the_users_own_address(world):
    user = world.user_with_aadhaar("me", email=f"me_{world.tag}@example.com")
    assert prepare(world, user, to="me")["to"] == user.email


def test_a_failed_send_gives_a_clear_error_and_can_be_retried(world):
    user = world.user_with_aadhaar("fail")
    action = prepare(world, user)
    world.fail_email["on"] = True
    try:
        r = confirm(world, user, action["token"])
    finally:
        world.fail_email["on"] = False
    assert r.status_code == 502 and "login rejected" in r.json()["detail"]
    # the token was given back
    assert confirm(world, user, action["token"]).status_code == 200


def test_the_daily_email_limit_is_enforced(world, monkeypatch):
    user = world.user_with_aadhaar("limit")
    assert confirm(world, user, prepare(world, user)
                   ["token"]).status_code == 200
    monkeypatch.setattr(world.settings, "email_daily_limit_per_user", 1)
    before = len(world.sent)
    # A different address, so this is a new confirmation and not a replay of the first (identical tokens made in the
    # same second would be refused as "already used" before the limit is ever checked).
    r = confirm(world, user, prepare(
        world, user, to="second@example.com")["token"])
    assert r.status_code == 429 and "limit" in r.json()["detail"].lower()
    assert len(world.sent) == before
