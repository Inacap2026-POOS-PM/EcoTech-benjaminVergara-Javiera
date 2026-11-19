import json
import logging
import os
import random
import sqlite3
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()  # lee el archivo .env (que NO se sube a GitHub)

# Registro de eventos: cada reintento y cada degradación quedan anotados
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cliente_api")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Base local (la misma del proyecto): ruta relativa a la carpeta del proyecto o absoluta
DB_NOMBRE = os.getenv("DB_NOMBRE", "ecotech.db")
RUTA_BD = (
    DB_NOMBRE
    if os.path.isabs(DB_NOMBRE)
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NOMBRE)
)

TIMEOUT = (3, 10)   # (conectar, leer): siempre un número
MAX_INTENTOS = 4    # tope: 1 intento + 3 reintentos
ESPERA_BASE = 1     # segundos; la espera se duplica: 1, 2, 4


# ---------------------------------------------------------------
# Parte 2: reintentos con espera creciente
# ---------------------------------------------------------------
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


# ---------------------------------------------------------------
# Parte 3: degradación controlada (plan B con datos locales)
# ---------------------------------------------------------------
def _conectar():
    con = sqlite3.connect(RUTA_BD)
    con.execute(
        "CREATE TABLE IF NOT EXISTS cache_api ("
        "tabla TEXT PRIMARY KEY, datos TEXT NOT NULL, guardado_en TEXT NOT NULL)"
    )
    return con


def guardar_cache(tabla, datos):
    """Guarda la última respuesta buena de la API en la base local."""
    ahora = datetime.now(timezone.utc).isoformat()
    try:
        con = _conectar()
        try:
            with con:
                con.execute(
                    "INSERT OR REPLACE INTO cache_api (tabla, datos, guardado_en) VALUES (?, ?, ?)",
                    (tabla, json.dumps(datos), ahora),
                )
        finally:
            con.close()
    except sqlite3.Error as e:
        log.error("No se pudo guardar la copia local: %s", e)


def leer_cache(tabla):
    """Devuelve (datos, momento_guardado) o None si no hay copia local."""
    try:
        con = _conectar()
        try:
            fila = con.execute(
                "SELECT datos, guardado_en FROM cache_api WHERE tabla = ?", (tabla,)
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error as e:
        log.error("No se pudo leer la copia local: %s", e)
        return None
    if fila is None:
        return None
    return json.loads(fila[0]), datetime.fromisoformat(fila[1])


def _hace_cuanto(momento):
    segundos = int((datetime.now(timezone.utc) - momento).total_seconds())
    if segundos < 60:
        return f"{segundos} segundos"
    if segundos < 3600:
        return f"{segundos // 60} minutos"
    if segundos < 86400:
        return f"{segundos // 3600} horas"
    return f"{segundos // 86400} días"


def obtener_datos(tabla):
    """Lo ideal: API. Plan B: datos locales con aviso. Plan C: mensaje claro."""
    datos = consultar_tabla(tabla)
    if datos is not None:
        guardar_cache(tabla, datos)
        return {"origen": "api", "datos": datos, "aviso": None}

    cache = leer_cache(tabla)
    if cache is not None:
        datos, momento = cache
        aviso = (
            "Atención: el servicio no responde. "
            f"Se muestran datos guardados hace {_hace_cuanto(momento)}."
        )
        log.warning("Plan B: usando datos locales (hace %s).", _hace_cuanto(momento))
        return {"origen": "local", "datos": datos, "aviso": aviso}

    aviso = "El servicio no está disponible y no hay datos guardados. Intenta de nuevo más tarde."
    log.error("Plan C: sin API y sin datos locales.")
    return {"origen": "ninguno", "datos": None, "aviso": aviso}


if __name__ == "__main__":
    resultado = obtener_datos("empleados")  # cambia "empleados" por el nombre real de tu tabla
    print(f"Origen de los datos: {resultado['origen']}")
    if resultado["aviso"]:
        print(resultado["aviso"])
    print(resultado["datos"])