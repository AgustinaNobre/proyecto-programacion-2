# API de Reserva de Canchas

API desarrollada con FastAPI y PostgreSQL para gestionar espacios deportivos, turnos, reservas, pagos y liquidaciones.

## Tecnologías

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Docker y Docker Compose

## Despliegue con Docker

La imagen de la API está publicada en Docker Hub:

https://hub.docker.com/r/morahanna/api-canchas

### Requisitos

- Docker Desktop instalado y funcionando.
- Docker Compose disponible.

### 1. Configurar las variables de entorno

Crear un archivo `.env` en la raíz del proyecto. Para generar automáticamente las claves necesarias, ejecutar en la terminal:

```bash
DB_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 32)

cat > .env <<EOF
DB_USER=canchas_user
DB_PASSWORD=$DB_PASSWORD
DB_NAME=canchas_db
SECRET_KEY=$SECRET_KEY
API_PORT=8000
EOF
```

Este comando genera una contraseña segura para PostgreSQL y una clave secreta para la API.

**Importante:** el archivo `.env` contiene información sensible. No debe compartirse ni subirse a GitHub.

### 2. Levantar la aplicación

Desde la carpeta del proyecto, ejecutar:

```bash
docker compose -p api-canchas --env-file .env -f compose.deploy.yaml up -d
```

Docker Compose descargará la imagen de Docker Hub si no está disponible localmente, iniciará PostgreSQL y luego levantará la API.

### 3. Acceder a la API

Una vez iniciados los contenedores, abrir:

- Documentación interactiva (Swagger): http://localhost:8000/docs
- Esquema OpenAPI: http://localhost:8000/openapi.json

### 4. Detener la aplicación

Ejecutar:

```bash
docker compose -p api-canchas --env-file .env -f compose.deploy.yaml down
```

Los datos de PostgreSQL se conservan en un volumen de Docker. Detener los contenedores de esta manera no elimina la base de datos.

## Imagen Docker

- Usuario de Docker Hub: `morahanna`
- Imagen: `morahanna/api-canchas:latest`