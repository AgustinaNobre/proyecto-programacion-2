from datetime import datetime, timedelta, timezone
from decimal import Decimal

import models
from database import SessionLocal


import pytest


@pytest.fixture
def turno_disponible(usuarios):
    """Prepara una cancha y un turno futuro para reservar."""

    db = SessionLocal()

    try:
        actividad = models.Actividad(
            nombre="Fútbol Test",
            descripcion="Actividad para pruebas"
        )

        ubicacion = models.Ubicacion(
            direccion="Dirección de prueba",
            latitud=-34.6,
            longitud=-58.4
        )

        db.add_all([actividad, ubicacion])
        db.flush()

        espacio = models.EspacioDeportivo(
            nombre="Cancha Test",
            tipo=models.TipoEspacio.CANCHA,
            propietario_id=usuarios["propietario"]["id"],
            actividad_id=actividad.id,
            ubicacion_id=ubicacion.id
        )

        db.add(espacio)
        db.flush()

        inicio = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)

        turno = models.Turno(
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio + timedelta(hours=1),
            precio=Decimal("10000"),
            cupo_maximo=3,
            espacio_deportivo_id=espacio.id
        )

        db.add(turno)
        db.commit()
        db.refresh(turno)

        return turno.id

    finally:
        db.close()


def crear_reserva(client, turno_id, headers):
    return client.post(
        "/reservas",
        json={"turno_id": turno_id, "usar_puntos": False},
        headers=headers
    )


def test_crear_reserva(client, usuarios, turno_disponible):
    respuesta = crear_reserva(
        client,
        turno_disponible,
        usuarios["headers_cliente"]
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["turno_id"] == turno_disponible
    assert respuesta.json()["estado"] == "EN_PROCESO"


def test_consultar_reservas_propias(client, usuarios, turno_disponible):
    crear_reserva(client, turno_disponible, usuarios["headers_cliente"])

    respuesta = client.get(
        "/reservas",
        headers=usuarios["headers_cliente"]
    )

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1


def test_cancelar_reserva_propia(client, usuarios, turno_disponible):
    creacion = crear_reserva(
        client,
        turno_disponible,
        usuarios["headers_cliente"]
    )
    reserva_id = creacion.json()["id"]

    respuesta = client.patch(
        f"/reservas/{reserva_id}/cancelar",
        headers=usuarios["headers_cliente"]
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "CANCELADA"


def test_no_cancelar_reserva_de_otro_usuario(
    client, usuarios, turno_disponible
):
    creacion = crear_reserva(
        client,
        turno_disponible,
        usuarios["headers_cliente"]
    )
    reserva_id = creacion.json()["id"]

    otro_usuario = client.post(
        "/usuarios",
        json={
            "nombre": "Otro Cliente",
            "email": "otro@test.com",
            "password": "Password123"
        }
    )
    assert otro_usuario.status_code == 200

    from auth import create_access_token

    token = create_access_token({"sub": str(otro_usuario.json()["id"])})
    headers_otro = {"Authorization": f"Bearer {token}"}

    respuesta = client.patch(
        f"/reservas/{reserva_id}/cancelar",
        headers=headers_otro
    )

    assert respuesta.status_code == 403


def test_no_confirmar_reserva_sin_pago_aprobado(
    client, usuarios, turno_disponible
):
    creacion = crear_reserva(
        client,
        turno_disponible,
        usuarios["headers_cliente"]
    )
    reserva_id = creacion.json()["id"]

    respuesta = client.patch(
        f"/reservas/{reserva_id}/confirmar",
        headers=usuarios["headers_cliente"]
    )

    assert respuesta.status_code == 400
