from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db


models.Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def inicio():
    return {"mensaje": "API de reserva de canchas funcionando"}


@app.post("/usuarios")
def crear_usuario(usuario: schemas.UsuarioCrear, db: Session = Depends(get_db)):

    usuario_existente = db.query(models.Usuario).filter(
        models.Usuario.email == usuario.email
    ).first()

    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="El email ya está registrado"
        )
    
    nuevo_usuario = models.Usuario(
        nombre=usuario.nombre,
        email=usuario.email,
        password=usuario.password
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario