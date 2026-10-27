# models describe cómo guardamos los datos en PostgreSQL
import enum
import hashlib
import hmac
import math
import os
from datetime import datetime, date, timedelta

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


PUNTOS_POR_RESERVA = 10  # puntos que gana el usuario al finalizar una reserva


# ---------- Enumeraciones ----------

class RolUsuario(enum.Enum):
    CLIENTE = "CLIENTE"
    PROPIETARIO = "PROPIETARIO"
    SUPER_ADMIN = "SUPER_ADMIN"


class TipoEspacio(enum.Enum):
    CANCHA = "CANCHA"
    SALON = "SALON"


class EstadoReserva(enum.Enum):
    EN_PROCESO = "EN_PROCESO"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"


class EstadoPago(enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    REEMBOLSADO = "REEMBOLSADO"


class MedioPago(enum.Enum):
    TRANSFERENCIA = "TRANSFERENCIA"
    MP = "MP"
    TARJETA = "TARJETA"


# ---------- Clases ----------

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    puntos = Column(Integer, nullable=False, default=0)
    rol = Column(Enum(RolUsuario), nullable=False, default=RolUsuario.CLIENTE)

    __table_args__ = (
        CheckConstraint("puntos >= 0", name="puntos_no_negativos"),
    )

    espacios = relationship("EspacioDeportivo", back_populates="propietario")
    reservas = relationship("Reserva", back_populates="usuario")

    def set_password(self, password: str) -> None:
        # guardamos "salt$hash" para no tener nunca la contraseña en texto plano
        salt = os.urandom(16)
        hash_ = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        self.password_hash = f"{salt.hex()}${hash_.hex()}"

    def verificar_password(self, password: str) -> bool:
        salt_hex, hash_hex = self.password_hash.split("$")
        hash_ = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 100_000
        )
        return hmac.compare_digest(hash_.hex(), hash_hex)

    def sumar_puntos(self, cantidad: int) -> None:
        if cantidad <= 0:
            raise ValueError("La cantidad de puntos debe ser positiva")
        self.puntos = (self.puntos or 0) + cantidad

    def canjear_puntos(self, cantidad: int) -> None:
        if cantidad <= 0:
            raise ValueError("La cantidad de puntos debe ser positiva")
        if cantidad > self.puntos:
            raise ValueError("Puntos insuficientes")
        self.puntos -= cantidad

    def es_propietario(self) -> bool:
        return self.rol == RolUsuario.PROPIETARIO


class Actividad(Base):
    __tablename__ = "actividades"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(String(500))

    espacios = relationship("EspacioDeportivo", back_populates="actividad")



class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id = Column(Integer, primary_key=True, index=True)
    direccion = Column(String(200), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint("latitud BETWEEN -90 AND 90", name="latitud_valida"),
        CheckConstraint("longitud BETWEEN -180 AND 180", name="longitud_valida"),
    )

    espacios = relationship("EspacioDeportivo", back_populates="ubicacion")

    def distancia_km(self, latitud: float, longitud: float) -> float:
        # distancia en línea recta (fórmula de haversine)
        r = 6371  # radio de la Tierra en km
        lat1, lat2 = math.radians(self.latitud), math.radians(latitud)
        dlat = lat2 - lat1
        dlon = math.radians(longitud - self.longitud)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    
class EspacioDeportivo(Base):
    __tablename__ = "espacios_deportivos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    ubicacion = Column(String(200), nullable=False)
    tipo = Column(Enum(TipoEspacio), nullable=False)
    activa = Column(Boolean, nullable=False, default=True)
    propietario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    actividad_id = Column(Integer, ForeignKey("actividades.id"), nullable=False)

    propietario = relationship("Usuario", back_populates="espacios")
    actividad = relationship("Actividad", back_populates="espacios")
    turnos = relationship("Turno", back_populates="espacio_deportivo")

    def activar(self) -> None:
        self.activa = True

    def desactivar(self) -> None:
        # baja lógica: no borramos para no perder el historial de turnos y reservas
        self.activa = False
        for turno in self.turnos:
            if turno.fecha_hora_inicio > datetime.now():
                turno.activo = False

    def crear_turno(self, inicio: datetime, fin: datetime, precio, cupo: int) -> "Turno":
        if not self.activa:
            raise ValueError("El espacio está desactivado")
        nuevo = Turno(
            fecha_hora_inicio=inicio,
            fecha_hora_fin=fin,
            precio=precio,
            cupo_maximo=cupo,
            activo=True,
        )
        for t in self.turnos:
            if t.activo and t.se_superpone(nuevo):
                raise ValueError("El turno se superpone con otro del mismo espacio")
        self.turnos.append(nuevo)
        return nuevo

    def turnos_disponibles(self, fecha: date) -> list["Turno"]:
        return [
            t for t in self.turnos
            if t.fecha_hora_inicio.date() == fecha and t.esta_disponible()
        ]


class Turno(Base):
    __tablename__ = "turnos"

    id = Column(Integer, primary_key=True, index=True)
    espacio_deportivo_id = Column(Integer, ForeignKey("espacios_deportivos.id"), nullable=False)
    fecha_hora_inicio = Column(DateTime, nullable=False)
    fecha_hora_fin = Column(DateTime, nullable=False)
    precio = Column(Numeric(10, 2), nullable=False)
    cupo_maximo = Column(Integer, nullable=False)
    activo = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("fecha_hora_fin > fecha_hora_inicio", name="turno_horario_valido"),
        CheckConstraint("cupo_maximo > 0", name="cupo_positivo"),
        CheckConstraint("precio >= 0", name="turno_precio_no_negativo"),
    )

    espacio_deportivo = relationship("EspacioDeportivo", back_populates="turnos")
    reservas = relationship("Reserva", back_populates="turno")

    def cupos_disponibles(self) -> int:
        ocupados = sum(
            1 for r in self.reservas
            if r.estado in (EstadoReserva.EN_PROCESO, EstadoReserva.CONFIRMADA)
        )
        return self.cupo_maximo - ocupados

    def esta_disponible(self) -> bool:
        return (
            self.activo
            and self.fecha_hora_inicio > datetime.now()
            and self.cupos_disponibles() > 0
        )

    def reservar(self, usuario: Usuario) -> "Reserva":
        if not self.esta_disponible():
            raise ValueError("El turno no está disponible")
        for r in self.reservas:
            if r.usuario_id == usuario.id and r.estado in (
                EstadoReserva.EN_PROCESO, EstadoReserva.CONFIRMADA
            ):
                raise ValueError("El usuario ya tiene una reserva en este turno")
        reserva = Reserva(
            usuario=usuario,
            estado=EstadoReserva.EN_PROCESO,
            precio=self.precio,  # se congela el precio al momento de reservar
        )
        self.reservas.append(reserva)
        return reserva


class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    estado = Column(Enum(EstadoReserva), nullable=False, default=EstadoReserva.EN_PROCESO)
    fecha_creacion = Column(DateTime, nullable=False, server_default=func.now())
    precio = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("precio >= 0", name="reserva_precio_no_negativo"),
    )

    turno = relationship("Turno", back_populates="reservas")
    usuario = relationship("Usuario", back_populates="reservas")
    pagos = relationship("Pago", back_populates="reserva")

    def confirmar(self) -> None:
        if self.estado != EstadoReserva.EN_PROCESO:
            raise ValueError("Solo se puede confirmar una reserva en proceso")
        self.estado = EstadoReserva.CONFIRMADA

    def cancelar(self) -> None:
        if self.estado not in (EstadoReserva.EN_PROCESO, EstadoReserva.CONFIRMADA):
            raise ValueError("Esta reserva ya no se puede cancelar")
        self.estado = EstadoReserva.CANCELADA
        for pago in self.pagos:
            if pago.esta_aprobado():
                pago.reembolsar()

    def finalizar(self) -> None:
        if self.estado != EstadoReserva.CONFIRMADA:
            raise ValueError("Solo se puede finalizar una reserva confirmada")
        self.estado = EstadoReserva.FINALIZADA
        self.usuario.sumar_puntos(PUNTOS_POR_RESERVA)


class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    reserva_id = Column(Integer, ForeignKey("reservas.id"), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    medio_pago = Column(Enum(MedioPago), nullable=False)
    estado_pago = Column(Enum(EstadoPago), nullable=False, default=EstadoPago.PENDIENTE)
    fecha_pago = Column(DateTime, nullable=False, server_default=func.now())
    referencia_externa = Column(String(200))

    __table_args__ = (
        CheckConstraint("monto >= 0", name="monto_no_negativo"),
    )

    reserva = relationship("Reserva", back_populates="pagos")

    def aprobar(self) -> None:
        if self.estado_pago != EstadoPago.PENDIENTE:
            raise ValueError("Solo se puede aprobar un pago pendiente")
        self.estado_pago = EstadoPago.APROBADO
        self.reserva.confirmar()

    def rechazar(self) -> None:
        if self.estado_pago != EstadoPago.PENDIENTE:
            raise ValueError("Solo se puede rechazar un pago pendiente")
        self.estado_pago = EstadoPago.RECHAZADO

    def reembolsar(self) -> None:
        if self.estado_pago != EstadoPago.APROBADO:
            raise ValueError("Solo se puede reembolsar un pago aprobado")
        self.estado_pago = EstadoPago.REEMBOLSADO

    def esta_aprobado(self) -> bool:
        return self.estado_pago == EstadoPago.APROBADO


