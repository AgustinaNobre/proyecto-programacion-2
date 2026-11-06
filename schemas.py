#describe qué datos permitimos que entren a nuestra API

from datetime import datetime
from decimal import Decimal

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
    nombre: str
    descripcion: str | None = None

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

    model_config = ConfigDict(from_attributes=True)

'''id: identificador del espacio, generado por PostgreSQL.
nombre: nombre de la cancha o del salón.
tipo: CANCHA o SALON.
activa: indica si el espacio está habilitado.
propietario_id: usuario propietario del espacio.
actividad_id: actividad que se realiza allí.
ubicacion_id: ubicación donde se encuentra.'''


class ReservaRespuesta(BaseModel):
    id: int
    turno_id: int
    usuario_id: int
    estado: EstadoReserva
    precio: Decimal
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def sena(self) -> Decimal:
        # lo que se paga por la app
        return (self.precio * PORCENTAJE_SENA).quantize(Decimal("0.01"))

    @computed_field
    @property
    def saldo_en_el_lugar(self) -> Decimal:
        # lo que se le paga al propietario en la cancha
        return self.precio - self.sena


class PagoCrear(BaseModel):
    medio_pago: MedioPago  # TRANSFERENCIA, MP o TARJETA
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
    alias_cobro: str = Field(min_length=3, max_length=100)  # CBU o alias


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