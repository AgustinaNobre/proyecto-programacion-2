import os
from datetime import datetime, timedelta, timezone

import jwt
from jwt import encode
from fastapi import Depends, HTTPException
from pwdlib import PasswordHash
from zoneinfo import ZoneInfo
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import models
from database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "unsam2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = PasswordHash.recommended() 


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(tz=ZoneInfo('UTC')) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({'exp': expire})
    encoded_jwt = encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_usuario_actual(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.Usuario:
    error = HTTPException(
        status_code=401,
        detail="Token inválido o vencido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        datos = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(datos["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error

    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise error
    return usuario


def get_propietario_actual(
    usuario: models.Usuario = Depends(get_usuario_actual),
) -> models.Usuario:
    if not usuario.es_propietario():
        raise HTTPException(status_code=403, detail="Solo para propietarios")
    return usuario


def get_password_hash(password: str):
    return pwd_context.hash(password) 


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password) 
