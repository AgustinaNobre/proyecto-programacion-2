from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from auth import get_password_hash, verify_password, create_access_token, get_usuario_actual, get_propietario_actual
from fastapi.security import OAuth2PasswordRequestForm

import models
import schemas
from database import engine, get_db


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

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
    password=get_password_hash(usuario.password)
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
    if not usuario or not verify_password(
    form_data.password, usuario.password
):
        raise HTTPException(
            status_code=401,
            detail="Email o contraseña incorrectos"
        )

    # Generamos el token JWT
    token = create_access_token({"sub": str(usuario.id)})

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.get("/usuarios/me", response_model=schemas.UsuarioRespuesta)
def ver_mi_perfil(
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    # Devuelve los datos del usuario que inició sesión
    return usuario_actual

''' @app.get("/prueba-propietario")
def prueba_propietario(
    propietario: models.Usuario = Depends(get_propietario_actual)
):
    return {"mensaje": "Acceso permitido para propietarios"} '''

@app.post(
    "/actividades",
    response_model=schemas.ActividadRespuesta,
    status_code=201
)
def crear_actividad(
    actividad: schemas.ActividadCrear,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    if usuario_actual.tipo_usuario not in (
        models.TipoUsuario.PROPIETARIO,
        models.TipoUsuario.SUPERADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos para crear actividades"
        )

    actividad_existente = db.query(models.Actividad).filter(
        models.Actividad.nombre == actividad.nombre
    ).first()

    if actividad_existente:
        raise HTTPException(
            status_code=400,
            detail="La actividad ya existe"
        )
    
    
    nueva_actividad = models.Actividad(
        nombre=actividad.nombre,
        descripcion=actividad.descripcion
    )

    db.add(nueva_actividad)
    db.commit()
    db.refresh(nueva_actividad)

    return {
        "id": nueva_actividad.id,
        "nombre": nueva_actividad.nombre,
        "descripcion": nueva_actividad.descripcion
    }

@app.get(
    "/actividades",
    response_model=list[schemas.ActividadRespuesta]
)
def listar_actividades(db: Session = Depends(get_db)):
    actividades = db.query(models.Actividad).all()

    return actividades


@app.post(
    "/ubicaciones",
    response_model=schemas.UbicacionRespuesta,
    status_code=201
)
def crear_ubicacion(
    ubicacion: schemas.UbicacionCrear,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    # Solo propietarios y administradores pueden crear ubicaciones
    if usuario_actual.tipo_usuario not in (
        models.TipoUsuario.PROPIETARIO,
        models.TipoUsuario.SUPERADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos para crear ubicaciones"
        )

    nueva_ubicacion = models.Ubicacion(
        direccion=ubicacion.direccion,
        latitud=ubicacion.latitud,
        longitud=ubicacion.longitud
    )

    db.add(nueva_ubicacion)
    db.commit()
    db.refresh(nueva_ubicacion)

    return nueva_ubicacion


@app.post(
    "/espacios-deportivos",
    response_model=schemas.EspacioDeportivoRespuesta,
    status_code=201
)
def crear_espacio_deportivo(
    espacio: schemas.EspacioDeportivoCrear,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    # Verificamos que sea propietario o administrador
    if usuario_actual.tipo_usuario not in (
        models.TipoUsuario.PROPIETARIO,
        models.TipoUsuario.SUPERADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos para crear espacios deportivos"
        )

    # Comprobamos que la actividad exista
    actividad = db.get(models.Actividad, espacio.actividad_id)

    if actividad is None:
        raise HTTPException(
            status_code=404,
            detail="La actividad no existe"
        )

    # Comprobamos que la ubicación exista
    ubicacion = db.get(models.Ubicacion, espacio.ubicacion_id)

    if ubicacion is None:
        raise HTTPException(
            status_code=404,
            detail="La ubicación no existe"
        )

    # Validamos el tipo de espacio
    try:
        tipo_espacio = models.TipoEspacio(espacio.tipo)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="El tipo debe ser CANCHA o SALON"
        )

    # Creamos el espacio deportivo
    nuevo_espacio = models.EspacioDeportivo(
        nombre=espacio.nombre,
        tipo=tipo_espacio,
        activa=True,
        propietario_id=usuario_actual.id,
        actividad_id=espacio.actividad_id,
        ubicacion_id=espacio.ubicacion_id
    )

    db.add(nuevo_espacio)
    db.commit()
    db.refresh(nuevo_espacio)

    return nuevo_espacio


@app.get(
    "/espacios-deportivos",
    response_model=list[schemas.EspacioDeportivoRespuesta]
)
def listar_espacios_deportivos(
    db: Session = Depends(get_db)
):
    espacios = db.query(models.EspacioDeportivo).filter(
        models.EspacioDeportivo.activa == True
    ).all()

    return espacios



