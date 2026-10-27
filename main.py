from http import HTTPStatus

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas
from auth import create_access_token, get_password_hash, verify_password
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def inicio():
    return {"mensaje": "API de reserva de canchas funcionando"}


@app.post('/usuarios/', status_code=HTTPStatus.CREATED, response_model=schemas.UsuarioRespuesta)
def crear_usuario(usuario: schemas.UsuarioCrear, db: Session = Depends(get_db)):
    db_usuario = db.scalar(
        select(models.Usuario).where(models.Usuario.email == usuario.email)
    )

    if db_usuario:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='El email ya está registrado',
        )

    hashed_password = get_password_hash(usuario.password)

    db_usuario = models.Usuario(
        nombre=usuario.nombre,
        email=usuario.email,
        password_hash=hashed_password,
        rol=usuario.rol,
    )

    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)

    return db_usuario



@app.post('/token', response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = db.scalar(
        select(models.Usuario).where(models.Usuario.email == form_data.username)
    )

    if not usuario or not verify_password(form_data.password, usuario.password_hash):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Email o contraseña incorrectos',
        )

    access_token = create_access_token(data={'sub': str(usuario.id)})

    return {'access_token': access_token, 'token_type': 'bearer'}