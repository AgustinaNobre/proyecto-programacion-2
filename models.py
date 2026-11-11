# Define cómo se guardan los datos en PostgreSQL
import enum
import math
from abc import ABC, abstractmethod
from decimal import Decimal

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Enum, Float, CheckConstraint, Boolean, ForeignKey, DateTime, Numeric, UniqueConstraint
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
ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")  # para mostrar los horarios en las notificaciones



class TipoUsuario(str, enum.Enum):
    """Define los roles disponibles para los usuarios."""
    CLIENTE = "CLIENTE"
    PROPIETARIO = "PROPIETARIO"
    SUPERADMIN = "SUPERADMIN"


class TipoEspacio(str, enum.Enum):
    """Define los tipos de espacios deportivos."""
    CANCHA = "CANCHA"
    SALON = "SALON"


class EstadoReserva(str, enum.Enum):
    """Define los posibles estados de una reserva."""
    EN_PROCESO = "EN_PROCESO"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"


class EstadoPago(str, enum.Enum):
    """Define los posibles estados de un pago."""
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    REEMBOLSADO = "REEMBOLSADO"


class MedioPago(str, enum.Enum):
    """Define los medios de pago admitidos por la plataforma."""
    TRANSFERENCIA = "TRANSFERENCIA"
    MP = "MP"
    TARJETA = "TARJETA"



class Usuario(Base):
    """
    Representa a los usuarios registrados en la plataforma.

    Los usuarios pueden tener los roles CLIENTE, PROPIETARIO o
    SUPERADMIN. Según su rol, pueden reservar turnos, publicar
    espacios deportivos o administrar la aplicación.

    También permite gestionar los puntos que los clientes
    acumulan al finalizar sus reservas.
    """

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
        """
        Comprueba si el usuario tiene el rol PROPIETARIO.

        Returns:
        bool: True si es propietario; False en caso contrario.
        """
        return self.tipo_usuario == TipoUsuario.PROPIETARIO


    def sumar_puntos(self, cantidad: int):
        """
        Agrega puntos al usuario.

        Args:
        cantidad (int): Cantidad de puntos que se desea sumar.

        Raises:
        ValueError: Si la cantidad es menor o igual a cero.
        """
        if cantidad <= 0:
            raise ValueError("La cantidad de puntos debe ser positiva")

        self.puntos = (self.puntos or 0) + cantidad


    def canjear_puntos(self, cantidad: int):
        """
        Descuenta puntos del saldo acumulado por el usuario.

        Args:
        cantidad (int): Cantidad de puntos que desea canjear.

        Raises:
        ValueError: Si la cantidad no es positiva o si el usuario
                    no tiene puntos suficientes.
        """
        if cantidad <= 0:
            raise ValueError("La cantidad de puntos debe ser positiva")

        if (self.puntos or 0) < cantidad:
            raise ValueError("El usuario no tiene puntos suficientes")

        self.puntos -= cantidad




class Actividad(Base):

    """
    Representa una actividad deportiva disponible en la plataforma.

    Cada actividad tiene un nombre y una descripción, y puede
    estar asociada a varios espacios deportivos.

    Ejemplos: fútbol, pádel, básquet o entrenamiento funcional.
    """

    __tablename__ = "actividades"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(String(500))
    espacios = relationship(
        "EspacioDeportivo",
        back_populates="actividad"
    )

class Ubicacion(Base):

    """
    Representa la ubicación geográfica de un espacio deportivo.

    Almacena la dirección, latitud y longitud. Las coordenadas
    tienen restricciones de validez definidas en PostgreSQL.

    Permite calcular distancias aproximadas entre ubicaciones
    mediante la fórmula de Haversine.
    """

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

        """
        Calcula la distancia aproximada entre dos coordenadas.

        Utiliza la fórmula de Haversine y considera un radio
        terrestre aproximado de 6371 kilómetros.

        Args:
            latitud (float): Latitud del punto de destino.
            longitud (float): Longitud del punto de destino.

        Returns:
            float: Distancia aproximada en kilómetros.
        """

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

    """
    Representa una cancha o salón publicado en la plataforma.

    Cada espacio pertenece a un propietario y se relaciona
    con una actividad deportiva y una ubicación.

    Permite administrar turnos, consultar reseñas y comprobar
    si un usuario ya realizó una actividad en el espacio.
    """

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
    resenas = relationship(
        "Resena",
        back_populates="espacio_deportivo"
    )


    @property
    def cantidad_resenas(self) -> int:
        """
        Devuelve la cantidad total de reseñas del espacio deportivo.
        """
        return len(self.resenas)


    @property
    def promedio_puntaje(self) -> float | None:
        """
        Calcula el promedio de las calificaciones recibidas.

        Returns:
        float | None: Promedio redondeado a un decimal,
        o None si todavía no existen reseñas.
        """
        if not self.resenas:
            return None

        return round(
        sum(r.puntaje for r in self.resenas) / len(self.resenas),
        1
        )


    def jugo_aca(self, usuario_id: int) -> bool:
        """
        Comprueba si un usuario tiene una reserva finalizada
        en este espacio deportivo.

        Args:
        usuario_id (int): Identificador del usuario.

        Returns:
        bool: True si existe una reserva finalizada.
        """
        return any(
        reserva.usuario_id == usuario_id
        and reserva.estado == EstadoReserva.FINALIZADA
        for turno in self.turnos
        for reserva in turno.reservas
    )


class Turno(Base):

    """
    Representa un turno disponible para reservar un espacio deportivo.

    Cada turno tiene una fecha y hora de inicio y fin, un precio,
    un cupo máximo y un estado que indica si está activo.

    Se relaciona con un espacio deportivo y con las reservas
    realizadas por los usuarios.

    Contiene las reglas de negocio para consultar la disponibilidad,
    controlar los cupos y evitar reservas duplicadas.
    """

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

    @property
    def cupos_disponibles(self) -> int:
        """
        Calcula la cantidad de lugares disponibles en el turno.

        Se consideran ocupados los cupos de las reservas que
        están EN_PROCESO o CONFIRMADAS.

        Las reservas canceladas o finalizadas no se cuentan
        como ocupadas.

        Returns:
            int: Cantidad de cupos disponibles, nunca negativa.
        """
        reservas_activas = sum(
            1 for reserva in self.reservas
            if reserva.estado in (
                EstadoReserva.EN_PROCESO,
                EstadoReserva.CONFIRMADA
            )
        )

        return max(0, self.cupo_maximo - reservas_activas)

    def esta_disponible(self) -> bool:
        """
        Comprueba si el turno puede recibir nuevas reservas.

        Para estar disponible deben cumplirse estas condiciones:
        - El turno debe estar activo.
        - El espacio deportivo debe estar activo.
        - La fecha de inicio debe ser futura.
        - Debe quedar al menos un cupo disponible.

        Returns:
            bool: True si se cumplen todas las condiciones.
        """
        return (
            self.activo
            and self.espacio_deportivo.activa
            and self.fecha_hora_inicio > datetime.now(timezone.utc).replace(tzinfo=None)
            and self.cupos_disponibles > 0
        )

    def usuario_ya_reservo(self, usuario_id: int) -> bool:
        """
        Verifica si un usuario ya tiene una reserva activa
        para este turno.

        Se consideran activas las reservas EN_PROCESO
        y CONFIRMADAS.

        Args:
            usuario_id (int): Identificador del usuario.

        Returns:
            bool: True si el usuario ya reservó el turno.
        """
        return any(
            reserva.usuario_id == usuario_id
            and reserva.estado in (
                EstadoReserva.EN_PROCESO,
                EstadoReserva.CONFIRMADA
            )
            for reserva in self.reservas
        )

    def reservar(self, usuario_id: int, precio=None, puntos_usados: int = 0) -> "Reserva":
        """
        Crea una nueva reserva para el turno.

        Antes de crearla, comprueba que el turno esté disponible
        y que el usuario no tenga otra reserva activa.

        El precio queda registrado al momento de reservar,
        por lo que no cambia si después se modifica el turno.

        Args:
            usuario_id (int): Identificador del usuario.
            precio: Precio final, si se aplicaron descuentos.
                    Si no se indica, se utiliza el precio del turno.
            puntos_usados (int): Puntos canjeados por el usuario.

        Returns:
            Reserva: Nueva reserva con estado EN_PROCESO.

        Raises:
            ValueError: Si el turno no está disponible o si
                        el usuario ya tiene una reserva activa.
        """
        if not self.esta_disponible():
            raise ValueError("El turno no está disponible")

        if self.usuario_ya_reservo(usuario_id):
            raise ValueError("El usuario ya reservó este turno")

        reserva = Reserva(
            usuario_id=usuario_id,
            estado=EstadoReserva.EN_PROCESO,
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
    """
    Define la interfaz común para calcular precios.

    Permite que el precio base y sus decoradores utilicen
    los mismos métodos: calcular() y detalle().

    Es la clase componente del patrón Decorator.
    """
    def calcular(self) -> Decimal:
        raise NotImplementedError

    def detalle(self) -> list[str]:
        raise NotImplementedError


class PrecioBase(Precio):
    """
    Representa el precio original de un turno.

    Es el componente concreto del patrón Decorator.
    A partir de este precio pueden aplicarse distintos
    descuentos sin modificar la clase Turno.
    """
    def __init__(self, turno: "Turno"):
        self.turno = turno

    def calcular(self) -> Decimal:
        return Decimal(self.turno.precio)

    def detalle(self) -> list[str]:
        return [f"Precio del turno: ${self.calcular():.2f}"]


class DecoradorPrecio(Precio):
    """
    Clase base para los decoradores de precio.

    Recibe otro objeto de tipo Precio y delega en él
    los cálculos. Las clases hijas pueden modificar
    el resultado agregando descuentos.

    Permite combinar diferentes reglas de precios.
    """
    def __init__(self, precio: Precio):
        self.precio = precio

    def calcular(self) -> Decimal:
        return self.precio.calcular()

    def detalle(self) -> list[str]:
        return self.precio.detalle()


class DescuentoPorPuntos(DecoradorPrecio):
    """
    Aplica un descuento al precio cuando el usuario
    canjea sus puntos acumulados.

    Es un decorador concreto que reduce el precio
    según PORCENTAJE_DESCUENTO_PUNTOS.
    """
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
    """
    Aplica un descuento automático a los turnos
    que comienzan dentro del período de última hora.

    Es un decorador concreto que utiliza
    PORCENTAJE_DESCUENTO_ULTIMA_HORA.
    """
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
    """
    Construye el precio final de un turno utilizando Decorator.

    Parte del precio base y agrega los descuentos que
    correspondan según la anticipación y el uso de puntos.

    Args:
        turno (Turno): Turno cuyo precio se desea calcular.
        usar_puntos (bool): Indica si se aplica el descuento
                           por puntos acumulados.

    Returns:
        Precio: Objeto que permite calcular el precio final
                y consultar el detalle de los descuentos.
    """
    # Arma el precio aplicando solo los decoradores que corresponden
    precio = PrecioBase(turno)

    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    if turno.fecha_hora_inicio - ahora <= timedelta(hours=HORAS_ULTIMA_HORA):
        precio = DescuentoUltimaHora(precio)  # se aplica solo, sin que el cliente haga nada

    if usar_puntos:
        precio = DescuentoPorPuntos(precio)

    return precio


# =====================================================================
# PATRÓN OBSERVER — notificaciones de una reserva
#
# La reserva es el "sujeto": cuando cambia de estado avisa a sus observadores
# llamando a notificar(evento). Cada observador decide qué hacer con ese aviso.
# La reserva no sabe quién la escucha ni qué hace cada uno, así que para sumar
# otro aviso (por ejemplo, un mail) alcanza con agregar otro observador a la lista.
#
#   reserva.cancelar()  ->  reserva.notificar("cancelada")
#                              -> AvisoAlCliente.actualizar(...)
#                              -> AvisoAlPropietario.actualizar(...)
# =====================================================================

class ObservadorReserva(ABC):
    """
    Define la interfaz de los observadores de una reserva.

    Utiliza el patrón Observer para permitir que diferentes
    clases reaccionen cuando cambia el estado de una reserva.

    Cada observador debe implementar el método actualizar().
    """
    @abstractmethod
    def actualizar(self, reserva: "Reserva", evento: str):
        """
        Recibe una notificación cuando ocurre un evento.

        Args:
            reserva (Reserva): Reserva que generó el evento.
            evento (str): Tipo de evento ocurrido.
        """
        pass


class AvisoAlCliente(ObservadorReserva):
    """
    Observador encargado de generar notificaciones al cliente.

    Crea mensajes cuando una reserva es confirmada, cancelada,
    anulada, vencida o finalizada.

    Los mensajes se almacenan en las notificaciones del usuario.
    """
    def actualizar(self, reserva: "Reserva", evento: str):
        """
        Genera una notificación para el cliente según el evento.

        Args:
            reserva (Reserva): Reserva que cambió de estado.
            evento (str): Evento que determina el mensaje.
        """
        turno = reserva.describir_turno()

        if evento == "confirmada":
            sena = f"{reserva.monto_sena():,.0f}".replace(",", ".")
            mensaje = f"¡Reserva confirmada! {turno}. Pagaste la seña de ${sena}; el resto se abona en la cancha."
        elif evento == "vencida":
            mensaje = f"Tu reserva para {turno} venció porque no se pagó la seña a tiempo."
        elif evento == "cancelada" and reserva.fue_reembolsada():
            mensaje = f"Cancelaste tu reserva para {turno}. Te devolvimos la seña."
        elif evento == "cancelada":
            mensaje = f"Cancelaste tu reserva para {turno}."
        elif evento == "anulada" and reserva.fue_reembolsada():
            mensaje = f"Se dio de baja el turno de {turno}. Te devolvimos la seña."
        elif evento == "anulada":
            mensaje = f"Se dio de baja el turno de {turno}, así que tu reserva quedó cancelada."
        elif evento == "finalizada":
            mensaje = f"¡Gracias por jugar! Sumaste {PUNTOS_POR_RESERVA} puntos. Contanos qué te pareció {reserva.turno.espacio_deportivo.nombre}."
        else:
            return

        reserva.usuario.notificaciones.append(Notificacion(mensaje=mensaje))


class AvisoAlPropietario(ObservadorReserva):
    """
    Observador encargado de notificar al propietario.

    Genera mensajes cuando un cliente confirma o cancela
    una reserva de su espacio deportivo.

    Permite informar al propietario sin incorporar
    esa lógica directamente en los métodos de Reserva.
    """
    def actualizar(self, reserva: "Reserva", evento: str):
        """
        Genera una notificación para el propietario.

        Args:
            reserva (Reserva): Reserva que generó el evento.
            evento (str): Evento ocurrido.
        """
        turno = reserva.describir_turno()

        if evento == "confirmada":
            mensaje = f"Nueva reserva de {reserva.usuario.nombre}: {turno}."
        elif evento == "cancelada" and reserva.pagos:
            mensaje = f"{reserva.usuario.nombre} canceló su reserva: {turno}. El turno quedó libre."
        else:
            return

        propietario = reserva.turno.espacio_deportivo.propietario
        propietario.notificaciones.append(Notificacion(mensaje=mensaje))


class Reserva(Base):

    """
    Representa una reserva realizada por un usuario.

    Cada reserva pertenece a un turno y tiene un estado,
    un precio y una posible cantidad de puntos utilizados.

    Administra el ciclo de vida de las reservas:
    creación, confirmación, vencimiento, cancelación,
    anulación y finalización.

    También gestiona los pagos y utiliza el patrón Observer
    para notificar los cambios de estado.
    """
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

    observadores = [AvisoAlCliente(), AvisoAlPropietario()]

    def notificar(self, evento: str):
        """
        Notifica a todos los observadores registrados.

        Recorre la lista de observadores y ejecuta actualizar()
        para que cada uno reaccione al evento ocurrido.

        Args:
            evento (str): Evento relacionado con la reserva.
        """
        for observador in self.observadores:
            observador.actualizar(self, evento)

    def describir_turno(self) -> str:
        """
        Genera una descripción del turno reservado.

        Convierte el horario a la zona horaria de Buenos Aires
        e incluye el nombre del espacio deportivo.

        Returns:
            str: Descripción del espacio, fecha y horario.
        """
        inicio = self.turno.fecha_hora_inicio.replace(tzinfo=timezone.utc).astimezone(ZONA_HORARIA)
        return f"{self.turno.espacio_deportivo.nombre}, el {inicio:%d/%m} a las {inicio:%H:%M}"

    def monto_sena(self) -> Decimal:
        """
        Calcula la seña necesaria para confirmar una reserva.

        La seña corresponde al 20% del precio final
        de la reserva.

        Returns:
            Decimal: Importe de la seña con dos decimales.
        """
        return (self.precio * PORCENTAJE_SENA).quantize(Decimal("0.01"))

    def fue_reembolsada(self) -> bool:
        """
        Comprueba si existe un pago reembolsado.

        Returns:
            bool: True si algún pago fue reembolsado.
        """
        return any(pago.estado_pago == EstadoPago.REEMBOLSADO for pago in self.pagos)

    def confirmar(self):
        """
        Confirma una reserva que se encuentra EN_PROCESO.

        Cambia su estado a CONFIRMADA y notifica
        a los observadores registrados.

        Raises:
            ValueError: Si la reserva no está EN_PROCESO.
        """
        if self.estado != EstadoReserva.EN_PROCESO:
            raise ValueError("Solo se pueden confirmar reservas en proceso")

        self.estado = EstadoReserva.CONFIRMADA
        self.notificar("confirmada")

    def vencer(self):
        """
        Cancela una reserva pendiente cuando vence.

        Si la reserva está EN_PROCESO, cambia su estado
        a CANCELADA, devuelve los puntos utilizados
        y genera la notificación correspondiente.

        Si la reserva ya cambió de estado, no hace nada.
        """
        # No se pagó la seña a tiempo: se libera el turno
        if self.estado != EstadoReserva.EN_PROCESO:
            return

        self.estado = EstadoReserva.CANCELADA

        if self.puntos_usados > 0:
            self.usuario.sumar_puntos(self.puntos_usados)
            self.puntos_usados = 0

        self.notificar("vencida")

    def cancelar(self):
        """
        Cancela una reserva solicitada por el usuario.

        Permite cancelar reservas EN_PROCESO o CONFIRMADAS.

        Si existe un pago aprobado, intenta reembolsarlo.
        El reembolso depende de la anticipación respecto
        del inicio del turno.

        Si se realiza un reembolso, también devuelve
        los puntos utilizados, cuando corresponda.

        La reserva se cancela aunque no corresponda
        devolver la seña.

        Raises:
            ValueError: Si la reserva no puede cancelarse.
        """
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

        if self.puntos_usados > 0 and self.fue_reembolsada():
            self.usuario.sumar_puntos(self.puntos_usados)
            self.puntos_usados = 0

        self.notificar("cancelada")

    def anular(self):
        """
        Anula una reserva por la baja del turno.

        Cambia su estado a CANCELADA, marca los pagos
        aprobados como reembolsados y devuelve los
        puntos utilizados.

        A diferencia de cancelar(), no aplica el límite
        de 48 horas para el reembolso.

        Finalmente, notifica a los observadores.
        """        """
        Anula una reserva por la baja del turno.

        Cambia su estado a CANCELADA, marca los pagos
        aprobados como reembolsados y devuelve los
        puntos utilizados.

        A diferencia de cancelar(), no aplica el límite
        de 48 horas para el reembolso.

        Finalmente, notifica a los observadores.
        """
        # El propietario dio de baja el turno: se cancela y se devuelve la seña sin importar la anticipación
        if self.estado not in (EstadoReserva.EN_PROCESO, EstadoReserva.CONFIRMADA):
            return

        self.estado = EstadoReserva.CANCELADA

        for pago in self.pagos:
            if pago.esta_aprobado():
                pago.estado_pago = EstadoPago.REEMBOLSADO

        if self.puntos_usados > 0:
            self.usuario.sumar_puntos(self.puntos_usados)
            self.puntos_usados = 0

        self.notificar("anulada")

    def finalizar(self):
        """
        Finaliza una reserva previamente confirmada.

        Cambia su estado a FINALIZADA, acredita los
        puntos correspondientes al usuario y genera
        una notificación.

        Raises:
            ValueError: Si la reserva no está CONFIRMADA.
        """
        if self.estado != EstadoReserva.CONFIRMADA:
            raise ValueError("Solo se pueden finalizar reservas confirmadas")

        self.estado = EstadoReserva.FINALIZADA
        self.usuario.sumar_puntos(PUNTOS_POR_RESERVA)
        self.notificar("finalizada")

    def registrar_pago(self, medio_pago, referencia_externa=None) -> "Pago":
        """
        Registra el pago simulado de la seña de una reserva.

        Calcula el 20% del precio como seña y el 5%
        del precio total como comisión de la plataforma.

        Crea un pago pendiente y lo aprueba mediante
        el método aprobar() de la clase Pago.

        Args:
            medio_pago: Medio de pago seleccionado.
            referencia_externa: Identificador opcional del pago.

        Returns:
            Pago: Objeto que representa el pago registrado.

        Raises:
            ValueError: Si la reserva no está EN_PROCESO.
        """
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
    """
    Representa el pago de la seña de una reserva.

    Almacena el importe abonado, la comisión de la plataforma,
    el medio de pago, el estado y la fecha de pago.

    Permite aprobar pagos pendientes y realizar reembolsos
    cuando se cumplen las condiciones establecidas.

    Actualmente los pagos se simulan dentro de la aplicación.
    """
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
        """
        Aprueba un pago que se encuentra pendiente.

        Cambia el estado del pago a APROBADO, registra
        la fecha de pago y confirma la reserva asociada.

        Raises:
            ValueError: Si el pago no está PENDIENTE
                        o la reserva no puede confirmarse.
        """
        if self.estado_pago != EstadoPago.PENDIENTE:
            raise ValueError("Solo se pueden aprobar pagos pendientes")

        self.estado_pago = EstadoPago.APROBADO
        self.fecha_pago = datetime.now(timezone.utc)
        self.reserva.confirmar()  # al aprobar el pago, la reserva queda confirmada

    def reembolsar(self):
        """
        Reembolsa un pago previamente aprobado.

        Comprueba que el pago esté APROBADO y que falten
        al menos 48 horas para el inicio del turno.

        Si se cumplen ambas condiciones, cambia el estado
        del pago a REEMBOLSADO.

        Raises:
            ValueError: Si el pago no está aprobado o si
                        no se cumple el plazo de reembolso.
        """
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
        """
        Comprueba si el pago fue aprobado.

        Returns:
            bool: True si el estado es APROBADO;
                  False en caso contrario.
        """
        return self.estado_pago == EstadoPago.APROBADO


class Liquidacion(Base):
    """
    Representa una liquidación realizada por la plataforma
    a un propietario de espacios deportivos.

    Almacena el importe transferido, la cuenta de destino,
    la fecha y una referencia opcional de la transferencia.

    Permite registrar los pagos que la plataforma
    realiza a los propietarios.
    """
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


class Resena(Base):
    """
    Representa una reseña realizada por un usuario
    sobre un espacio deportivo.

    Cada reseña contiene un puntaje entre 1 y 5,
    un comentario opcional y una fecha de creación.

    La base de datos impide que un mismo usuario
    publique más de una reseña por espacio deportivo.
    """
    __tablename__ = "resenas"

    id = Column(Integer, primary_key=True, index=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False
    )

    espacio_deportivo_id = Column(
        Integer,
        ForeignKey("espacios_deportivos.id"),
        nullable=False
    )

    puntaje = Column(Integer, nullable=False)

    comentario = Column(String(500), nullable=True)

    fecha = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    usuario = relationship("Usuario")

    espacio_deportivo = relationship(
        "EspacioDeportivo",
        back_populates="resenas"
    )

    __table_args__ = (
        CheckConstraint(
            "puntaje BETWEEN 1 AND 5",
            name="puntaje_valido"
        ),
        UniqueConstraint(
            "usuario_id",
            "espacio_deportivo_id",
            name="una_resena_por_cancha"
        ),
    )


class Notificacion(Base):
    """
    Representa una notificación destinada a un usuario.

    Almacena el mensaje, la fecha de creación y un
    indicador que permite saber si fue leída.

    Las notificaciones se generan principalmente
    mediante el patrón Observer cuando ocurren
    eventos relacionados con las reservas.
    """
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