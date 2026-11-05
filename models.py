# Define cómo se guardan los datos en PostgreSQL
import enum
import math

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Enum, Float, CheckConstraint, Boolean, ForeignKey, DateTime, Numeric
from database import Base
from datetime import datetime, timezone


class TipoUsuario(str, enum.Enum):
    CLIENTE = "CLIENTE"
    PROPIETARIO = "PROPIETARIO"
    SUPERADMIN = "SUPERADMIN"


class TipoEspacio(str, enum.Enum):
    CANCHA = "CANCHA"
    SALON = "SALON"

class EstadoReserva(str, enum.Enum):
    EN_PROCESO = "EN_PROCESO"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"

class EstadoPago(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    REEMBOLSADO = "REEMBOLSADO"

class MedioPago(str, enum.Enum):
    TRANSFERENCIA = "TRANSFERENCIA"
    MP = "MP"
    TARJETA = "TARJETA"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    puntos = Column(Integer, default=0)

    tipo_usuario = Column(
        Enum(TipoUsuario),
        nullable=False,
        default=TipoUsuario.CLIENTE
    )

    espacios = relationship(
        "EspacioDeportivo",
        back_populates="propietario"
    )

    reservas = relationship(
        "Reserva",
        back_populates="usuario"
    )

    # Comprueba si el usuario tiene el rol de propietario
    def es_propietario(self) -> bool:
        return self.tipo_usuario == TipoUsuario.PROPIETARIO

    def sumar_puntos(self, cantidad: int):
        if cantidad <= 0:
            raise ValueError("La cantidad de puntos debe ser positiva")

        self.puntos = (self.puntos or 0) + cantidad

    def canjear_puntos(self, cantidad: int):
        if cantidad <= 0:
            raise ValueError("La cantidad de puntos debe ser positiva")

        if (self.puntos or 0) < cantidad:
            raise ValueError("El usuario no tiene puntos suficientes")

        self.puntos -= cantidad

    

class Actividad(Base):
    __tablename__ = "actividades"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(String(500))
    espacios = relationship(
        "EspacioDeportivo",
        back_populates="actividad"
    )

class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id = Column(Integer, primary_key=True, index=True)
    direccion = Column(String(200), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
        # Valida que las coordenadas estén dentro de los rangos permitidos
    __table_args__ = (
        CheckConstraint(
            "latitud BETWEEN -90 AND 90",
            name="latitud_valida"
        ),
        CheckConstraint(
            "longitud BETWEEN -180 AND 180",
            name="longitud_valida"
        ),
    )
    espacios = relationship(
        "EspacioDeportivo",
        back_populates="ubicacion"
    )
        # Calcula la distancia en kilómetros entre dos ubicaciones
    def distancia_km(self, latitud: float, longitud: float) -> float:
        r = 6371  # Radio aproximado de la Tierra en kilómetros

        lat1 = math.radians(self.latitud)
        lat2 = math.radians(latitud)

        dlat = lat2 - lat1
        dlon = math.radians(longitud - self.longitud)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2)
            * math.sin(dlon / 2) ** 2
        )

        return 2 * r * math.asin(math.sqrt(a))

class EspacioDeportivo(Base):
    __tablename__ = "espacios_deportivos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(Enum(TipoEspacio), nullable=False)
    activa = Column(Boolean, nullable=False, default=True)

    propietario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False
    )
    actividad_id = Column(
        Integer,
        ForeignKey("actividades.id"),
        nullable=False
    )

    ubicacion_id = Column(
        Integer,
        ForeignKey("ubicaciones.id"),
        nullable=False
    )

    propietario = relationship(
        "Usuario",
        back_populates="espacios"
    )
    actividad = relationship(
        "Actividad",
        back_populates="espacios"
    )
    ubicacion = relationship(
        "Ubicacion",
        back_populates="espacios"
    )
    turnos = relationship(
        "Turno",
        back_populates="espacio_deportivo"
    )

class Turno(Base):
    __tablename__ = "turnos"

    id = Column(Integer, primary_key=True, index=True)
    fecha_hora_inicio = Column(DateTime, nullable=False)
    fecha_hora_fin = Column(DateTime, nullable=False)
    precio = Column(Numeric(10, 2), nullable=False)
    cupo_maximo = Column(Integer, nullable=False, default=1)
    activo = Column(Boolean, nullable=False, default=True)
    espacio_deportivo_id = Column(
        Integer,
        ForeignKey("espacios_deportivos.id"),
        nullable=False
    )

    espacio_deportivo = relationship(
        "EspacioDeportivo",
        back_populates="turnos"
    )

    reservas = relationship(
        "Reserva",
        back_populates="turno"
    )

    __table_args__ = (
        CheckConstraint(
            "precio >= 0",
            name="precio_turno_valido"
        ),
        CheckConstraint(
            "cupo_maximo >= 1",
            name="cupo_turno_valido"
        ),
        CheckConstraint(
            "fecha_hora_fin > fecha_hora_inicio",
            name="horario_turno_valido"
        ),
    )
    def cupos_disponibles(self) -> int:
        reservas_activas = sum(
            1 for reserva in self.reservas
            if reserva.estado in (
                EstadoReserva.EN_PROCESO,
                EstadoReserva.CONFIRMADA
            )
        )

        return max(0, self.cupo_maximo - reservas_activas)
    
    def esta_disponible(self) -> bool:
        return (
            self.activo
            and self.espacio_deportivo.activa
            and self.fecha_hora_inicio > datetime.now(timezone.utc).replace(tzinfo=None)
            and self.cupos_disponibles() > 0
        )

    def usuario_ya_reservo(self, usuario_id: int) -> bool:
        return any(
            reserva.usuario_id == usuario_id
            and reserva.estado in (
                EstadoReserva.EN_PROCESO,
                EstadoReserva.CONFIRMADA
            )
            for reserva in self.reservas
        )

    def reservar(self, usuario_id: int):
        if not self.esta_disponible():
            raise ValueError("El turno no está disponible")

        if self.usuario_ya_reservo(usuario_id):
            raise ValueError("El usuario ya reservó este turno")

class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True, index=True)

    estado = Column(
        Enum(EstadoReserva),
        nullable=False,
        default=EstadoReserva.EN_PROCESO
    )
    fecha_creacion = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    precio = Column(Numeric(10, 2), nullable=False)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False
    )
    turno_id = Column(
        Integer,
        ForeignKey("turnos.id"),
        nullable=False
    )
    usuario = relationship(
        "Usuario",
        back_populates="reservas"
    )
    turno = relationship(
        "Turno",
        back_populates="reservas"
    )
    pagos = relationship(
        "Pago",
        back_populates="reserva"
    )
    def confirmar(self):
        if self.estado != EstadoReserva.EN_PROCESO:
            raise ValueError("Solo se pueden confirmar reservas en proceso")

        self.estado = EstadoReserva.CONFIRMADA

    def cancelar(self):
        if self.estado not in (
            EstadoReserva.EN_PROCESO,
            EstadoReserva.CONFIRMADA
        ):
            raise ValueError("Esta reserva no se puede cancelar")

        self.estado = EstadoReserva.CANCELADA

    def finalizar(self):
        if self.estado != EstadoReserva.CONFIRMADA:
            raise ValueError("Solo se pueden finalizar reservas confirmadas")

        self.estado = EstadoReserva.FINALIZADA

class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)

    monto = Column(Numeric(10, 2), nullable=False)

    medio_pago = Column(
        Enum(MedioPago),
        nullable=False
    )

    estado_pago = Column(
        Enum(EstadoPago),
        nullable=False,
        default=EstadoPago.PENDIENTE
    )

    reserva_id = Column(
        Integer,
        ForeignKey("reservas.id"),
        nullable=False
    )

    reserva = relationship(
        "Reserva",
        back_populates="pagos"
    )
    
    __table_args__ = (
        CheckConstraint(
            "monto > 0",
            name="monto_pago_valido"
        ),
    )
        
    fecha_pago = Column(
        DateTime(timezone=True),
        nullable=True
    )

    referencia_externa = Column(
        String(150),
        nullable=True
    )