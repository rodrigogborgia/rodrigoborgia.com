"""
Script de prueba para verificar la conexión con Instagram Graph API
"""

import os
import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Obtener credenciales del archivo .env
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("META_INSTAGRAM_BUSINESS_ACCOUNT_ID")

# Validar que las variables estén configuradas
if not ACCESS_TOKEN:
    print("❌ Error: META_ACCESS_TOKEN no está configurado en .env")
    exit(1)

if not INSTAGRAM_BUSINESS_ACCOUNT_ID:
    print("❌ Error: META_INSTAGRAM_BUSINESS_ACCOUNT_ID no está configurado en .env")
    exit(1)

print(f"✓ Credenciales cargadas correctamente")
print(f"  Account ID: {INSTAGRAM_BUSINESS_ACCOUNT_ID}")
print()

# Configurar la petición a Instagram Graph API
api_version = "v18.0"
endpoint = f"https://graph.instagram.com/{api_version}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"

params = {
    "fields": "id,caption,media_type,media_url,timestamp",
    "access_token": ACCESS_TOKEN
}

print(f"Realizando petición GET a: {endpoint}")
print()

try:
    # Realizar la petición GET
    response = requests.get(endpoint, params=params)
    
    # Verificar el código de estado
    if response.status_code == 200:
        print("✅ Conexión exitosa con Instagram Graph API")
        print()
        data = response.json()
        
        if "data" in data:
            media_items = data["data"]
            print(f"Se encontraron {len(media_items)} elementos de media:")
            print()
            for item in media_items[:5]:  # Mostrar los primeros 5
                print(f"  - ID: {item.get('id')}")
                print(f"    Tipo: {item.get('media_type')}")
                print(f"    Caption: {item.get('caption', 'Sin descripción')[:50]}...")
                print()
        else:
            print("No se encontraron elementos de media")
            print(f"Respuesta: {data}")
    else:
        print(f"❌ Error en la conexión (Status: {response.status_code})")
        print()
        try:
            error_data = response.json()
            error_message = error_data.get("error", {})
            print(f"Tipo de error: {error_message.get('type', 'Desconocido')}")
            print(f"Mensaje: {error_message.get('message', 'Sin mensaje')}")
            print(f"Código: {error_message.get('code', 'Sin código')}")
        except:
            print(f"Respuesta: {response.text}")

except requests.exceptions.ConnectionError:
    print("❌ Error de conexión: No se pudo conectar a Instagram Graph API")
    print("   Verifica tu conexión a internet")

except requests.exceptions.Timeout:
    print("❌ Error de conexión: La petición expiró")

except Exception as e:
    print(f"❌ Error inesperado: {str(e)}")
