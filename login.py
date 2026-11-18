import hashlib
import sys

# La contraseña secreta es "admin123"
# Nunca guardamos "admin123" en texto plano, solo guardamos su "hash" (su huella digital)
HASH_CORRECTO = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"

def iniciar_sesion():
    print("========================================")
    print("   🔐 SISTEMA ECOTECH - LOGIN SEGURO   ")
    print("========================================")
    
    intentos = 3
    
    while intentos > 0:
        clave_ingresada = input("Ingrese la contraseña para continuar: ")
        
        # Hasheamos la clave que escribió el usuario para compararla
        hash_ingresado = hashlib.sha256(clave_ingresada.encode('utf-8')).hexdigest()
        
        if hash_ingresado == HASH_CORRECTO:
            print("✅ ¡Acceso concedido! Iniciando sistema...\n")
            return True
        else:
            intentos -= 1
            print(f"❌ Contraseña incorrecta. Te quedan {intentos} intento(s).\n")
            
    print("⛔ Acceso denegado. Cerrando programa por seguridad.")
    sys.exit() # Esto apaga el programa por completo si falla 3 veces