import os
import time  # NUEVO: Necesario para la espera creciente
import requests
from dotenv import load_dotenv

load_dotenv()
# Ahora leemos las variables de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def obtener_datos_externos():
    url_tabla = f"{SUPABASE_URL}/rest/v1/empleados?select=*"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    max_intentos = 3  # Intentar, reintentar, reintentar, rendirse
    
    for intento in range(1, max_intentos + 1):
        try:
            print(f"\n--- Intento {intento} de {max_intentos} ---")
            print("Conectando a Supabase...")
            
            # 1. TIMEOUT: Cortar a los N segundos
            respuesta = requests.get(url_tabla, headers=headers, timeout=5)
            codigo = respuesta.status_code
            
            # MANEJO POR CÓDIGO DE ESTADO
            if codigo == 200:
                print("¡Conexión a Supabase exitosa!")
                return respuesta.json() # Deserialización lista
                
            elif 400 <= codigo < 500:
                # Los errores 4xx son culpa del cliente (ej. 401, 403, 404). No se reintentan.
                print(f"Error del cliente ({codigo}). Revisa permisos o URL. Cancelando intentos.")
                break # Rompe el ciclo, no reintenta
                
            elif 500 <= codigo < 600:
                # Los errores 5xx son falla del servidor. Reintentar con espera creciente.
                print(f"El servidor de Supabase falló (Error {codigo}).")
                # Pasa a la lógica de espera creciente de abajo
                
        # 2. NO HAY RED: Avisar claro y no reintentar
        except requests.exceptions.ConnectionError:
            print("Error Crítico: No hay conexión a la red. Pasando al modo local (Plan B).")
            break # Rompe el ciclo directo al plan B
            
        except requests.exceptions.Timeout:
            print("Error: El servidor no responde (Timeout).")
            # Pasa a la lógica de espera creciente de abajo
            
        except requests.exceptions.RequestException as e:
            print(f"Falla inesperada de la librería requests: {e}")
            break

        # 3. REINTENTO CON ESPERA CRECIENTE (Para Timeouts o Errores 5xx)[cite: 14]
        if intento < max_intentos:
            espera = 2 ** intento  # Esperará 2s, luego 4s...
            print(f"Esperando {espera} segundos antes de reintentar...")
            time.sleep(espera)
        else:
            print("Nos rendimos. Límite de intentos alcanzado.")
            
    # Si todo falla, devuelve None para que tu programa active SQLite (Plan B)
    return None