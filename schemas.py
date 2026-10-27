#describe qué datos permitimos que entren a nuestra API

from pydantic import BaseModel, EmailStr, ConfigDict
from models import RolUsuario


class UsuarioCrear(BaseModel):
    nombre: str
    email: EmailStr
    password: str

class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    puntos: int
    rol: RolUsuario



class Token(BaseModel):
    access_token: str
    token_type: str