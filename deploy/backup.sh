#!/bin/bash
# Daily backup of the database and the encrypted document vault. Runs ON THE SERVER (see the cron lines below).
# Output: ~/backups/db-<time>.sql.gz.age and ~/backups/vault-<time>.tar.gz.age, kept for 7 days on the server,
# and copied to a private S3 bucket (30 days, set by a lifecycle rule on the bucket).
# Both files are encrypted with `age` using the PUBLIC key below, so this server can lock backups but never
# open them. The private key lives only on the owner's computer and in a password manager.
# Restore: age -d -i <private key file> db-<time>.sql.gz.age | gunzip | psql ...   (see README)
# NOT included on purpose: the .env file. Keep VAULT_KEY (and the rest of .env) in your password manager:
# without VAULT_KEY the vault backup cannot be read.
# Cron: 30 2 * * * (nightly) and @reboot after a delay (the server is stopped when not in use, cron does not catch up).
# Log: journalctl -t omnidoc-backup
set -euo pipefail
exec > >(logger -t omnidoc-backup) 2>&1

KEEP_DAYS=7
BACKUP_DIR="$HOME/backups"
STAMP=$(date +%Y%m%d-%H%M%S)
VAULT_VOLUME="omnidoc_vault"        # <folder name>_vault, created by docker compose
S3_BUCKET="omnidoc-backups-rohit-2026"   # the server's role may only ADD files here, never read or delete
AGE_RECIPIENT="age1wn7y3qaejzl2fs9nuqhg56djvhnyap7frl0h2sf06hj0dgx5jpqs3hgfz8"   # public key: safe to keep here
export PATH="$PATH:/snap/bin"            # cron's PATH does not include the snap-installed aws tool

umask 077
mkdir -p "$BACKUP_DIR"

# Never run two backups at once (nightly run and start-up run could overlap).
exec 9> "$BACKUP_DIR/.lock"
if ! flock -n 9; then
    echo "another backup is already running; skipping this one"
    exit 0
fi

command -v age > /dev/null || { echo "ERROR: age is not installed (sudo apt-get install -y age)"; exit 1; }

# A failed run must not leave half-finished files behind.
trap 'rm -f "$BACKUP_DIR"/*.tmp' EXIT

# Fails unless the file is not empty and really is an age-encrypted file.
check_encrypted() {
    [ -s "$1" ] && head -c 21 "$1" | grep -q "age-encryption.org/v1"
}

cd "$HOME/omnidoc"

# 1. Database (written to a temp name first, so a failed run never leaves a half-finished backup)
docker compose exec -T db pg_dump -U omnidoc -d omnidoc | gzip | age -r "$AGE_RECIPIENT" > "$BACKUP_DIR/db-$STAMP.sql.gz.age.tmp"
check_encrypted "$BACKUP_DIR/db-$STAMP.sql.gz.age.tmp"
mv "$BACKUP_DIR/db-$STAMP.sql.gz.age.tmp" "$BACKUP_DIR/db-$STAMP.sql.gz.age"

# 2. Vault files (already encrypted by the app; encrypted again so the whole backup is one uniform, locked file).
#    Uses an image that is already on the server. The archive streams out of the container straight into age.
docker run --rm -v "$VAULT_VOLUME":/data:ro postgres:16-alpine tar czf - -C /data . \
    | age -r "$AGE_RECIPIENT" > "$BACKUP_DIR/vault-$STAMP.tar.gz.age.tmp"
check_encrypted "$BACKUP_DIR/vault-$STAMP.tar.gz.age.tmp"
mv "$BACKUP_DIR/vault-$STAMP.tar.gz.age.tmp" "$BACKUP_DIR/vault-$STAMP.tar.gz.age"

# 3. Copy both files off the server. A failed upload is logged loudly but does not undo the local backup.
UPLOAD_FAILED=0
for f in "db-$STAMP.sql.gz.age" "vault-$STAMP.tar.gz.age"; do
    if ! aws s3 cp --only-show-errors "$BACKUP_DIR/$f" "s3://$S3_BUCKET/$f"; then
        echo "WARNING: upload of $f to s3://$S3_BUCKET failed"
        UPLOAD_FAILED=1
    fi
done

# 4. Delete local backups older than KEEP_DAYS (the patterns also match the older, unencrypted files)
find "$BACKUP_DIR" -name 'db-*.sql.gz*' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'vault-*.tar.gz*' -mtime +"$KEEP_DAYS" -delete

if [ "$UPLOAD_FAILED" -eq 1 ]; then
    echo "backup finished locally, but the off-server copy FAILED"
    exit 1
fi
echo "backup finished: db-$STAMP.sql.gz.age, vault-$STAMP.tar.gz.age (encrypted, copied to s3://$S3_BUCKET)"