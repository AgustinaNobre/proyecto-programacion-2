from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from auth import get_password_hash, verify_password, create_access_token, get_usuario_actual, get_propietario_actual
from fastapi.security import OAuth2PasswordRequestForm

import catalogo
import models
import schemas
from database import SessionLocal, engine, get_db


models.Base.metadata.create_all(bind=engine)

with SessionLocal() as _db:
    catalogo.cargar_catalogo(_db)

app = FastAPI()

@app.get("/")
def inicio():
    """Verifica que la API esté funcionando."""
    return {"mensaje": "API de reserva de canchas funcionando"}


@app.post("/usuarios", response_model=schemas.UsuarioRespuesta)
def crear_usuario(usuario: schemas.UsuarioCrear, db: Session = Depends(get_db)):
    """Registra un usuario nuevo (cliente) con la contraseña hasheada.

    Devuelve 400 si el email ya está registrado.
    """
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
    """Inicia sesión con email y contraseña y devuelve un token JWT.

    El email va en el campo `username` (así lo pide OAuth2).
    Devuelve 401 si el email no existe o la contraseña es incorrecta.
    """
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == form_data.username
    ).first()

    if not usuario or not verify_password(form_data.password, usuario.password):
        raise HTTPException(
            status_code=401,
            detail="Email o contraseña incorrectos"
        )

    token = create_access_token({"sub": str(usuario.id)})

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.get("/usuarios/me", response_model=schemas.UsuarioRespuesta)
def ver_mi_perfil(
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    """Devuelve los datos del usuario logueado."""
    return usuario_actual

# Corta con 403 si el usuario no es admin.
def _solo_admin(usuario: models.Usuario):
    if usuario.tipo_usuario != models.TipoUsuario.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Solo un administrador puede gestionar el catálogo de deportes")


@app.post("/actividades", response_model=schemas.ActividadRespuesta, status_code=201)
def crear_actividad(
    actividad: schemas.ActividadCrear,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual),
):
    """Agrega un deporte al catálogo. Solo admin.

    Devuelve 403 si no es admin y 400 si el deporte ya existe
    (sin importar mayúsculas, acentos ni espacios).
    """
    _solo_admin(usuario_actual)

    if catalogo.buscar_por_nombre(db, actividad.nombre):
        raise HTTPException(status_code=400, detail="Ese deporte ya está en el catálogo")

    nueva_actividad = models.Actividad(
        nombre=" ".join(actividad.nombre.split()),
        descripcion=actividad.descripcion.strip() if actividad.descripcion else None,
    )
    db.add(nueva_actividad)
    db.commit()
    db.refresh(nueva_actividad)
    return nueva_actividad


@app.get("/actividades", response_model=list[schemas.ActividadRespuesta])
def listar_actividades(db: Session = Depends(get_db)):
    """Lista los deportes del catálogo, ordenados alfabéticamente."""
    return sorted(db.query(models.Actividad).all(), key=lambda a: catalogo.normalizar(a.nombre))


@app.patch("/actividades/{actividad_id}", response_model=schemas.ActividadRespuesta)
def actualizar_actividad(
    actividad_id: int,
    datos: schemas.ActividadActualizar,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual),
):
    """Edita el nombre o la descripción de un deporte del catálogo. Solo admin.

    Devuelve 403 si no es admin, 404 si el deporte no existe
    y 400 si el nombre nuevo ya lo usa otro deporte.
    """
    _solo_admin(usuario_actual)

    actividad = db.get(models.Actividad, actividad_id)
    if actividad is None:
        raise HTTPException(status_code=404, detail="El deporte no existe")

    if datos.nombre is not None:
        if catalogo.buscar_por_nombre(db, datos.nombre, excluir_id=actividad_id):
            raise HTTPException(status_code=400, detail="Ese deporte ya está en el catálogo")
        actividad.nombre = " ".join(datos.nombre.split())

    if datos.descripcion is not None:
        actividad.descripcion = datos.descripcion.strip() or None

    db.commit()
    db.refresh(actividad)
    return actividad


@app.delete("/actividades/{actividad_id}", status_code=204)
def borrar_actividad(
    actividad_id: int,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual),
):
    """Borra un deporte del catálogo. Solo admin.

    Devuelve 404 si no existe y 400 si hay canchas que lo usan.
    """
    _solo_admin(usuario_actual)

    actividad = db.get(models.Actividad, actividad_id)
    if actividad is None:
        raise HTTPException(status_code=404, detail="El deporte no existe")

    if actividad.espacios:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede borrar: lo usan {len(actividad.espacios)} cancha(s)",
        )

    db.delete(actividad)
    db.commit()


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
    """Crea una ubicación (dirección con latitud y longitud) para asociarla después a una cancha.

    Solo propietarios y admin. Devuelve 403 si el usuario es cliente.
    """
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
    """Publica una cancha del propietario logueado en una ubicación ya creada.

    Solo propietarios y admin. Devuelve 404 si el deporte o la ubicación no existen
    y 422 si el tipo no es CANCHA o SALON.
    """
    if usuario_actual.tipo_usuario not in (
        models.TipoUsuario.PROPIETARIO,
        models.TipoUsuario.SUPERADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos para crear espacios deportivos"
        )

    actividad = db.get(models.Actividad, espacio.actividad_id)

    if actividad is None:
        raise HTTPException(
            status_code=404,
            detail="La actividad no existe"
        )

    ubicacion = db.get(models.Ubicacion, espacio.ubicacion_id)

    if ubicacion is None:
        raise HTTPException(
            status_code=404,
            detail="La ubicación no existe"
        )

    try:
        tipo_espacio = models.TipoEspacio(espacio.tipo)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="El tipo debe ser CANCHA o SALON"
        )

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
    """Lista las canchas activas, con su ubicación y el promedio de reseñas."""
    espacios = db.query(models.EspacioDeportivo).filter(
        models.EspacioDeportivo.activa == True
    ).order_by(models.EspacioDeportivo.id).all()

    return espacios


@app.post(
    "/turnos",
    response_model=schemas.TurnoRespuesta,
    status_code=201
)
def crear_turno(
    turno: schemas.TurnoCrear,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    """Crea un turno para una cancha del propietario logueado.

    Con cupo_maximo 1 es un turno de cancha; con más de 1 es una clase o actividad grupal,
    y el precio pasa a ser por persona.

    Devuelve 403 si la cancha no es suya, 404 si no existe o está inactiva,
    422 si el fin es anterior al inicio y 400 si se superpone con otro turno.
    """
    if usuario_actual.tipo_usuario not in (
        models.TipoUsuario.PROPIETARIO,
        models.TipoUsuario.SUPERADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos para crear turnos"
        )

    espacio = db.get(models.EspacioDeportivo, turno.espacio_deportivo_id)

    if espacio is None or not espacio.activa:
        raise HTTPException(
            status_code=404,
            detail="El espacio deportivo no existe o no está activo"
        )

    if (
        usuario_actual.tipo_usuario != models.TipoUsuario.SUPERADMIN
        and espacio.propietario_id != usuario_actual.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Solo podés crear turnos para tus propios espacios"
        )

    if turno.fecha_hora_fin <= turno.fecha_hora_inicio:
        raise HTTPException(
            status_code=422,
            detail="La fecha y hora de fin deben ser posteriores al inicio"
        )

    turno_superpuesto = db.query(models.Turno).filter(
        models.Turno.espacio_deportivo_id == turno.espacio_deportivo_id,
        models.Turno.activo == True,
        models.Turno.fecha_hora_inicio < turno.fecha_hora_fin,
        models.Turno.fecha_hora_fin > turno.fecha_hora_inicio
    ).first()

    if turno_superpuesto:
        raise HTTPException(
            status_code=400,
            detail="Ya existe un turno en ese horario para este espacio"
        )

    nuevo_turno = models.Turno(
        fecha_hora_inicio=turno.fecha_hora_inicio,
        fecha_hora_fin=turno.fecha_hora_fin,
        precio=turno.precio,
        cupo_maximo=turno.cupo_maximo,
        activo=True,
        espacio_deportivo_id=turno.espacio_deportivo_id
    )

    db.add(nuevo_turno)
    db.commit()
    db.refresh(nuevo_turno)

    return nuevo_turno


@app.get(
    "/turnos",
    response_model=list[schemas.TurnoRespuesta]
)
def listar_turnos(db: Session = Depends(get_db)):
    """Lista los turnos disponibles: activos, de canchas activas y con cupo libre.

    Antes vence las reservas que no se pagaron a tiempo, para liberar esos turnos.
    """
    # Actualizar las reservas que vencieron por falta de pago
    _vencer_reservas_sin_pago(db)
    turnos = db.query(models.Turno).join(
        models.EspacioDeportivo
    ).filter(
        models.Turno.activo == True,
        models.EspacioDeportivo.activa == True
    ).all()

    turnos_disponibles = [
        turno for turno in turnos
        if turno.esta_disponible()
    ]

    return turnos_disponibles


@app.get(
    "/turnos/{id}",
    response_model=schemas.TurnoRespuesta
)
def obtener_turno(
    id: int,
    db: Session = Depends(get_db)
):
    """Devuelve un turno por su id. Devuelve 404 si no existe."""
    turno = db.get(models.Turno, id)

    if turno is None:
        raise HTTPException(
            status_code=404,
            detail="El turno no existe"
        )

    return turno


@app.patch(
    "/turnos/{id}",
    response_model=schemas.TurnoRespuesta
)
def actualizar_turno(
    id: int,
    datos: schemas.TurnoActualizar,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual)
):
    """Edita un turno (horario, precio, cupo o si está activo). Solo el dueño de la cancha o el admin.

    Si se desactiva el turno, se cancelan sus reservas, se devuelven las señas y se avisa a cada cliente.
    Devuelve 404 si no existe, 403 si no es el dueño, 422 si el fin es anterior al inicio
    y 400 si el horario se superpone con otro turno o si el cupo nuevo es menor que las reservas hechas.
    """
    turno = db.get(models.Turno, id)

    if turno is None:
        raise HTTPException(
            status_code=404,
            detail="El turno no existe"
        )

    espacio = db.get(
        models.EspacioDeportivo,
        turno.espacio_deportivo_id
    )

    if espacio is None:
        raise HTTPException(
            status_code=404,
            detail="El espacio deportivo no existe"
        )

    if usuario_actual.tipo_usuario not in (
        models.TipoUsuario.PROPIETARIO,
        models.TipoUsuario.SUPERADMIN
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos para modificar turnos"
        )

    if (
        usuario_actual.tipo_usuario != models.TipoUsuario.SUPERADMIN
        and espacio.propietario_id != usuario_actual.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Solo podés modificar turnos de tus propios espacios"
        )

    cambios = datos.model_dump(exclude_unset=True)

    fecha_inicio = cambios.get(
        "fecha_hora_inicio",
        turno.fecha_hora_inicio
    )
    fecha_fin = cambios.get(
        "fecha_hora_fin",
        turno.fecha_hora_fin
    )

    if fecha_fin <= fecha_inicio:
        raise HTTPException(
            status_code=422,
            detail="La fecha y hora de fin deben ser posteriores al inicio"
        )

    turno_activo = cambios.get("activo", turno.activo)

    if turno_activo:
        turno_superpuesto = db.query(models.Turno).filter(
            models.Turno.espacio_deportivo_id == turno.espacio_deportivo_id,
            models.Turno.id != turno.id,
            models.Turno.activo == True,
            models.Turno.fecha_hora_inicio < fecha_fin,
            models.Turno.fecha_hora_fin > fecha_inicio
        ).first()

        if turno_superpuesto:
            raise HTTPException(
                status_code=400,
                detail="Ya existe otro turno en ese horario para este espacio"
            )

    ocupados = turno.cupo_maximo - turno.cupos_disponibles
    if cambios.get("cupo_maximo") is not None and cambios["cupo_maximo"] < ocupados:
        raise HTTPException(
            status_code=400,
            detail=f"Ya hay {ocupados} reserva(s) en este turno: el cupo no puede ser menor"
        )

    # Si se da de baja el turno, se cancelan sus reservas y se devuelven las señas
    if turno.activo and turno_activo is False:
        for reserva in turno.reservas:
            reserva.anular()

    for campo, valor in cambios.items():
        setattr(turno, campo, valor)

    db.commit()
    db.refresh(turno)

    return turno



# Indica si el usuario es admin.
def _es_admin(usuario: models.Usuario) -> bool:
    return usuario.tipo_usuario == models.TipoUsuario.SUPERADMIN


# Dependencia para endpoints de admin: devuelve el usuario o corta con 403.
def _get_admin_actual(usuario: models.Usuario = Depends(get_usuario_actual)) -> models.Usuario:
    if not _es_admin(usuario):
        raise HTTPException(status_code=403, detail="Solo para administradores")
    return usuario


# Indica si el usuario es dueño de la cancha de esa reserva.
def _es_duenio_del_espacio(usuario: models.Usuario, reserva: models.Reserva) -> bool:
    return reserva.turno.espacio_deportivo.propietario_id == usuario.id


# Busca una reserva por id o corta con 404.
def _buscar_reserva(db: Session, reserva_id: int) -> models.Reserva:
    reserva = db.get(models.Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(status_code=404, detail="La reserva no existe")
    return reserva


# Convierte un error de regla de negocio (ValueError) en un error 400.
def _error_de_regla(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


# Vence las reservas que no se pagaron dentro del plazo, para liberar el turno.
def _vencer_reservas_sin_pago(db: Session):
    limite = datetime.now(timezone.utc) - timedelta(minutes=models.MINUTOS_PARA_PAGAR)

    vencidas = db.query(models.Reserva).filter(
        models.Reserva.estado == models.EstadoReserva.EN_PROCESO,
        models.Reserva.fecha_creacion < limite,
    ).all()

    for reserva in vencidas:
        reserva.vencer()

    db.commit()


# Resumen de lo que cobra un propietario.
# La seña la cobra la app, se queda con su comisión y le liquida el resto al propietario.
def _resumen_cobros(db: Session, propietario: models.Usuario) -> schemas.ResumenCobros:
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    limite_reembolso = timedelta(hours=models.HORAS_LIMITE_REEMBOLSO)

    pagos = (
        db.query(models.Pago)
        .join(models.Reserva)
        .join(models.Turno)
        .join(models.EspacioDeportivo)
        .filter(
            models.EspacioDeportivo.propietario_id == propietario.id,
            models.Pago.estado_pago == models.EstadoPago.APROBADO,
        )
        .all()
    )

    a_confirmar = Decimal("0")
    confirmado = Decimal("0")
    for pago in pagos:
        parte_propietario = pago.monto - pago.comision
        # Si todavía se puede reembolsar, la plata no es segura
        if pago.reserva.turno.fecha_hora_inicio - ahora >= limite_reembolso:
            a_confirmar += parte_propietario
        else:
            confirmado += parte_propietario

    liquidado = sum(
        (l.monto for l in db.query(models.Liquidacion).filter(
            models.Liquidacion.propietario_id == propietario.id
        )),
        Decimal("0"),
    )

    return schemas.ResumenCobros(
        alias_cobro=propietario.cuenta_cobro,
        a_confirmar=a_confirmar,
        confirmado=confirmado,
        liquidado=liquidado,
        saldo_a_cobrar=confirmado - liquidado,
    )


@app.post("/reservas", response_model=schemas.ReservaRespuesta, status_code=201)
def reservar_turno(
    datos: schemas.ReservaCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Reserva un turno para el usuario logueado.

    Calcula el precio con los descuentos que correspondan (patrón Decorator) y,
    si se pide, canjea puntos. La reserva queda esperando el pago de la seña.
    Devuelve 404 si el turno no existe y 400 si no se puede reservar
    (turno lleno, pasado o puntos insuficientes).
    """
    _vencer_reservas_sin_pago(db)

    turno = db.query(models.Turno).filter(
        models.Turno.id == datos.turno_id
    ).with_for_update().first()  # Bloquea el turno para que dos personas no lo reserven a la vez

    if turno is None:
        raise HTTPException(status_code=404, detail="El turno no existe")

    precio = models.armar_precio(turno, datos.usar_puntos)  # Patrón Decorator: precio base + descuentos

    try:
        puntos_usados = 0
        if datos.usar_puntos:
            usuario.canjear_puntos(models.PUNTOS_PARA_DESCUENTO)
            puntos_usados = models.PUNTOS_PARA_DESCUENTO

        reserva = turno.reservar(
            usuario.id,
            precio=precio.calcular(),
            puntos_usados=puntos_usados
        )
    except ValueError as e:
        _error_de_regla(e)

    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva


@app.get("/reservas", response_model=list[schemas.ReservaRespuesta])
@app.get("/reservas/mis-reservas", response_model=list[schemas.ReservaRespuesta])
def mis_reservas(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Devuelve las reservas del usuario logueado, de la más nueva a la más vieja."""
    _vencer_reservas_sin_pago(db)
    return (
        db.query(models.Reserva)
        .filter(models.Reserva.usuario_id == usuario.id)
        .order_by(models.Reserva.fecha_creacion.desc())
        .all()
    )


@app.post("/reservas/{reserva_id}/cancelar", response_model=schemas.ReservaRespuesta)
@app.patch("/reservas/{reserva_id}/cancelar", response_model=schemas.ReservaRespuesta)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Cancela una reserva. Si faltan 48 horas o más para el turno, se reembolsa la seña.

    Solo el dueño de la reserva o el admin. Devuelve 403 si es de otro usuario
    y 400 si la reserva ya no se puede cancelar.
    """
    _vencer_reservas_sin_pago(db)
    reserva = _buscar_reserva(db, reserva_id)
    if reserva.usuario_id != usuario.id and not _es_admin(usuario):
        raise HTTPException(status_code=403, detail="Solo podés cancelar tus propias reservas")

    try:
        reserva.cancelar()
    except ValueError as e:
        _error_de_regla(e)

    db.commit()
    db.refresh(reserva)
    return reserva

@app.patch("/reservas/{reserva_id}/confirmar", response_model=schemas.ReservaRespuesta)
def confirmar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Confirma una reserva que ya tiene un pago aprobado.

    Devuelve 403 si es de otro usuario y 400 si no tiene pago aprobado.
    """
    reserva = _buscar_reserva(db, reserva_id)

    # Cada cliente solo puede confirmar sus propias reservas
    if reserva.usuario_id != usuario.id and not _es_admin(usuario):
        raise HTTPException(
            status_code=403,
            detail="Solo podés confirmar tus propias reservas"
        )

    # Verificar que exista un pago aprobado
    tiene_pago_aprobado = any(
        pago.estado_pago == models.EstadoPago.APROBADO
        for pago in reserva.pagos
    )

    if not tiene_pago_aprobado:
        raise HTTPException(
            status_code=400,
            detail="No podés confirmar una reserva sin un pago aprobado"
        )

    # Si el pago ya confirmó la reserva, no hacemos nada más
    if reserva.estado == models.EstadoReserva.CONFIRMADA:
        return reserva

    try:
        reserva.confirmar()
    except ValueError as e:
        _error_de_regla(e)

    db.commit()
    db.refresh(reserva)
    return reserva

@app.post("/reservas/{reserva_id}/finalizar", response_model=schemas.ReservaRespuesta)
def finalizar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Marca una reserva como jugada y le suma puntos al cliente. Solo el dueño de la cancha o el admin.

    Devuelve 403 si no es el dueño y 400 si la reserva no está confirmada.
    """
    reserva = _buscar_reserva(db, reserva_id)
    if not _es_duenio_del_espacio(usuario, reserva) and not _es_admin(usuario):
        raise HTTPException(status_code=403, detail="Solo el propietario de la cancha puede finalizar la reserva")

    try:
        reserva.finalizar()
    except ValueError as e:
        _error_de_regla(e)

    db.commit()
    db.refresh(reserva)
    return reserva


@app.post("/reservas/{reserva_id}/pago", response_model=schemas.PagoRespuesta, status_code=201)
def pagar_sena(
    reserva_id: int,
    datos: schemas.PagoCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Registra el pago de la seña (20% del total). Se aprueba automáticamente y confirma la reserva.

    Devuelve 403 si la reserva es de otro usuario y 400 si ya venció el plazo
    para pagar o ya estaba pagada.
    """
    _vencer_reservas_sin_pago(db)
    reserva = _buscar_reserva(db, reserva_id)
    if reserva.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="Solo podés pagar tus propias reservas")

    try:
        pago = reserva.registrar_pago(datos.medio_pago, datos.referencia_externa)   
    except ValueError as e:
        _error_de_regla(e)

    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


@app.get("/reservas/{reserva_id}/pagos", response_model=list[schemas.PagoRespuesta])
def ver_pagos_de_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Lista los pagos de una reserva. Pueden verlos el cliente, el dueño de la cancha o el admin."""
    reserva = _buscar_reserva(db, reserva_id)
    puede_ver = (
        reserva.usuario_id == usuario.id
        or _es_duenio_del_espacio(usuario, reserva)
        or _es_admin(usuario)
    )
    if not puede_ver:
        raise HTTPException(status_code=403, detail="No tenés acceso a esta reserva")
    return reserva.pagos


@app.put("/usuarios/me/alias-cobro", response_model=schemas.ResumenCobros)
def cargar_alias_cobro(
    datos: schemas.AliasCobro,
    db: Session = Depends(get_db),
    propietario: models.Usuario = Depends(get_propietario_actual),
):
    """Guarda el CBU o alias donde el propietario recibe sus cobros y devuelve su resumen."""
    propietario.cuenta_cobro = datos.alias_cobro.strip()
    db.commit()
    return _resumen_cobros(db, propietario)


@app.get("/mis-cobros", response_model=schemas.ResumenCobros)
def mis_cobros(
    db: Session = Depends(get_db),
    propietario: models.Usuario = Depends(get_propietario_actual),
):
    """Devuelve el resumen de cobros del propietario logueado."""
    return _resumen_cobros(db, propietario)


@app.get("/mis-liquidaciones", response_model=list[schemas.LiquidacionRespuesta])
def mis_liquidaciones(
    db: Session = Depends(get_db),
    propietario: models.Usuario = Depends(get_propietario_actual),
):
    """Lista las transferencias que la app ya le hizo al propietario logueado."""
    return (
        db.query(models.Liquidacion)
        .filter(models.Liquidacion.propietario_id == propietario.id)
        .order_by(models.Liquidacion.fecha.desc())
        .all()
    )


@app.get("/liquidaciones/pendientes", response_model=list[schemas.PropietarioACobrar])
def propietarios_a_liquidar(
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(_get_admin_actual),
):
    """Lista los propietarios con saldo a cobrar. Solo admin."""
    propietarios = db.query(models.Usuario).filter(
        models.Usuario.tipo_usuario == models.TipoUsuario.PROPIETARIO
    ).all()

    pendientes = []
    for p in propietarios:
        saldo = _resumen_cobros(db, p).saldo_a_cobrar
        if saldo > 0:
            pendientes.append(schemas.PropietarioACobrar(
                propietario_id=p.id, nombre=p.nombre,
                alias_cobro=p.cuenta_cobro, saldo_a_cobrar=saldo,
            ))
    return pendientes


@app.post("/liquidaciones", response_model=schemas.LiquidacionRespuesta, status_code=201)
def registrar_liquidacion(
    datos: schemas.LiquidacionCrear,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(_get_admin_actual),
):
    """Registra una transferencia de la app a un propietario. Solo admin.

    Si no se indica monto, liquida todo el saldo. Devuelve 404 si el propietario no existe
    y 400 si no cargó su alias, no tiene saldo o el monto supera el saldo.
    """
    propietario = db.get(models.Usuario, datos.propietario_id)
    if propietario is None or propietario.tipo_usuario != models.TipoUsuario.PROPIETARIO:
        raise HTTPException(status_code=404, detail="El propietario no existe")

    if not propietario.cuenta_cobro:
        raise HTTPException(status_code=400, detail="El propietario no cargó su CBU/alias de cobro")

    saldo = _resumen_cobros(db, propietario).saldo_a_cobrar
    monto = datos.monto if datos.monto is not None else saldo

    if monto <= 0:
        raise HTTPException(status_code=400, detail="El propietario no tiene saldo para liquidar")
    if monto > saldo:
        raise HTTPException(status_code=400, detail=f"El monto supera el saldo a cobrar ({saldo})")

    liquidacion = models.Liquidacion(
        propietario_id=propietario.id,
        monto=monto,
        alias_destino=propietario.cuenta_cobro,
        referencia_externa=datos.referencia_externa,
    )
    monto_texto = f"{monto:,.0f}".replace(",", ".")
    propietario.notificaciones.append(models.Notificacion(
        mensaje=f"Te transferimos ${monto_texto} a {propietario.cuenta_cobro}."
    ))
    db.add(liquidacion)
    db.commit()
    db.refresh(liquidacion)
    return liquidacion


@app.get("/turnos/{turno_id}/precio", response_model=schemas.PrecioDetalle)
def ver_precio_turno(
    turno_id: int,
    usar_puntos: bool = False,
    db: Session = Depends(get_db),
):
    """Muestra el precio final de un turno, la seña a pagar y el detalle de los descuentos aplicados."""
    turno = db.get(models.Turno, turno_id)
    if turno is None:
        raise HTTPException(status_code=404, detail="El turno no existe")

    precio = models.armar_precio(turno, usar_puntos)
    total = precio.calcular()
    return schemas.PrecioDetalle(
        total=total,
        sena=(total * models.PORCENTAJE_SENA).quantize(Decimal("0.01")),
        detalle=precio.detalle(),
    )


@app.get("/espacios-deportivos/{espacio_id}/resenas", response_model=list[schemas.ResenaRespuesta])
def listar_resenas(espacio_id: int, db: Session = Depends(get_db)):
    """Lista las reseñas de una cancha, de la más nueva a la más vieja."""
    espacio = db.get(models.EspacioDeportivo, espacio_id)
    if espacio is None:
        raise HTTPException(status_code=404, detail="La cancha no existe")

    return (
        db.query(models.Resena)
        .filter(models.Resena.espacio_deportivo_id == espacio_id)
        .order_by(models.Resena.fecha.desc())
        .all()
    )


@app.post("/espacios-deportivos/{espacio_id}/resenas", response_model=schemas.ResenaRespuesta, status_code=201)
def crear_resena(
    espacio_id: int,
    datos: schemas.ResenaCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Deja una reseña (puntaje de 1 a 5 y comentario opcional) sobre una cancha.

    Solo si el usuario ya jugó ahí (tiene una reserva finalizada).
    Devuelve 404 si la cancha no existe, 403 si nunca jugó ahí y 400 si ya dejó una reseña.
    """
    espacio = db.get(models.EspacioDeportivo, espacio_id)
    if espacio is None:
        raise HTTPException(status_code=404, detail="La cancha no existe")

    if not espacio.jugo_aca(usuario.id):
        raise HTTPException(status_code=403, detail="Solo podés opinar sobre canchas en las que jugaste")

    ya_opino = db.query(models.Resena).filter(
        models.Resena.usuario_id == usuario.id,
        models.Resena.espacio_deportivo_id == espacio_id,
    ).first()
    if ya_opino:
        raise HTTPException(status_code=400, detail="Ya dejaste una reseña para esta cancha")

    resena = models.Resena(
        usuario_id=usuario.id,
        espacio_deportivo_id=espacio_id,
        puntaje=datos.puntaje,
        comentario=datos.comentario.strip() if datos.comentario else None,
    )
    db.add(resena)
    db.flush()

    cantidad_resenas = db.query(models.Resena).filter(models.Resena.usuario_id == usuario.id).count()
    if cantidad_resenas >= 3:
        usuario.desbloquear_logro("critico")

    db.commit()
    db.refresh(resena)
    return resena


@app.get("/notificaciones", response_model=list[schemas.NotificacionRespuesta])
def mis_notificaciones(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Devuelve las últimas 30 notificaciones del usuario logueado, de la más nueva a la más vieja."""
    _vencer_reservas_sin_pago(db)
    return (
        db.query(models.Notificacion)
        .filter(models.Notificacion.usuario_id == usuario.id)
        .order_by(models.Notificacion.fecha.desc(), models.Notificacion.id.desc())
        .limit(30)
        .all()
    )


@app.patch("/notificaciones/leer-todas", status_code=204)
def leer_todas_las_notificaciones(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Marca como leídas todas las notificaciones del usuario logueado."""
    db.query(models.Notificacion).filter(
        models.Notificacion.usuario_id == usuario.id,
        models.Notificacion.leida == False,
    ).update({"leida": True})
    db.commit()


@app.get("/usuarios", response_model=list[schemas.UsuarioRespuesta])
def listar_usuarios(
    buscar: str | None = None,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(_get_admin_actual),
):
    """Lista los usuarios, filtrando por nombre o email si se indica `buscar`. Solo admin."""
    consulta = db.query(models.Usuario)
    if buscar:
        patron = f"%{buscar.strip()}%"
        consulta = consulta.filter(
            models.Usuario.email.ilike(patron) | models.Usuario.nombre.ilike(patron)
        )
    return consulta.order_by(models.Usuario.nombre).limit(50).all()


@app.patch("/usuarios/rol", response_model=schemas.UsuarioRespuesta)
def cambiar_rol(
    datos: schemas.CambioRol,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(_get_admin_actual),
):
    """Convierte a un usuario en propietario, o lo vuelve a cliente. Solo admin.

    El usuario tiene que estar registrado. Devuelve 404 si no existe, 400 si es administrador
    y 400 si se lo quiere volver cliente pero todavía tiene canchas publicadas.
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="No hay ningún usuario registrado con ese email")

    if usuario.tipo_usuario == models.TipoUsuario.SUPERADMIN:
        raise HTTPException(status_code=400, detail="No se puede cambiar el rol de un administrador")

    nuevo_rol = models.TipoUsuario(datos.tipo_usuario)
    if usuario.tipo_usuario == nuevo_rol:
        return usuario

    canchas_activas = [e for e in usuario.espacios if e.activa]
    if nuevo_rol == models.TipoUsuario.CLIENTE and canchas_activas:
        raise HTTPException(
            status_code=400,
            detail=f"Tiene {len(canchas_activas)} cancha(s) publicada(s): primero hay que darlas de baja"
        )

    usuario.tipo_usuario = nuevo_rol
    mensaje = (
        "¡Ya sos propietario! Desde Mi complejo podés publicar tus canchas y cargar turnos."
        if nuevo_rol == models.TipoUsuario.PROPIETARIO
        else "Tu cuenta volvió a ser de cliente."
    )
    usuario.notificaciones.append(models.Notificacion(mensaje=mensaje))

    db.commit()
    db.refresh(usuario)
    return usuario


@app.get("/usuarios/me/logros", response_model=list[schemas.LogroRespuesta])
def mis_logros(usuario: models.Usuario = Depends(get_usuario_actual)):
    """Lista los logros secretos del usuario logueado.

    Los que todavía no ganó se devuelven ocultos ("???"), para que sean una sorpresa.
    `veces` indica cuántas veces se ganó (los repetibles, como "En racha", pueden ser más de una).
    """
    logros = []
    for codigo, (emoji, nombre, descripcion, puntos) in models.LOGROS.items():
        veces = sum(1 for l in usuario.logros if l.codigo == codigo)
        if veces:
            logros.append(schemas.LogroRespuesta(
                codigo=codigo, emoji=emoji, nombre=nombre, descripcion=descripcion,
                puntos=puntos, ganado=True, veces=veces,
            ))
        else:
            logros.append(schemas.LogroRespuesta(
                codigo=codigo, emoji="❔", nombre="???", descripcion="Logro secreto. Seguí jugando para descubrirlo.",
                puntos=puntos, ganado=False,
            ))
    return logros


# Busca un espacio y verifica que el usuario sea su dueño (o admin)
def _espacio_propio(db: Session, espacio_id: int, usuario: models.Usuario) -> models.EspacioDeportivo:
    espacio = db.get(models.EspacioDeportivo, espacio_id)
    if espacio is None:
        raise HTTPException(status_code=404, detail="El espacio deportivo no existe")
    if espacio.propietario_id != usuario.id and not _es_admin(usuario):
        raise HTTPException(status_code=403, detail="Solo podés modificar tus propios espacios")
    return espacio


@app.patch("/espacios-deportivos/{espacio_id}", response_model=schemas.EspacioDeportivoRespuesta)
def actualizar_espacio_deportivo(
    espacio_id: int,
    datos: schemas.EspacioDeportivoActualizar,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Edita el nombre, el tipo (CANCHA o SALON) o el deporte de un espacio. Solo su dueño o el admin.

    Devuelve 404 si el espacio o el deporte no existen y 403 si el espacio es de otro propietario.
    """
    espacio = _espacio_propio(db, espacio_id, usuario)

    if datos.actividad_id is not None and db.get(models.Actividad, datos.actividad_id) is None:
        raise HTTPException(status_code=404, detail="El deporte no existe")

    if datos.nombre is not None:
        espacio.nombre = " ".join(datos.nombre.split())
    if datos.tipo is not None:
        espacio.tipo = models.TipoEspacio(datos.tipo)
    if datos.actividad_id is not None:
        espacio.actividad_id = datos.actividad_id

    db.commit()
    db.refresh(espacio)
    return espacio


@app.post("/espacios-deportivos/{espacio_id}/fotos", response_model=schemas.FotoRespuesta, status_code=201)
def subir_foto(
    espacio_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Sube una foto (JPG, PNG o WEBP, hasta 2 MB) a un espacio. Solo su dueño o el admin.

    Cada espacio puede tener hasta 6 fotos; la primera se usa como portada.
    Devuelve 404 si el espacio no existe, 403 si es de otro propietario y 400 si el archivo
    no es una imagen válida, pesa demasiado o ya se llegó al máximo de fotos.
    """
    espacio = _espacio_propio(db, espacio_id, usuario)

    if len(espacio.fotos) >= models.MAX_FOTOS_POR_ESPACIO:
        raise HTTPException(status_code=400, detail=f"Cada espacio puede tener hasta {models.MAX_FOTOS_POR_ESPACIO} fotos")

    datos = archivo.file.read(models.MAX_BYTES_FOTO + 1)
    if len(datos) > models.MAX_BYTES_FOTO:
        raise HTTPException(status_code=400, detail="La foto no puede pesar más de 2 MB")

    if datos.startswith(b"\xff\xd8\xff"):
        tipo_contenido = "image/jpeg"
    elif datos.startswith(b"\x89PNG\r\n\x1a\n"):
        tipo_contenido = "image/png"
    elif datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        tipo_contenido = "image/webp"
    else:
        raise HTTPException(status_code=400, detail="La foto tiene que ser JPG, PNG o WEBP")

    foto = models.FotoEspacio(tipo_contenido=tipo_contenido, datos=datos)
    espacio.fotos.append(foto)
    db.commit()
    db.refresh(foto)
    return foto


@app.get("/fotos/{foto_id}", response_class=Response)
def ver_foto(foto_id: int, db: Session = Depends(get_db)):
    """Devuelve la imagen de una foto. Es pública, para poder mostrarla en la lista de espacios."""
    foto = db.get(models.FotoEspacio, foto_id)
    if foto is None:
        raise HTTPException(status_code=404, detail="La foto no existe")
    return Response(
        content=foto.datos,
        media_type=foto.tipo_contenido,
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@app.delete("/fotos/{foto_id}", status_code=204)
def borrar_foto(
    foto_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_actual),
):
    """Borra una foto de un espacio. Solo el dueño del espacio o el admin."""
    foto = db.get(models.FotoEspacio, foto_id)
    if foto is None:
        raise HTTPException(status_code=404, detail="La foto no existe")
    _espacio_propio(db, foto.espacio_deportivo_id, usuario)
    db.delete(foto)
    db.commit()