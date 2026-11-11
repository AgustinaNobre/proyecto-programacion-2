from datetime import datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, EmailStr, ConfigDict, Field, computed_field

from models import EstadoPago, EstadoReserva, MedioPago, PORCENTAJE_SENA

class UsuarioCrear(BaseModel):
    nombre: str
    email: EmailStr
    password: str

class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    puntos: int
    tipo_usuario: str

    model_config = {"from_attributes": True}

class ActividadCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)


class ActividadActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)

class ActividadRespuesta(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UbicacionCrear(BaseModel):
    direccion: str = Field(min_length=1, max_length=200)
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)


class UbicacionRespuesta(BaseModel):
    id: int
    direccion: str
    latitud: float
    longitud: float

    model_config = ConfigDict(from_attributes=True)


class EspacioDeportivoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str
    actividad_id: int
    ubicacion_id: int


class EspacioDeportivoRespuesta(BaseModel):
    id: int
    nombre: str
    tipo: str
    activa: bool
    propietario_id: int
    actividad_id: int
    ubicacion_id: int
    ubicacion: UbicacionRespuesta
    promedio_puntaje: float | None = None
    cantidad_resenas: int = 0

    model_config = ConfigDict(from_attributes=True)

# Datos necesarios para crear un turno
class TurnoCrear(BaseModel):
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
    precio: Decimal = Field(ge=0)
    cupo_maximo: int = Field(ge=1)
    espacio_deportivo_id: int


# Datos que devuelve la API al consultar un turno
class TurnoRespuesta(BaseModel):
    id: int
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
    precio: Decimal
    cupo_maximo: int
    cupos_disponibles: int
    activo: bool
    espacio_deportivo_id: int

    model_config = ConfigDict(from_attributes=True)


# Datos permitidos para modificar un turno
class TurnoActualizar(BaseModel):
    fecha_hora_inicio: datetime | None = None
    fecha_hora_fin: datetime | None = None
    precio: Decimal | None = Field(default=None, ge=0)
    cupo_maximo: int | None = Field(default=None, ge=1)
    activo: bool | None = None

'''id: identificador del espacio, generado por PostgreSQL.
nombre: nombre de la cancha o del salón.
tipo: CANCHA o SALON.
activa: indica si el espacio está habilitado.
propietario_id: usuario propietario del espacio.
actividad_id: actividad que se realiza allí.
ubicacion_id: ubicación donde se encuentra.'''

class ReservaCrear(BaseModel):
    turno_id: int = Field(gt=0)
    usar_puntos: bool = False

class ReservaRespuesta(BaseModel):
    id: int
    turno_id: int
    usuario_id: int
    estado: EstadoReserva
    precio: Decimal
    puntos_usados: int = 0
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def sena(self) -> Decimal:
        return (self.precio * PORCENTAJE_SENA).quantize(Decimal("0.01"))

    @computed_field
    @property
    def saldo_en_el_lugar(self) -> Decimal:
        return self.precio - self.sena


class PagoCrear(BaseModel):
    medio_pago: MedioPago
    referencia_externa: str | None = Field(default=None, max_length=150)


class PagoRespuesta(BaseModel):
    id: int
    reserva_id: int
    monto: Decimal
    comision: Decimal
    medio_pago: MedioPago
    estado_pago: EstadoPago
    fecha_pago: datetime | None = None
    referencia_externa: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AliasCobro(BaseModel):
    alias_cobro: str = Field(min_length=3, max_length=100)


class ResumenCobros(BaseModel):
    alias_cobro: str | None
    a_confirmar: Decimal      
    confirmado: Decimal      
    liquidado: Decimal       
    saldo_a_cobrar: Decimal  


class PropietarioACobrar(BaseModel):
    propietario_id: int
    nombre: str
    alias_cobro: str | None
    saldo_a_cobrar: Decimal


class LiquidacionCrear(BaseModel):
    propietario_id: int
    monto: Decimal | None = Field(default=None, gt=0)  
    referencia_externa: str | None = Field(default=None, max_length=150)


class LiquidacionRespuesta(BaseModel):
    id: int
    propietario_id: int
    monto: Decimal
    alias_destino: str
    fecha: datetime
    referencia_externa: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PrecioDetalle(BaseModel):
    total: Decimal
    sena: Decimal
    detalle: list[str]


class ResenaCrear(BaseModel):
    puntaje: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=500)


class Autor(BaseModel):
    id: int
    nombre: str

    model_config = ConfigDict(from_attributes=True)


class ResenaRespuesta(BaseModel):
    id: int
    espacio_deportivo_id: int
    puntaje: int
    comentario: str | None = None
    fecha: datetime
    usuario: Autor

    model_config = ConfigDict(from_attributes=True)


class NotificacionRespuesta(BaseModel):
    id: int
    mensaje: str
    leida: bool
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class CambioRol(BaseModel):
    email: EmailStr
    tipo_usuario: Literal["CLIENTE", "PROPIETARIO"]