#describe qué datos permitimos que entren a nuestra API

from pydantic import BaseModel, EmailStr, ConfigDict, Field


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
