import os
import requests
from dotenv import load_dotenv

load_dotenv()
# Ahora leemos las variables de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def obtener_datos_externos():
    # Supabase necesita la tabla a la que vas a consultar. 
    # Asumamos que tienes una tabla llamada "empleados". Si se llama distinto, cámbialo aquí:
    url_tabla = f"{SUPABASE_URL}/rest/v1/empleados?select=*"
    
    # Supabase exige estos headers específicos
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    try:
        print("Intentando conectar a Supabase...")
        respuesta = requests.get(url_tabla, headers=headers, timeout=5)
        respuesta.raise_for_status()
        
        print("¡Conexión a Supabase exitosa!")
        return respuesta.json()
        
    except requests.exceptions.Timeout:
        print("Error: La conexión a Supabase demoró mucho (Timeout).")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error HTTP de Supabase: {e.response.status_code}. Revisa tu URL, Clave o nombre de tabla.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error de red crítico: {e}")
        return None