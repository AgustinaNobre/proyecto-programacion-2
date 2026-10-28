from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from auth import generar_hash, verificar_password, crear_token, verificar_token
from fastapi.security import OAuth2PasswordBearer

import models
import schemas
from database import engine, get_db


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def obtener_usuario_actual(                         
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    # Verificamos el token y obtenemos el ID del usuario
    usuario_id = verificar_token(token)

    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o vencido",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Buscamos al usuario en PostgreSQL
    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == int(usuario_id)
    ).first()

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return usuario


@app.get("/")
def inicio():
    return {"mensaje": "API de reserva de canchas funcionando"}


@app.post("/usuarios", response_model=schemas.UsuarioRespuesta)
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
    password=generar_hash(usuario.password)
)

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario

@app.post("/login")
def iniciar_sesion(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Buscamos al usuario por su email
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == form_data.username
    ).first()

    # Verificamos que exista y que la contraseña sea correcta
    if not usuario or not verificar_password(
        form_data.password, usuario.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Email o contraseña incorrectos"
        )

    # Generamos el token JWT
    token = crear_token(usuario.id)

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.get("/usuarios/me", response_model=schemas.UsuarioRespuesta)
def ver_mi_perfil(
    usuario_actual: models.Usuario = Depends(obtener_usuario_actual)
):
    # Devuelve los datos del usuario que inició sesión
    return usuario_actual