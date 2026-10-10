#!/bin/bash
# Daily backup of the database and the encrypted document vault. Runs ON THE SERVER (see cron line below).
# Output: ~/backups/db-<time>.sql.gz and ~/backups/vault-<time>.tar.gz, kept for 7 days.
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

# 3. Delete backups older than KEEP_DAYS
find "$BACKUP_DIR" -name 'db-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'vault-*.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "backup finished: db-$STAMP.sql.gz, vault-$STAMP.tar.gz"
