# Define cómo se guardan los datos en PostgreSQL
import enum
import math
from decimal import Decimal

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Enum, Float, CheckConstraint, Boolean, ForeignKey, DateTime, Numeric
from database import Base
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


PUNTOS_POR_RESERVA = 10  # puntos que gana el cliente al finalizar una reserva
HORAS_LIMITE_REEMBOLSO = 48  # se reembolsa solo si se cancela con esta anticipación
PORCENTAJE_SENA = Decimal("0.20")  # la app cobra el 20%; el resto se paga en el lugar
MINUTOS_PARA_PAGAR = 5  # si no se paga la seña en este tiempo, la reserva vence
PORCENTAJE_COMISION = Decimal("0.05")  # la app se queda con el 5% del total de la reserva
PUNTOS_PARA_DESCUENTO = 100  # puntos que se canjean por un descuento
PORCENTAJE_DESCUENTO_PUNTOS = Decimal("0.10")  # descuento al canjear puntos
HORAS_ULTIMA_HORA = 2  # si el turno empieza dentro de estas horas, es "de última hora"
PORCENTAJE_DESCUENTO_ULTIMA_HORA = Decimal("0.15")  # descuento automático de última hora
ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")  # los turnos se guardan en UTC


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
    cuenta_cobro = Column(String(100), nullable=True)  # CBU o alias donde el propietario recibe las liquidaciones

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

    notificaciones = relationship(
        "Notificacion",
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

    def reservar(self, usuario_id: int, precio=None, puntos_usados: int = 0) -> "Reserva":
        if not self.esta_disponible():
            raise ValueError("El turno no está disponible")

        if self.usuario_ya_reservo(usuario_id):
            raise ValueError("El usuario ya reservó este turno")

        reserva = Reserva(
            usuario_id=usuario_id,
            estado=EstadoReserva.EN_PROCESO,
            # se congela el precio al momento de reservar; si no viene uno
            # calculado (con descuentos o recargos), se usa el del turno
            precio=precio if precio is not None else self.precio,
            puntos_usados=puntos_usados,
        )
        self.reservas.append(reserva)
        return reserva


# =====================================================================
# PATRÓN DECORATOR — precio de un turno
#
# El precio se arma "envolviendo" el precio base con decoradores.
# Cada decorador agrega una regla (descuento, recargo) sin tocar las demás,
# y se pueden apilar en cualquier orden:
#
#   precio = DescuentoPorPuntos(DescuentoUltimaHora(PrecioBase(turno)))
#   precio.calcular()  -> total final
#   precio.detalle()   -> ["Precio del turno: $15000", "Descuento ...", ...]
# =====================================================================

class Precio:
    def calcular(self) -> Decimal:
        raise NotImplementedError

    def detalle(self) -> list[str]:
        raise NotImplementedError


class PrecioBase(Precio):
    def __init__(self, turno: "Turno"):
        self.turno = turno

    def calcular(self) -> Decimal:
        return Decimal(self.turno.precio)

    def detalle(self) -> list[str]:
        return [f"Precio del turno: ${self.calcular():.2f}"]


class DecoradorPrecio(Precio):
    def __init__(self, precio: Precio):
        self.precio = precio

    def calcular(self) -> Decimal:
        return self.precio.calcular()

    def detalle(self) -> list[str]:
        return self.precio.detalle()


class DescuentoPorPuntos(DecoradorPrecio):
    # Canjeando puntos, el cliente tiene un descuento (RQ19)
    def calcular(self) -> Decimal:
        base = self.precio.calcular()
        return (base * (1 - PORCENTAJE_DESCUENTO_PUNTOS)).quantize(Decimal("0.01"))

    def detalle(self) -> list[str]:
        ahorro = self.precio.calcular() - self.calcular()
        return self.precio.detalle() + [
            f"Descuento por {PUNTOS_PARA_DESCUENTO} puntos ({PORCENTAJE_DESCUENTO_PUNTOS:.0%}): -${ahorro:.2f}"
        ]


class DescuentoUltimaHora(DecoradorPrecio):
    # Descuento automático si el turno empieza muy pronto:
    # mejor llenar el turno con descuento que dejarlo vacío
    def calcular(self) -> Decimal:
        base = self.precio.calcular()
        return (base * (1 - PORCENTAJE_DESCUENTO_ULTIMA_HORA)).quantize(Decimal("0.01"))

    def detalle(self) -> list[str]:
        ahorro = self.precio.calcular() - self.calcular()
        return self.precio.detalle() + [
            f"Descuento de última hora ({PORCENTAJE_DESCUENTO_ULTIMA_HORA:.0%}): -${ahorro:.2f}"
        ]


def armar_precio(turno: "Turno", usar_puntos: bool = False) -> Precio:
    # Arma el precio aplicando solo los decoradores que corresponden
    precio = PrecioBase(turno)

    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    if turno.fecha_hora_inicio - ahora <= timedelta(hours=HORAS_ULTIMA_HORA):
        precio = DescuentoUltimaHora(precio)  # se aplica solo, sin que el cliente haga nada

    if usar_puntos:
        precio = DescuentoPorPuntos(precio)

    return precio


# =====================================================================
# PATRÓN OBSERVER — cambios de estado de una reserva
#
# La reserva (sujeto) avisa cada vez que cambia de estado, sin saber
# quién la escucha. Cada observador decide qué hacer con el aviso.
# Para sumar un comportamiento nuevo (ej: mandar un mail) se agrega
# un observador, sin tocar la clase Reserva.
#
# Eventos: "confirmada", "cancelada", "vencida", "finalizada"
# =====================================================================

class ObservadorReserva:
    # Interfaz que implementan todos los observadores
    def actualizar(self, reserva: "Reserva", evento: str):
        raise NotImplementedError


class SumarPuntosAlFinalizar(ObservadorReserva):
    # Cuando se juega el turno, el cliente suma puntos
    def actualizar(self, reserva, evento):
        if evento == "finalizada":
            reserva.usuario.sumar_puntos(PUNTOS_POR_RESERVA)


class DevolverPuntosCanjeados(ObservadorReserva):
    # Si la reserva vence o se cancela con reembolso, se devuelven los puntos canjeados
    def actualizar(self, reserva, evento):
        if reserva.puntos_usados <= 0:
            return
        if evento == "vencida" or (evento == "cancelada" and reserva.fue_reembolsada()):
            reserva.usuario.sumar_puntos(reserva.puntos_usados)
            reserva.puntos_usados = 0


class NotificarCambios(ObservadorReserva):
    # Deja una notificación al cliente y al propietario de la cancha
    def actualizar(self, reserva, evento):
        cancha = reserva.turno.espacio_deportivo
        cuando = (
            reserva.turno.fecha_hora_inicio
            .replace(tzinfo=timezone.utc)
            .astimezone(ZONA_HORARIA)
            .strftime("%d/%m a las %H:%M")
        )
        cliente = reserva.usuario
        propietario = cancha.propietario

        mensajes = {
            "confirmada": [
                (cliente, f"Tu reserva en {cancha.nombre} el {cuando} está confirmada. "
                          f"Pagás ${reserva.precio - reserva.monto_sena():.2f} en la cancha."),
                (propietario, f"{cliente.nombre} reservó {cancha.nombre} para el {cuando}."),
            ],
            "cancelada": [
                (cliente, f"Cancelaste tu reserva en {cancha.nombre} del {cuando}. "
                          + ("Te devolvimos la seña." if reserva.fue_reembolsada()
                             else "La seña no se devuelve.")),
                (propietario, f"{cliente.nombre} canceló su reserva en {cancha.nombre} del {cuando}."),
            ],
            "vencida": [
                (cliente, f"Tu reserva en {cancha.nombre} del {cuando} venció porque no se pagó la seña a tiempo."),
            ],
            "finalizada": [
                (cliente, f"¡Sumaste {PUNTOS_POR_RESERVA} puntos por jugar en {cancha.nombre}!"),
            ],
        }

        for destinatario, texto in mensajes.get(evento, []):
            destinatario.notificaciones.append(Notificacion(mensaje=texto))


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
    puntos_usados = Column(Integer, nullable=False, default=0)  # puntos canjeados por descuento
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

    # Observadores que se enteran de cada cambio de estado (patrón Observer).
    # Es una lista de la clase: la comparten todas las reservas.
    observadores = [
        SumarPuntosAlFinalizar(),
        DevolverPuntosCanjeados(),
        NotificarCambios(),
    ]

    def notificar(self, evento: str):
        for observador in self.observadores:
            observador.actualizar(self, evento)

    def monto_sena(self) -> Decimal:
        return (self.precio * PORCENTAJE_SENA).quantize(Decimal("0.01"))

    def fue_reembolsada(self) -> bool:
        return any(pago.estado_pago == EstadoPago.REEMBOLSADO for pago in self.pagos)

    def confirmar(self):
        if self.estado != EstadoReserva.EN_PROCESO:
            raise ValueError("Solo se pueden confirmar reservas en proceso")

        self.estado = EstadoReserva.CONFIRMADA
        self.notificar("confirmada")

    def vencer(self):
        # No se pagó la seña a tiempo: se libera el turno
        if self.estado != EstadoReserva.EN_PROCESO:
            return

        self.estado = EstadoReserva.CANCELADA
        self.notificar("vencida")

    def cancelar(self):
        if self.estado not in (
            EstadoReserva.EN_PROCESO,
            EstadoReserva.CONFIRMADA
        ):
            raise ValueError("Esta reserva no se puede cancelar")

        self.estado = EstadoReserva.CANCELADA

        # Si ya había pagado, intentamos devolverle la plata.
        # reembolsar() decide si corresponde (48 hs antes del turno);
        # si no corresponde, la reserva se cancela igual y el pago queda aprobado.
        for pago in self.pagos:
            if pago.esta_aprobado():
                try:
                    pago.reembolsar()
                except ValueError:
                    pass

        self.notificar("cancelada")

    def finalizar(self):
        if self.estado != EstadoReserva.CONFIRMADA:
            raise ValueError("Solo se pueden finalizar reservas confirmadas")

        self.estado = EstadoReserva.FINALIZADA
        self.notificar("finalizada")  # SumarPuntosAlFinalizar se encarga de los puntos

    def registrar_pago(self, medio_pago, referencia_externa=None) -> "Pago":
        if self.estado == EstadoReserva.CONFIRMADA:
            raise ValueError("Esta reserva ya está pagada")

        if self.estado != EstadoReserva.EN_PROCESO:
            raise ValueError(
                "Solo se pueden pagar reservas en proceso "
                f"(si pasaron más de {MINUTOS_PARA_PAGAR} minutos sin pagar, la reserva venció)"
            )

        # Por la app solo se paga la seña; el resto se abona en el lugar.
        # De la seña, la app se queda con la comisión y el resto es del propietario.
        sena = self.monto_sena()
        comision = (self.precio * PORCENTAJE_COMISION).quantize(Decimal("0.01"))

        pago = Pago(
            monto=sena,
            comision=comision,
            medio_pago=medio_pago,
            estado_pago=EstadoPago.PENDIENTE,
            referencia_externa=referencia_externa,
        )
        self.pagos.append(pago)

        # Pago simulado: se aprueba en el momento, como si lo confirmara la pasarela
        pago.aprobar()
        return pago

class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)

    monto = Column(Numeric(10, 2), nullable=False)
    comision = Column(Numeric(10, 2), nullable=False, default=0)  # parte del monto que se queda la app

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

    def aprobar(self):
        if self.estado_pago != EstadoPago.PENDIENTE:
            raise ValueError("Solo se pueden aprobar pagos pendientes")

        self.estado_pago = EstadoPago.APROBADO
        self.fecha_pago = datetime.now(timezone.utc)
        self.reserva.confirmar()  # al aprobar el pago, la reserva queda confirmada

    def reembolsar(self):
        if self.estado_pago != EstadoPago.APROBADO:
            raise ValueError("Solo se pueden reembolsar pagos aprobados")

        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        inicio_turno = self.reserva.turno.fecha_hora_inicio

        if inicio_turno - ahora < timedelta(hours=HORAS_LIMITE_REEMBOLSO):
            raise ValueError(
                f"Solo se puede reembolsar hasta {HORAS_LIMITE_REEMBOLSO} horas antes del turno"
            )

        self.estado_pago = EstadoPago.REEMBOLSADO

    def esta_aprobado(self) -> bool:
        return self.estado_pago == EstadoPago.APROBADO


class Liquidacion(Base):
    # Transferencia que la app le hace al propietario con lo que cobró por sus canchas
    __tablename__ = "liquidaciones"

    id = Column(Integer, primary_key=True, index=True)

    propietario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False
    )

    monto = Column(Numeric(10, 2), nullable=False)

    alias_destino = Column(String(100), nullable=False)  # a dónde se transfirió

    fecha = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    referencia_externa = Column(String(150), nullable=True)  # ej: número de transferencia

    propietario = relationship("Usuario")

    __table_args__ = (
        CheckConstraint(
            "monto > 0",
            name="monto_liquidacion_valido"
        ),
    )


class Notificacion(Base):
    # Mensajes que generan los observadores de las reservas
    __tablename__ = "notificaciones"

    id = Column(Integer, primary_key=True, index=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False
    )

    mensaje = Column(String(300), nullable=False)

    leida = Column(Boolean, nullable=False, default=False)

    fecha = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    usuario = relationship(
        "Usuario",
        back_populates="notificaciones"
    )