
import httpx
import pytest
from models import Usuario, TipoUsuario, Turno, EspacioDeportivo, Reserva, EstadoReserva
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock


# PRUEBA 1

def test_documentacion_api(client):
    """
    Verifica que FastAPI genere correctamente
    la documentación automática de la API.
    """
    respuesta = client.get("/openapi.json")

    assert respuesta.status_code == 200
    assert "paths" in respuesta.json()

# PRUEBA 2

def test_listar_usuarios(client):
    """
    Verifica que un usuario sin autenticación
    no pueda acceder al listado de usuarios.
    """
    respuesta = client.get("/usuarios")

    assert respuesta.status_code in (401, 403)


# PRUEBA 3

def test_sumar_puntos_usuario():
    """
    Verifica que un usuario pueda acumular puntos
    al finalizar una reserva.
    """
    usuario = Usuario(
        nombre="Cliente de prueba",
        email="cliente_test@example.com",
        password="password_test",
        tipo_usuario=TipoUsuario.CLIENTE,
        puntos=0
    )

    usuario.sumar_puntos(10)

    assert usuario.puntos == 10

# PRUEBA 4

def test_turno_disponible():
    """
    Verifica que un turno futuro esté disponible cuando:
    - El turno está activo.
    - El espacio deportivo está activo.
    - Todavía quedan cupos libres.

    No utiliza la base de datos.
    """

    inicio = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)

    espacio = EspacioDeportivo()
    espacio.activa = True

    turno = Turno(
        fecha_hora_inicio=inicio,
        fecha_hora_fin=inicio + timedelta(hours=1),
        precio=Decimal("25000.00"),
        cupo_maximo=5,
        activo=True,
    )

    turno.espacio_deportivo = espacio
    turno.reservas = []

    assert turno.cupos_disponibles == 5
    assert turno.esta_disponible() is True

# PRUEBA 5

def test_no_reservar_turno_sin_cupos():
    """
    Verifica que no se pueda realizar una reserva
    cuando todos los cupos del turno están ocupados.

    Resultado esperado:
    - No quedan cupos disponibles.
    - El turno no está disponible.
    - Se genera un ValueError al intentar reservar.
    """

    inicio = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)

    espacio = EspacioDeportivo()
    espacio.activa = True

    turno = Turno(
        fecha_hora_inicio=inicio,
        fecha_hora_fin=inicio + timedelta(hours=1),
        precio=Decimal("25000.00"),
        cupo_maximo=1,
        activo=True,
    )

    turno.espacio_deportivo = espacio

    # Simulamos una reserva confirmada que ocupa el único cupo.
    reserva_existente = Reserva(
        usuario_id=1,
        estado=EstadoReserva.CONFIRMADA,
        precio=Decimal("25000.00"),
        puntos_usados=0,
    )

    turno.reservas = [reserva_existente]

    assert turno.cupos_disponibles == 0
    assert turno.esta_disponible() is False

    # Comprobamos que se rechace una nueva reserva.
    with pytest.raises(ValueError, match="El turno no está disponible"):
        turno.reservar(usuario_id=2)


# PRUEBA 6
def test_cupos_disponibles():
    """
    Verifica que un turno sin reservas tenga todos sus cupos disponibles.
    """
    turno = Turno(cupo_maximo=5, activo=True)

    assert turno.cupos_disponibles == 5


# PRUEBA 7
def test_cupos_con_reserva_confirmada():
    """
    Verifica que una reserva confirmada ocupe un cupo.
    """
    turno = Turno(cupo_maximo=3, activo=True)
    turno.reservas.append(
        Reserva(
            usuario_id=1,
            precio=Decimal("25000"),
            estado=EstadoReserva.CONFIRMADA
        )
    )

    assert turno.cupos_disponibles == 2


# PRUEBA 8
def test_usuario_ya_reservo():
    """
    Verifica que se detecte una reserva existente del mismo usuario.
    """
    turno = Turno(cupo_maximo=2, activo=True)
    turno.reservas.append(
        Reserva(
            usuario_id=1,
            precio=Decimal("25000"),
            estado=EstadoReserva.EN_PROCESO
        )
    )

    assert turno.usuario_ya_reservo(1) is True
    assert turno.usuario_ya_reservo(2) is False


# PRUEBA 9
def test_calcular_sena():
    """
    Verifica que la seña se calcule con el porcentaje
    configurado en el sistema.
    """
    from models import PORCENTAJE_SENA

    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        estado=EstadoReserva.EN_PROCESO
    )

    esperado = (
        Decimal("25000") * PORCENTAJE_SENA
    ).quantize(Decimal("0.01"))

    assert reserva.monto_sena() == esperado


# PRUEBA 10
def test_confirmar_reserva():
    """
    Verifica que una reserva en proceso pueda confirmarse.
    Se simulan las notificaciones para no enviar avisos reales.
    """
    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        estado=EstadoReserva.EN_PROCESO
    )

    reserva.notificar = Mock()
    reserva.confirmar()

    assert reserva.estado == EstadoReserva.CONFIRMADA
    reserva.notificar.assert_called_once_with("confirmada")


# PRUEBA 11
def test_no_confirmar_reserva_cancelada():
    """
    Verifica que una reserva cancelada no pueda confirmarse.
    """
    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        estado=EstadoReserva.CANCELADA
    )

    with pytest.raises(ValueError):
        reserva.confirmar()


# PRUEBA 12

def test_finalizar_reserva():
    """
    Verifica que al finalizar una reserva confirmada:
    - Su estado cambie a FINALIZADA.
    - Se acrediten los puntos correspondientes al usuario.
    - Se genere la notificación de finalización.
    """
    from unittest.mock import patch
    from models import Usuario, PUNTOS_POR_RESERVA

    usuario = Usuario()
    reserva = Reserva(
        usuario=usuario,
        precio=Decimal("25000"),
        estado=EstadoReserva.CONFIRMADA
    )

    with patch.object(Usuario, "sumar_puntos") as sumar_puntos:
        with patch.object(Reserva, "notificar") as notificar:
            reserva.finalizar()

    assert reserva.estado == EstadoReserva.FINALIZADA
    sumar_puntos.assert_called_once_with(PUNTOS_POR_RESERVA)
    notificar.assert_called_once_with("finalizada")


# PRUEBA 13
def test_no_finalizar_reserva_en_proceso():
    """
    Verifica que una reserva que todavía no fue confirmada
    no pueda marcarse como finalizada.
    """
    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        estado=EstadoReserva.EN_PROCESO
    )

    with pytest.raises(ValueError, match="Solo se pueden finalizar"):
        reserva.finalizar()

    assert reserva.estado == EstadoReserva.EN_PROCESO


# PRUEBA 14
def test_reserva_sin_pagos_no_fue_reembolsada():
    """
    Verifica que una reserva sin pagos registrados
    no figure como reembolsada.
    """
    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        estado=EstadoReserva.EN_PROCESO
    )

    assert reserva.fue_reembolsada() is False


# PRUEBA 15
def test_reserva_cancelada_no_puede_pagarse():
    """
    Verifica que una reserva cancelada no permita
    registrar nuevos pagos.
    """
    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        estado=EstadoReserva.CANCELADA
    )

    with pytest.raises(ValueError, match="Solo se pueden pagar"):
        reserva.registrar_pago(medio_pago="TARJETA")


# PRUEBA 16

def test_vencer_reserva_en_proceso():
    """
    Verifica que una reserva pendiente de pago
    cambie a CANCELADA cuando vence.
    """
    from unittest.mock import patch

    reserva = Reserva(
        usuario_id=1,
        precio=Decimal("25000"),
        puntos_usados=0,
        estado=EstadoReserva.EN_PROCESO
    )

    with patch.object(Reserva, "notificar") as notificar:
        reserva.vencer()

    assert reserva.estado == EstadoReserva.CANCELADA
    notificar.assert_called_once_with("vencida")



