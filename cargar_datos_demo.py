"""Carga espacios y turnos de demostración mediante la API de ACTIVA.

Ejecutar desde el equipo anfitrión con Python 3.10+:
    python cargar_datos_demo.py

No requiere bibliotecas externas. No almacena credenciales.
"""
import getpass
import json
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API = "http://localhost:8000"
PROPIETARIO_ID = 2
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")

# Direcciones y coordenadas ficticias de demostración, aproximadas.
ESPACIOS = [
    ("ACTIVA Demo - Arena Norte Futbol 5", "CANCHA", ["Fútbol", "Futbol", "Fútbol 5", "Futbol 5"], "Av. San Martín 2100, San Martín, Buenos Aires (demo)", -34.5750, -58.5360, 35000, 1, 60),
    ("ACTIVA Demo - Punto Padel", "CANCHA", ["Pádel", "Padel"], "Av. Balbín 2400, San Martín, Buenos Aires (demo)", -34.5735, -58.5320, 24000, 1, 90),
    ("ACTIVA Demo - Club Central Tenis", "CANCHA", ["Tenis"], "Av. Mitre 3800, Villa Ballester, Buenos Aires (demo)", -34.5510, -58.5580, 20000, 1, 60),
    ("ACTIVA Demo - Urban Court Basquet", "CANCHA", ["Básquet", "Basquet", "Baloncesto"], "Av. 25 de Mayo 1900, San Martín, Buenos Aires (demo)", -34.5770, -58.5380, 28000, 1, 60),
    ("ACTIVA Demo - Box 360 Cross Training", "SALON", ["Cross Training", "Crossfit", "CrossFit", "Entrenamiento funcional"], "Av. Rodríguez Peña 3100, Santos Lugares, Buenos Aires (demo)", -34.6040, -58.5450, 8000, 14, 60),
    ("ACTIVA Demo - Move Studio Funcional", "SALON", ["Funcional", "Entrenamiento funcional"], "Av. La Plata 1800, Santos Lugares, Buenos Aires (demo)", -34.6020, -58.5430, 7000, 12, 60),
    ("ACTIVA Demo - Espacio Zen Yoga", "SALON", ["Yoga", "Yoga deportivo"], "Av. Alvear 2600, Villa Ballester, Buenos Aires (demo)", -34.5470, -58.5570, 6500, 10, 60),
    ("ACTIVA Demo - Core Studio Pilates", "SALON", ["Pilates"], "Av. Libertador 3100, San Martín, Buenos Aires (demo)", -34.5680, -58.5400, 9000, 8, 60),
]


def normalizar(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.casefold()) if unicodedata.category(c) != "Mn").strip()


def solicitud(metodo, ruta, token=None, datos=None, formulario=False):
    cuerpo = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if datos is not None:
        if formulario:
            cuerpo = urllib.parse.urlencode(datos).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + ruta, data=cuerpo, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{metodo} {ruta}: HTTP {e.code}: {detalle[:350]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"No se puede conectar con {API}. Revisá Docker. {e}") from e


def main():
    print("ACTIVA - carga de datos DEMO (solo API local)")
    print("Los datos son ficticios y las direcciones son aproximadas; no representan establecimientos reales.")
    email = input("Email de Demo Propietario: ").strip()
    clave = getpass.getpass("Contraseña (no se muestra): ")
    token = solicitud("POST", "/login", datos={"username": email, "password": clave}, formulario=True)["access_token"]
    perfil = solicitud("GET", "/usuarios/me", token)
    if perfil["id"] != PROPIETARIO_ID or perfil["tipo_usuario"] not in ("PROPIETARIO", "SUPERADMIN"):
        raise RuntimeError("La cuenta debe ser Demo Propietario, ID 2, con rol PROPIETARIO. No se modificó nada.")
    print("Sesión validada:", perfil["nombre"])

    actividades = solicitud("GET", "/actividades")
    existentes = solicitud("GET", "/espacios-deportivos")
    turnos = solicitud("GET", "/turnos")
    nombres = {e["nombre"]: e for e in existentes}
    faltantes = []
    creados = 0
    turnos_creados = 0

    # Fechas futuras: mañana y pasado mañana, evitando turnos del pasado.
    ahora = datetime.now(ZONA)
    fechas = [(ahora + timedelta(days=d)).date() for d in (1, 2, 3)]

    for nombre, tipo, alternativas, direccion, lat, lon, precio, cupo, minutos in ESPACIOS:
        actividad = next((a for alternativa in alternativas for a in actividades if normalizar(a["nombre"]) == normalizar(alternativa)), None)
        if actividad is None:
            faltantes.append(f"{nombre}: falta actividad ({', '.join(alternativas)})")
            continue
        espacio = nombres.get(nombre)
        if espacio and espacio["propietario_id"] != PROPIETARIO_ID:
            print("OMITIDO, nombre usado por otro propietario:", nombre)
            continue
        if espacio is None:
            ubicacion = solicitud("POST", "/ubicaciones", token, {"direccion": direccion, "latitud": lat, "longitud": lon})
            espacio = solicitud("POST", "/espacios-deportivos", token, {"nombre": nombre, "tipo": tipo, "actividad_id": actividad["id"], "ubicacion_id": ubicacion["id"]})
            nombres[nombre] = espacio
            creados += 1
            print("Espacio creado:", nombre)
        else:
            print("Espacio existente:", nombre)

        # Dos turnos por día y espacio; nunca superpuestos.
        for fecha in fechas:
            for hora in (10, 18):
                inicio = datetime(fecha.year, fecha.month, fecha.day, hora, 0)
                fin = inicio + timedelta(minutes=minutos)
                # Los timestamps se envían como hora local sin offset, como el frontend.
                inicio_txt = inicio.isoformat(timespec="seconds")
                fin_txt = fin.isoformat(timespec="seconds")
                # /turnos solo devuelve disponibles. Para idempotencia exacta,
                # los turnos reservados/no disponibles pueden requerir inspección adicional.
                duplicado = any(t["espacio_deportivo_id"] == espacio["id"] and t["fecha_hora_inicio"][:19] == inicio_txt for t in turnos)
                if duplicado:
                    continue
                try:
                    nuevo = solicitud("POST", "/turnos", token, {"fecha_hora_inicio": inicio_txt, "fecha_hora_fin": fin_txt, "precio": precio, "cupo_maximo": cupo, "espacio_deportivo_id": espacio["id"]})
                    turnos.append(nuevo)
                    turnos_creados += 1
                except RuntimeError as e:
                    # La API rechaza superposiciones, incluidas las no visibles en /turnos.
                    if "Ya existe un turno en ese horario" in str(e):
                        print("Turno ya existente:", nombre, inicio_txt)
                    else:
                        print("No se pudo crear turno:", nombre, inicio_txt, e)
    print(f"\nResultado: {creados} espacios nuevos, {turnos_creados} turnos nuevos.")
    if faltantes:
        print("\nActividades que faltan en el catálogo (las crea un SUPERADMIN):")
        for item in faltantes:
            print(" -", item)
    print("\nAbrí http://localhost:5500 y actualizá Explorar / Mi complejo.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as error:
        print("\nERROR:", error)