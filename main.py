from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def inicio():
    return {"mensaje": "API de reserva de canchas funcionando"}