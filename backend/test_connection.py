import google.generativeai as genai
import os

# Configuración explícita (hardcodeada solo para este test)
API_KEY = "AIzaSyCkDDDeeciCgevQv4JbTQZTsoF6je_jixI" 
genai.configure(api_key=API_KEY)

print("Intentando listar modelos...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
    print("¡Conexión exitosa!")
except Exception as e:
    print(f"Error al conectar: {e}")