import requests

# 1. PEGÁ LA URL NUEVA AQUÍ (RÁPIDO)
url_nueva = "https://rodrigoborgia.com/?code=h2mAPeFJ3E4AR5AdVXo2bhJcv3qC1W7vwkQgeEEUWo9E0GwEB4uErEaHGuC39uoyuSHeJZaIPRkrr24g9fh7SMS_u6HyiRqBizH1R9THm9zBzvCe8vT-zKYWD1qkAxHS23-3dH5nNfd4sALaTxpPzkKZpO_0x6Zew338dRHcolyxDUfb3WNU0WX3Rmhs3aLBmHrzyVeFtou2gRZL%2Av%214433.s1&scopes=user.info.basic%2Cvideo.publish%2Cvideo.upload&state=borgia_automation"

# Limpieza automática
auth_code = (
    url_nueva.split("code=")[1].split("&")[0].replace("%2A", "*").replace("%21", "!")
)

# Esta es la URL que nos dio el error 10007 (o sea, la que TikTok acepta)
url = "https://open-api.tiktok.com/oauth/access_token/"

# Enviamos SOLO lo que la API de Sandbox pidió la última vez que funcionó
query_params = {
    "client_key": "sbaw8b33o3djfyh5np",
    "client_secret": "hyCaYLdYQbScvsKtB6SEuNdsYLPC8AP4",
    "code": auth_code,
    "grant_type": "authorization_code",
}

print(f"🚀 Intentando canje (Estructura Exitosa): {auth_code[:15]}...")

# IMPORTANTE: Usamos params= para que vayan en la URL (como la vez que dio Expired)
response = requests.post(url, params=query_params)

print(f"Status Code: {response.status_code}")
print("Respuesta:", response.text)
