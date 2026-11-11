import os

# Forzar el uso de la base de datos exclusiva para pruebas.
os.environ["DB_NAME"] = "test_reserva_canchas"
os.environ.setdefault("SECRET_KEY", "clave-secreta-para-tests-de-32-bytes")

import pytest
from fastapi.testclient import TestClient

import models
from database import Base, engine
from main import app
from auth import create_access_token


@pytest.fixture(autouse=True)
def limpiar_base():
    """Deja la base de pruebas limpia antes de cada test."""
    assert engine.url.database == "test_reserva_canchas", (
        "Los tests deben ejecutarse exclusivamente en test_reserva_canchas"
    )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def usuarios(client):
    """Crea un cliente y un propietario autenticados."""

    respuesta_cliente = client.post(
        "/usuarios",
        json={
            "nombre": "Cliente Test",
            "email": "cliente@test.com",
            "password": "Password123"
        }
    )
    assert respuesta_cliente.status_code == 200, respuesta_cliente.text
    cliente = respuesta_cliente.json()

    respuesta_propietario = client.post(
        "/usuarios",
        json={
            "nombre": "Propietario Test",
            "email": "propietario@test.com",
            "password": "Password123"
        }
    )
    assert respuesta_propietario.status_code == 200, respuesta_propietario.text
    propietario = respuesta_propietario.json()

    # Darle al segundo usuario el rol de propietario.
    from database import SessionLocal

    db = SessionLocal()
    try:
        usuario_db = db.get(models.Usuario, propietario["id"])
        usuario_db.tipo_usuario = models.TipoUsuario.PROPIETARIO
        db.commit()
    finally:
        db.close()

    token_cliente = create_access_token({"sub": str(cliente["id"])})
    token_propietario = create_access_token({"sub": str(propietario["id"])})

    return {
        "cliente": cliente,
        "propietario": propietario,
        "headers_cliente": {"Authorization": f"Bearer {token_cliente}"},
        "headers_propietario": {"Authorization": f"Bearer {token_propietario}"}
    }
