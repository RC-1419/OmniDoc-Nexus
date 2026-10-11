"""The most important promise: one user can never see or change another user's data."""
import pytest


def test_a_new_user_sees_nothing_of_anyone_else(world, alice, bob):
    assert world.client.get("/documents", headers=bob.headers).json() == []
    assert len(world.client.get("/people", headers=bob.headers).json()
               ) == 1       # only Bob himself


@pytest.mark.parametrize("act", [
    lambda c, h, doc: c.get(f"/documents/{doc.id}/file", headers=h),
    lambda c, h, doc: c.delete(f"/documents/{doc.id}", headers=h),
    lambda c, h, doc: c.put(
        f"/documents/{doc.id}/fields/aadhaar_number", headers=h, json={"value": doc.number}),
])
def test_other_users_documents_look_like_they_do_not_exist(world, alice, bob, act):
    missing = world.client.get("/documents/99999999/file", headers=bob.headers)
    r = act(world.client, bob.headers, alice.doc)
    # no hint that the document is real
    assert r.status_code == 404 and r.json() == missing.json()


def test_bob_cannot_file_things_under_alices_family_members(world, alice, bob):
    alice_person = world.client.get(
        "/people", headers=alice.headers).json()[0]["id"]
    assert world.upload(bob, "x.pdf", alice.doc.pdf,
                        person_id=alice_person).status_code == 404


def test_alice_still_has_her_document_after_bobs_attempts(world, alice, bob):
    world.client.delete(f"/documents/{alice.doc.id}", headers=bob.headers)
    assert world.client.get(
        f"/documents/{alice.doc.id}/file", headers=alice.headers).status_code == 200


def test_search_entries_belong_to_their_owner(world, alice, bob):
    owners = {meta["user_id"] for _, meta in world.store.items.values(
    ) if meta.get("document_id") == alice.doc.id}
    assert owners == {int(world.client.get(
        "/auth/me", headers=alice.headers).json()["id"])}
