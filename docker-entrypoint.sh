#!/bin/bash
set -e

echo "=== JavBot Entrypoint ==="
echo "Starting JavBot..."
exec python -m app.main "$@"
