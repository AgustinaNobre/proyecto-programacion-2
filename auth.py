import jwt
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from pwdlib import PasswordHash

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

# Configuramos el sistema para proteger las contraseñas
password_hash = PasswordHash.recommended()


def generar_hash(password: str) -> str:
    # Convierte la contraseña en un hash seguro
    return password_hash.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    # Comprueba si la contraseña coincide con el hash almacenado
    return password_hash.verify(password, hash_guardado)

def crear_token(usuario_id: int) -> str:
    # Establecemos que el token dure 30 minutos
    vencimiento = datetime.now(timezone.utc) + timedelta(minutes=30)

    # Información que guardamos dentro del token
    datos = {
        "sub": str(usuario_id),
        "exp": vencimiento
    }

    # Generamos el token firmado con nuestra clave secreta
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(token: str):
    try:
        # Decodificamos el token y comprobamos su firma y vencimiento
        datos = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Obtenemos el ID del usuario
        usuario_id = datos.get("sub")

        return usuario_id

    except jwt.InvalidTokenError:
        # Si el token es inválido o venció
        return None

