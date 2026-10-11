"""The in-memory stand-ins must behave like the real vector store: a search never leaves the caller's own data."""
from types import SimpleNamespace

from scripts.api_fakes import DIM, FakeEmbedder, FakeVectorStore


def item(item_id, vector, **meta):
    return SimpleNamespace(id=item_id, vector=vector, metadata=meta)


def found(matches):
    return repr(matches)          # works whatever the Match class looks like


def test_embedder_makes_unit_vectors_of_fixed_size():
    e = FakeEmbedder()
    v = e.embed_query("my aadhaar number")
    assert len(v) == DIM and abs(sum(x * x for x in v) - 1) < 1e-9
    assert e.embed_documents(["a b", "c d"]) == [
        e.embed_query("a b"), e.embed_query("c d")]


def test_embedder_handles_empty_text():
    assert e_sum(FakeEmbedder().embed_query("")) == 0


def e_sum(v):
    return sum(abs(x) for x in v)


def test_search_never_returns_another_users_items():
    e, store = FakeEmbedder(), FakeVectorStore()
    vec = e.embed_query("address lucknow")
    store.upsert(1, [item("alice-doc", vec, document_id=1)])
    store.upsert(
        2, [item("bob-doc", e.embed_query("address delhi"), document_id=2)])
    assert "alice-doc" in found(store.query(1, vec, top_k=5)
                                ) and "bob-doc" not in found(store.query(1, vec, top_k=5))
    assert "bob-doc" not in found(store.query(3, vec, top_k=5)
                                  ) and store.query(3, vec, top_k=5) == []


def test_user_id_in_metadata_cannot_be_forged():
    e, store = FakeEmbedder(), FakeVectorStore()
    vec = e.embed_query("x")
    # tries to claim to be someone else's
    store.upsert(1, [item("doc", vec, user_id=999)])
    assert store.items["doc"][1]["user_id"] == 1


def test_filters_narrow_results_and_none_filters_are_ignored():
    e, store = FakeEmbedder(), FakeVectorStore()
    vec = e.embed_query("x")
    store.upsert(1, [item("pan", vec, doc_type="pan"),
                 item("aad", vec, doc_type="aadhaar")])
    assert "aad" not in found(store.query(1, vec, filters={"doc_type": "pan"}))
    assert len(store.query(1, vec, filters={"doc_type": None})) == 2


def test_top_k_limits_results():
    e, store = FakeEmbedder(), FakeVectorStore()
    vec = e.embed_query("x")
    store.upsert(1, [item(f"d{i}", vec) for i in range(10)])
    assert len(store.query(1, vec, top_k=3)) == 3


def test_delete_only_removes_the_owners_items():
    e, store = FakeEmbedder(), FakeVectorStore()
    vec = e.embed_query("x")
    store.upsert(1, [item("mine", vec)])
    # someone else asks
    store.delete(2, ["mine"])
    assert "mine" in store.items
    store.delete(1, ["mine", "does-not-exist"])
    assert "mine" not in store.items
