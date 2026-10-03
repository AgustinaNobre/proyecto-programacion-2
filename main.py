from fastapi import FastAPI

import models
from database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def inicio():
    return {"mensaje": "API de reserva de canchas funcionando"}