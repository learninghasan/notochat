#!/bin/sh
# Install in the deployment's scheduler with database/key environment already loaded.
set -eu
: "${BACKUP_DIR:?Configure a durable backup directory}"
: "${BACKUP_ENCRYPTION_KEY:?Configure a separate backup encryption key}"
: "${DATABASE_URL:?Configure the operational database URL}"
umask 077
mkdir -p "$BACKUP_DIR"
backup_script_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backup_timestamp=$(date -u +%Y%m%dT%H%M%SZ)
"${NOTOCHAT_PYTHON:-python}" "$backup_script_root/backend/backups.py" --output "$BACKUP_DIR/notochat-$backup_timestamp.ncb"
"${NOTOCHAT_PYTHON:-python}" "$backup_script_root/backend/backups.py" --verify --input "$BACKUP_DIR/notochat-$backup_timestamp.ncb"
