import unicodedata

from sqlalchemy.orm import Session

import models


CATALOGO_DEPORTES = [
    ("Fútbol 5", "Fútbol de 5 jugadores por equipo, en cancha chica de césped sintético."),
    ("Fútbol 7", "Fútbol de 7 jugadores por equipo, en cancha mediana."),
    ("Fútbol 8", "Fútbol de 8 jugadores por equipo, en cancha mediana."),
    ("Fútbol 11", "Fútbol de 11 jugadores por equipo, en cancha reglamentaria."),
    ("Futsal", "Fútbol de salón de 5 jugadores, en piso de parquet o sintético."),
    ("Fútbol tenis", "Se juega con los pies sobre una red baja, de a 1, 2 o 3 por lado."),
    ("Pádel", "Se juega en parejas, en cancha cerrada con paredes de vidrio."),
    ("Tenis", "Single o dobles, en cancha de polvo de ladrillo, cemento o césped."),
    ("Pickleball", "Mezcla de tenis, pádel y ping pong, en cancha chica con paleta."),
    ("Squash", "Se juega en una cancha cerrada, golpeando la pelota contra la pared."),
    ("Frontón", "Pelota paleta o frontón a mano, contra una pared."),
    ("Tenis de mesa", "Ping pong, en mesa reglamentaria."),
    ("Bádminton", "Se juega con raqueta y volante, sobre una red alta."),
    ("Básquet", "Básquet de 5 contra 5, en cancha completa."),
    ("Básquet 3x3", "Básquet de 3 contra 3, en media cancha."),
    ("Vóley", "Vóley de 6 jugadores por equipo, en cancha cubierta."),
    ("Beach vóley", "Vóley de playa, de a 2 por equipo, en cancha de arena."),
    ("Handball", "Handball de 7 jugadores por equipo."),
    ("Hockey", "Hockey sobre césped sintético."),
    ("Rugby", "Rugby de 15 o de 7 jugadores por equipo."),
    ("Natación", "Pileta para nado libre o entrenamiento."),
]


def normalizar(nombre: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().split())


def buscar_por_nombre(db: Session, nombre: str, excluir_id: int | None = None):
    clave = normalizar(nombre)
    for actividad in db.query(models.Actividad).all():
        if actividad.id != excluir_id and normalizar(actividad.nombre) == clave:
            return actividad
    return None


def cargar_catalogo(db: Session) -> int:
    nuevas = 0
    for nombre, descripcion in CATALOGO_DEPORTES:
        if buscar_por_nombre(db, nombre) is None:
            db.add(models.Actividad(nombre=nombre, descripcion=descripcion))
            db.flush()
            nuevas += 1
    db.commit()
    return nuevas