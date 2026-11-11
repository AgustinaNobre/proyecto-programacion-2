from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException
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
    """Inicia sesión con email y contraseña y devuelve un token JWT.

    El email va en el campo `username` (así lo pide OAuth2).
    Devuelve 401 si el email no existe o la contraseña es incorrecta.
    """
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == form_data.username
    ).first()

    if not usuario or not verify_password(
    form_data.password, usuario.password
):
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
    return usuario_actual

''' @app.get("/prueba-propietario")
def prueba_propietario(
    propietario: models.Usuario = Depends(get_propietario_actual)
):
    return {"mensaje": "Acceso permitido para propietarios"} '''

def _solo_admin(usuario: models.Usuario):
    if usuario.tipo_usuario != models.TipoUsuario.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Solo un administrador puede gestionar el catálogo de deportes")


@app.post("/actividades", response_model=schemas.ActividadRespuesta, status_code=201)
def crear_actividad(
    actividad: schemas.ActividadCrear,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual),
):
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
    return sorted(db.query(models.Actividad).all(), key=lambda a: catalogo.normalizar(a.nombre))


@app.patch("/actividades/{actividad_id}", response_model=schemas.ActividadRespuesta)
def actualizar_actividad(
    actividad_id: int,
    datos: schemas.ActividadActualizar,
    db: Session = Depends(get_db),
    usuario_actual: models.Usuario = Depends(get_usuario_actual),
):
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
    espacios = db.query(models.EspacioDeportivo).filter(
        models.EspacioDeportivo.activa == True
    ).all()

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

    # Aplicar los cambios
    for campo, valor in cambios.items():
        setattr(turno, campo, valor)

    db.commit()
    db.refresh(turno)

    return turno



def _es_admin(usuario: models.Usuario) -> bool:
    return usuario.tipo_usuario == models.TipoUsuario.SUPERADMIN


def _get_admin_actual(usuario: models.Usuario = Depends(get_usuario_actual)) -> models.Usuario:
    if not _es_admin(usuario):
        raise HTTPException(status_code=403, detail="Solo para administradores")
    return usuario


def _es_duenio_del_espacio(usuario: models.Usuario, reserva: models.Reserva) -> bool:
    return reserva.turno.espacio_deportivo.propietario_id == usuario.id


def _buscar_reserva(db: Session, reserva_id: int) -> models.Reserva:
    reserva = db.get(models.Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(status_code=404, detail="La reserva no existe")
    return reserva


def _error_de_regla(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


def _vencer_reservas_sin_pago(db: Session):
    limite = datetime.now(timezone.utc) - timedelta(minutes=models.MINUTOS_PARA_PAGAR)

    vencidas = db.query(models.Reserva).filter(
        models.Reserva.estado == models.EstadoReserva.EN_PROCESO,
        models.Reserva.fecha_creacion < limite,
    ).all()

    for reserva in vencidas:
        reserva.vencer()

    db.commit()


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
    _vencer_reservas_sin_pago(db)

    turno = db.query(models.Turno).filter(
        models.Turno.id == datos.turno_id
    ).with_for_update().first()

    if turno is None:
        raise HTTPException(status_code=404, detail="El turno no existe")

    precio = models.armar_precio(turno, datos.usar_puntos)

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
    propietario.cuenta_cobro = datos.alias_cobro.strip()
    db.commit()
    return _resumen_cobros(db, propietario)


@app.get("/mis-cobros", response_model=schemas.ResumenCobros)
def mis_cobros(
    db: Session = Depends(get_db),
    propietario: models.Usuario = Depends(get_propietario_actual),
):
    return _resumen_cobros(db, propietario)


@app.get("/mis-liquidaciones", response_model=list[schemas.LiquidacionRespuesta])
def mis_liquidaciones(
    db: Session = Depends(get_db),
    propietario: models.Usuario = Depends(get_propietario_actual),
):
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
    db.commit()
    db.refresh(resena)
    return resena