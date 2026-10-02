import shutil
from pathlib import Path

from omnidoc.core import crypto
from omnidoc.core.config import get_settings
from omnidoc.providers.storage.factory import get_file_store

store = get_file_store()
root = Path(get_settings().vault_dir)
secret = b"AADHAAR 1234 5678 9012"

# 1. round trip
key = store.save(1, secret)
assert store.load(1, key) == secret
print("round trip OK")

# 2. what's on disk is not readable
raw = (root / "user-1" / f"{key}.bin").read_bytes()
assert secret not in raw and b"AADHAAR" not in raw
print("file on disk is encrypted OK")

# 3. another user cannot load it
try:
    store.load(2, key)
    raise SystemExit("LEAK: user 2 read user 1's file")
except FileNotFoundError:
    print("user 2 blocked (no such file) OK")

# 4. even if the file is copied into user 2's folder, user 2's key can't decrypt it
(root / "user-2").mkdir(parents=True, exist_ok=True)
shutil.copy(root / "user-1" / f"{key}.bin", root / "user-2" / f"{key}.bin")
try:
    store.load(2, key)
    raise SystemExit("LEAK: user 2 decrypted user 1's file")
except crypto.InvalidToken:
    print("user 2 cannot decrypt copied file OK")

# 5. text/json helpers
assert crypto.decrypt_json(1, crypto.encrypt_json(
    1, {"aadhaar": "1234 5678 9012"})) == {"aadhaar": "1234 5678 9012"}
print("text/json helpers OK")

# cleanup
store.delete(1, key)
(root / "user-2" / f"{key}.bin").unlink(missing_ok=True)
assert not (root / "user-1" / f"{key}.bin").exists()
print("delete OK")
