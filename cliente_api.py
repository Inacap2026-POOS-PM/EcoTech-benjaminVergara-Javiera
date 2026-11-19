import os
import requests
from dotenv import load_dotenv

load_dotenv()  # lee el archivo .env (que NO se sube a GitHub)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TIMEOUT = (3, 10)  # (conectar, leer): siempre un número


def consultar_tabla(tabla):
    """Pide los datos de una tabla de Supabase. Devuelve una lista o None si falla."""
    url = f"{SUPABASE_URL}/rest/v1/{tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        print("El servidor no respondió a tiempo.")
        return None
    except requests.exceptions.ConnectionError:
        print("No hay conexión de red.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error en la petición: {e}")
        return None

    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 401:
        print("401: clave inválida o expirada.")
    elif resp.status_code == 403:
        print("403: sin permiso. Revisar la configuración, no reintentar.")
    elif resp.status_code == 404:
        print("404: la tabla no existe (¿nombre inválido?).")
    elif resp.status_code == 429:
        print("429: superaste la cuota. Esperar Retry-After.")
    elif 500 <= resp.status_code <= 503:
        print(f"{resp.status_code}: falló el servidor.")
    return None


if __name__ == "__main__":
    print(consultar_tabla("empleados"))  # cambia "empleados" por el nombre real de tu tabla