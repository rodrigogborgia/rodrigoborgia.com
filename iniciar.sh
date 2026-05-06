#!/bin/bash

# 1. Nos movemos a la carpeta del proyecto
cd "/Users/rodrigoborgia/RB/rodrigoborgia.com/"

# 2. Activamos el entorno virtual
source .venv/bin/activate

# 3. Abrimos Chrome en el Swagger (esperamos 2 segundos para que el servidor arranque)
# Nota: Esta línea abre Chrome después de lanzar el servidor
(sleep 2 && open -a "Google Chrome" http://127.0.0.1:8000/docs) &

# 4. Lanzamos el servidor
python3 -m uvicorn backend.app.main:app --reload