"""Creates the test users the JMeter plan logs in as, and gives each one a small document to download.

  python -m loadtest.setup_users                       # 3 users against http://localhost:8000/v1
  python -m loadtest.setup_users --count 10            # more users (see the sign-up limit note in loadtest/README.md)

It writes loadtest/users.csv (git-ignored, random passwords) and can be run again safely: users that
already exist are reused, and a document is uploaded only if the user has none.
"""
import argparse
import csv
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

OUT = Path(__file__).with_name("users.csv")


def make_pdf(lines):
    """A tiny valid PDF made by hand, so no extra library is needed."""
    content = "BT /F1 12 Tf 50 750 Td 14 TL " + \
        " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


def read_existing(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["username"]: row["password"] for row in csv.DictReader(f)}


def is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in ("localhost", "127.0.0.1", "::1")


class SetupError(Exception):
    """A problem worth telling the user about; the message is printed as is."""


def sign_up(c, name, password, known, out):
    r = c.post("/auth/signup", json={"username": name, "password": password})
    if r.status_code == 429:
        raise SetupError(f"Stopped at {name}: sign-up limit reached ({r.json().get('detail')}). "
                         "Wait, or raise SIGNUP_PER_HOUR_PER_IP on a local server. See loadtest/README.md.")
    if r.status_code == 409 and name not in known:
        raise SetupError(
            f"{name} already exists but its password is not in {out}. Use --prefix with another word.")
    if r.status_code not in (201, 409):
        raise SetupError(
            f"Sign-up failed for {name}: {r.status_code} {r.text}")


def log_in(c, name, password):
    r = c.post("/auth/login", data={"username": name, "password": password})
    if r.status_code != 200:
        raise SetupError(f"Login failed for {name}: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def ensure_document(c, name, auth, pdf):
    if c.get("/documents", headers=auth).json():
        return
    up = c.post("/documents", headers=auth, data={"doc_type": "other"},
                files={"file": ("loadtest.pdf", pdf, "application/pdf")})
    if up.status_code != 201:
        raise SetupError(
            f"Upload failed for {name}: {up.status_code} {up.text}")


def write_users(out, rows):
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["username", "password"])
        w.writerows(rows)
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass


def parse_args(argv):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://localhost:8000/v1")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--prefix", default="loadtest")
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--allow-remote", action="store_true",
                   help="needed to create test users on a server that is not on this computer")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not is_local(args.base_url) and not args.allow_remote:
        print("That address is not on this computer. Add --allow-remote if you really want test users there.")
        return 2

    known = read_existing(args.out)
    pdf = make_pdf(["Load test document", "Nothing personal in this file"])
    rows = []
    try:
        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30) as c:
            for i in range(1, args.count + 1):
                name = f"{args.prefix}{i}"
                password = known.get(name) or secrets.token_urlsafe(12)
                sign_up(c, name, password, known, args.out)
                ensure_document(c, name, log_in(c, name, password), pdf)
                rows.append((name, password))
                print(f"ready: {name}")
    except SetupError as exc:
        print(exc)
        return 1

    write_users(args.out, rows)
    print(f"Wrote {args.out} with {len(rows)} users.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
