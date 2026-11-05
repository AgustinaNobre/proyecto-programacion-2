from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import models
from database import get_db
import jwt
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from pwdlib import PasswordHash

load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Configuramos el sistema para proteger las contraseñas
password_hash = PasswordHash.recommended()


def get_password_hash(password: str):
    # Genera un hash seguro de la contraseña
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    # Comprueba si la contraseña coincide con el hash guardado
    return password_hash.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, SECRET_KEY, algorithm=ALGORITHM
    )

    return encoded_jwt


def get_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.Usuario:

    error = HTTPException(
        status_code=401,
        detail="Token inválido o vencido",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        datos = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(datos["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise error

    usuario = db.get(models.Usuario, usuario_id)

    if usuario is None:
        raise error

    return usuario

def get_propietario_actual(
    usuario: models.Usuario = Depends(get_usuario_actual),
) -> models.Usuario:

    if not usuario.es_propietario():
        raise HTTPException(
            status_code=403,
            detail="Solo para propietarios"
        )

    return usuario