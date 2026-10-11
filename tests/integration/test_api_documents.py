from types import SimpleNamespace

from tests.helpers import fake_aadhaar, make_pdf


def test_upload_list_and_download_hide_the_number_in_json(world, alice):
    n, pdf = alice.doc.number, alice.doc.pdf
    listing = world.client.get("/documents", headers=alice.headers)
    docs = listing.json()
    assert len(docs) == 1 and docs[0]["doc_type"] == "aadhaar" and docs[0]["fields"] == [
        "aadhaar_number"]
    assert docs[0]["person_name"] == alice.name
    assert n not in listing.text and n.replace(" ", "") not in listing.text
    r = world.client.get(
        f"/documents/{alice.doc.id}/file", headers=alice.headers)
    assert r.status_code == 200 and r.content == pdf and r.headers[
        "content-type"] == "application/pdf"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    assert "sandbox" in r.headers["content-security-policy"]


def test_upload_response_names_the_fields_but_never_the_numbers(world):
    user = world.new_user("up")
    n = fake_aadhaar()
    r = world.upload(user, "aadhaar.pdf", make_pdf(
        ["Government of India", f"Aadhaar number {n}"]))
    assert r.status_code == 201
    body = r.json()
    assert body["doc_type"] == "aadhaar" and body["fields_found"] == [
        "aadhaar_number"] and body["warnings"] == []
    assert n not in r.text and n.replace(" ", "") not in r.text


def test_uploading_the_same_kind_again_replaces_the_old_one(world):
    user = world.user_with_aadhaar("rep")
    r = world.upload(user, "aadhaar2.pdf", user.doc.pdf)
    assert r.status_code == 201 and r.json()["replaced"] == 1
    assert world.client.get(
        f"/documents/{user.doc.id}/file", headers=user.headers).status_code == 404
    assert len(world.client.get(
        "/documents", headers=user.headers).json()) == 1


def test_wrong_and_empty_files_are_refused(world):
    user = world.new_user("bad")
    assert world.upload(user, "notes.txt", b"just some text",
                        mime="text/plain").status_code == 415
    assert world.upload(user, "empty.pdf", b"").status_code == 415


def test_oversized_file_is_refused_with_a_clear_message(world):
    user = world.new_user("big")
    limit = world.settings.max_upload_mb * 1024 * 1024
    r = world.upload(user, "big.pdf", b"%PDF" + b"0" * (limit + 500_000))
    assert r.status_code == 413 and "larger" in r.json()["detail"]


def test_a_huge_request_is_stopped_before_it_is_read(world):
    user = world.new_user("huge")
    limit = world.settings.max_upload_mb * 1024 * 1024
    r = world.upload(user, "huge.pdf", b"%PDF" +
                     b"0" * (limit + 3 * 1024 * 1024))
    assert r.status_code == 413 and r.json()["detail"] == "Request too large"


def test_a_number_the_scanner_missed_can_be_typed_in_and_is_checked(world):
    user = world.new_user("fld")
    r = world.upload(user, "blank.pdf", make_pdf([]), doc_type="pan")
    assert r.status_code == 201 and any(
        "No readable text" in w for w in r.json()["warnings"])
    url = f"/documents/{r.json()['document_id']}/fields/pan_number"
    assert world.client.put(url, headers=user.headers, json={
                            "value": "NOT-A-PAN"}).status_code == 422
    assert world.client.put(url, headers=user.headers, json={
                            "value": ""}).status_code == 422
    assert world.client.put(url, headers=user.headers, json={
                            "value": "abcpe1234f"}).status_code == 204


def test_delete_removes_file_record_and_search_entries(world):
    user = world.user_with_aadhaar("del")
    doc_id = user.doc.id
    assert any(meta.get("document_id") == doc_id for _,
               meta in world.store.items.values())
    assert world.client.delete(
        f"/documents/{doc_id}", headers=user.headers).status_code == 204
    assert world.client.get(
        f"/documents/{doc_id}/file", headers=user.headers).status_code == 404
    assert doc_id not in [d["id"] for d in world.client.get(
        "/documents", headers=user.headers).json()]
    assert world.client.delete(
        f"/documents/{doc_id}", headers=user.headers).status_code == 404
    assert not any(meta.get("document_id") == doc_id for _,
                   meta in world.store.items.values())


def test_people_and_documents_filed_under_them(world):
    user = world.new_user("fam")
    r = world.client.post("/people", headers=user.headers,
                          json={"name": "Test Mum", "relation": "Mother"})
    assert r.status_code == 201 and r.json()["relation"] == "mother"
    mum = r.json()["id"]
    assert [p["name"] for p in world.client.get(
        "/people", headers=user.headers).json()] == [user.name, "Test Mum"]
    assert world.client.post("/people", headers=user.headers,
                             json={"name": "", "relation": "x"}).status_code == 422
    r = world.upload(user, "mum_pan.pdf", make_pdf(["INCOME TAX DEPARTMENT", "Permanent Account Number MUMPM5678K"]),
                     person_id=mum, doc_type="PAN card")
    assert r.status_code == 201 and r.json()["doc_type"] == "pan"
    docs = world.client.get("/documents", headers=user.headers).json()
    assert [d["person_name"] for d in docs] == ["Test Mum"]
    assert world.upload(user, "x.pdf", make_pdf(
        ["x"]), person_id=99999999).status_code == 404
