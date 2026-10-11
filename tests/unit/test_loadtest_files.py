"""Guards for the load test files, so a broken edit is noticed before JMeter is opened."""
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from loadtest import setup_users

JMX = Path(__file__).resolve().parents[2] / "loadtest" / "omnidoc.jmx"


def test_plan_is_valid_xml_with_every_element_followed_by_its_hashtree():
    root = ET.parse(JMX).getroot()

    def walk(tree):
        kids = list(tree)
        assert len(kids) % 2 == 0
        for element, child in zip(kids[::2], kids[1::2]):
            assert element.tag != "hashTree" and child.tag == "hashTree", element.get(
                "testname")
            walk(child)

    walk(root[0])


def test_plan_covers_the_expected_requests_and_is_read_only():
    root = ET.parse(JMX).getroot()
    samplers = {e.get("testname"): e for e in root.iter("HTTPSamplerProxy")}
    assert set(samplers) == {"POST /auth/login", "GET /auth/me", "GET /providers", "GET /documents",
                             "GET /documents/{id}/file"}
    methods = {n: next(p.text for p in s.iter("stringProp") if p.get("name") == "HTTPSampler.method")
               for n, s in samplers.items()}
    assert [n for n, m in methods.items() if m != "GET"] == [
        "POST /auth/login"]    # no chat, upload or delete


def test_plan_takes_its_settings_from_properties():
    text = JMX.read_text(encoding="utf-8")
    for prop in ("host", "port", "protocol", "base_path", "threads", "rampup", "loops", "think_ms", "users_file"):
        assert f"__P({prop}," in text, prop
    assert "Bearer ${token}" in text


def test_setup_users_refuses_remote_servers_without_permission(capsys):
    assert setup_users.main(["--base-url", "https://example.org/api/v1"]) == 2
    assert "--allow-remote" in capsys.readouterr().out


def test_setup_users_helpers(tmp_path):
    assert setup_users.is_local(
        "http://localhost:8000/v1") and setup_users.is_local("http://127.0.0.1/v1")
    assert not setup_users.is_local("https://omnidocs.duckdns.org/api/v1")
    path = tmp_path / "u.csv"
    assert setup_users.read_existing(path) == {}
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(
            [["username", "password"], ["loadtest1", "pw1"]])
    assert setup_users.read_existing(path) == {"loadtest1": "pw1"}
    pdf = setup_users.make_pdf(["hello"])
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
