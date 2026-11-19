import logging
import os
import random
import time

import requests
from dotenv import load_dotenv

load_dotenv()  # lee el archivo .env (que NO se sube a GitHub)

# Registro de eventos: cada reintento queda anotado
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cliente_api")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TIMEOUT = (3, 10)   # (conectar, leer): siempre un número
MAX_INTENTOS = 4    # tope: 1 intento + 3 reintentos
ESPERA_BASE = 1     # segundos; la espera se duplica: 1, 2, 4


def _leer_retry_after(resp):
    """Si el servidor dice cuánto esperar (429), usa ese valor con un máximo de 30 s."""
    valor = resp.headers.get("Retry-After")
    try:
        return min(float(valor), 30)
    except (TypeError, ValueError):
        return None


def _esperar(intento, retry_after=None):
    """Espera creciente con un poco de azar (jitter)."""
    if retry_after is not None:
        espera = retry_after
    else:
        espera = ESPERA_BASE * (2 ** (intento - 1)) + random.uniform(0, 0.5)
    log.warning("Reintentando en %.1f s (falló el intento %d de %d)", espera, intento, MAX_INTENTOS)
    time.sleep(espera)


def consultar_tabla(tabla):
    """Pide los datos de una tabla de Supabase. Devuelve una lista o None si falla."""
    url = f"{SUPABASE_URL}/rest/v1/{tabla}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    for intento in range(1, MAX_INTENTOS + 1):
        retry_after = None
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        except requests.exceptions.Timeout:
            log.warning("Intento %d: el servidor no respondió a tiempo.", intento)
        except requests.exceptions.ConnectionError:
            log.warning("Intento %d: no hay conexión de red.", intento)
        except requests.exceptions.RequestException as e:
            log.error("Error en la petición, no se reintenta: %s", e)
            return None
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                log.warning("429: superaste la cuota.")
                retry_after = _leer_retry_after(resp)
            elif 500 <= resp.status_code <= 503:
                log.warning("%d: falló el servidor.", resp.status_code)
            else:
                # Errores 4xx: culpa de quien llama, no se reintentan
                mensajes = {
                    401: "401: clave inválida o expirada.",
                    403: "403: sin permiso. Revisar la configuración.",
                    404: "404: la tabla no existe (¿nombre inválido?).",
                }
                log.error(mensajes.get(resp.status_code, f"Error {resp.status_code}, no se reintenta."))
                return None

        if intento < MAX_INTENTOS:
            _esperar(intento, retry_after)

    log.error("Se agotaron los %d intentos. No se pudo completar la consulta.", MAX_INTENTOS)
    return None


if __name__ == "__main__":
    print(consultar_tabla("empleados"))  # cambia "empleados" por el nombre real de tu tabla