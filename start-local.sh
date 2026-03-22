#!/bin/sh
# Minimal script to serve static files from the current directory on port 8080

PORT=8080
FRONTEND_DIR="frontend"

if [ ! -d "$FRONTEND_DIR" ]; then
	echo "Error: No se encontró el directorio '$FRONTEND_DIR'."
	exit 1
fi

cd "$FRONTEND_DIR" || exit 1

if command -v python3 >/dev/null 2>&1; then
	echo "Serving static files from '$FRONTEND_DIR' at http://localhost:$PORT"
	python3 -m http.server "$PORT"
else
	echo "Error: python3 is not installed. Please install Python 3 to use this script."
	exit 1
fi
