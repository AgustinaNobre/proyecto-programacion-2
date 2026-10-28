#describe qué datos permitimos que entren a nuestra API

from pydantic import BaseModel, EmailStr


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