#describe qué datos permitimos que entren a nuestra API

from pydantic import BaseModel, EmailStr


class UsuarioCrear(BaseModel):
    nombre: str
    email: EmailStr
    password: str