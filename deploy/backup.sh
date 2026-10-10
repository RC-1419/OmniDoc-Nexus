#!/bin/bash
# Daily backup of the database and the encrypted document vault. Runs ON THE SERVER (see cron line below).
# Output: ~/backups/db-<time>.sql.gz and ~/backups/vault-<time>.tar.gz, kept for 7 days on the server,
# and copied to a private S3 bucket (30 days, set by a lifecycle rule on the bucket).
# NOT included on purpose: the .env file. Keep VAULT_KEY (and the rest of .env) in your password manager:
# without VAULT_KEY the vault backup cannot be read.
# Log: journalctl -t omnidoc-backup
set -euo pipefail
exec > >(logger -t omnidoc-backup) 2>&1

KEEP_DAYS=7
BACKUP_DIR="$HOME/backups"
STAMP=$(date +%Y%m%d-%H%M%S)
VAULT_VOLUME="omnidoc_vault"        # <folder name>_vault, created by docker compose
OWNER="$(id -u):$(id -g)"
S3_BUCKET="omnidoc-backups-rohit-2026"   # the server's role may only ADD files here, never read or delete
export PATH="$PATH:/snap/bin"            # cron's PATH does not include the snap-installed aws tool

umask 077
mkdir -p "$BACKUP_DIR"
cd "$HOME/omnidoc"

# 1. Database (written to a temp name first, so a failed run never leaves a half-finished backup)
docker compose exec -T db pg_dump -U omnidoc -d omnidoc | gzip > "$BACKUP_DIR/db-$STAMP.sql.gz.tmp"
mv "$BACKUP_DIR/db-$STAMP.sql.gz.tmp" "$BACKUP_DIR/db-$STAMP.sql.gz"

# 2. Vault files (already encrypted by the app). Uses an image that is already on the server.
#    The archive is made inside a container (as root), so hand it to this user and make it private.
docker run --rm -e OWNER="$OWNER" -v "$VAULT_VOLUME":/data:ro -v "$BACKUP_DIR":/backup postgres:16-alpine \
    sh -c "tar czf /backup/vault-$STAMP.tar.gz.tmp -C /data . \
           && chown \"\$OWNER\" /backup/vault-$STAMP.tar.gz.tmp \
           && chmod 600 /backup/vault-$STAMP.tar.gz.tmp"
mv "$BACKUP_DIR/vault-$STAMP.tar.gz.tmp" "$BACKUP_DIR/vault-$STAMP.tar.gz"

# 3. Copy both files off the server. A failed upload is logged loudly but does not undo the local backup.
UPLOAD_FAILED=0
for f in "db-$STAMP.sql.gz" "vault-$STAMP.tar.gz"; do
    if ! aws s3 cp --only-show-errors "$BACKUP_DIR/$f" "s3://$S3_BUCKET/$f"; then
        echo "WARNING: upload of $f to s3://$S3_BUCKET failed"
        UPLOAD_FAILED=1
    fi
done

# 4. Delete local backups older than KEEP_DAYS
find "$BACKUP_DIR" -name 'db-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'vault-*.tar.gz' -mtime +"$KEEP_DAYS" -delete

if [ "$UPLOAD_FAILED" -eq 1 ]; then
    echo "backup finished locally, but the off-server copy FAILED"
    exit 1
fi
echo "backup finished: db-$STAMP.sql.gz, vault-$STAMP.tar.gz (copied to s3://$S3_BUCKET)"