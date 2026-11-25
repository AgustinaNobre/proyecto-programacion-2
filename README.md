
# ACTIVA — Plataforma de reservas deportivas

Proyecto desarrollado para la materia Programación 2.

ACTIVA es una plataforma que permite buscar y reservar canchas y clases deportivas, facilitando la gestión de espacios, actividades, turnos y reservas tanto para usuarios como para propietarios.

## Funcionalidades principales

- Registro e inicio de sesión de usuarios.
- Gestión de usuarios y propietarios.
- Búsqueda de espacios y actividades deportivas.
- Reserva de canchas y clases.
- Gestión de turnos y cupos.
- Gestión de pagos y liquidaciones.
- Sistema de notificaciones mediante el patrón Observer.
- Interfaz gráfica para interactuar con la aplicación.

## Tecnologías utilizadas

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL

### Frontend

- HTML
- CSS
- JavaScript

### Infraestructura y testing

- Docker
- Docker Compose
- Docker Hub
- GitHub Actions
- Pytest

## Arquitectura de la aplicación

La aplicación se organiza en tres componentes principales:

- Frontend: interfaz gráfica con la que interactúan los usuarios.
- Backend: API REST desarrollada con FastAPI, encargada de la lógica de negocio.
- Base de datos: PostgreSQL, encargada de almacenar la información del sistema.

Los componentes se ejecutan mediante contenedores Docker.

## Despliegue con Docker

La imagen de la API está publicada en Docker Hub:

https://hub.docker.com/r/agusnobre/api-canchas

### Requisitos

- Git.
- Docker Desktop instalado y funcionando.
- Docker Compose disponible.

### 1. Clonar el repositorio

```bash
git clone https://github.com/AgustinaNobre/proyecto-programacion-2.git
cd proyecto-programacion-2
```

### 2. Configurar las variables de entorno

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
DB_USER=canchas_user
DB_PASSWORD=reemplazar_por_contrasena_segura
DB_NAME=canchas_db
SECRET_KEY=reemplazar_por_clave_secreta_segura
API_PORT=8000
```

Reemplazar los valores de DB_PASSWORD y SECRET_KEY por claves seguras.

IMPORTANTE: el archivo `.env` contiene información sensible y no debe compartirse ni subirse a GitHub.

### 3. Levantar la aplicación

Desde la carpeta raíz del proyecto, ejecutar:

```bash
docker compose -p api-canchas --env-file .env -f compose.deploy.yaml up -d --build
```

Docker Compose se encarga de:

- Iniciar la base de datos PostgreSQL.
- Descargar la imagen de la API si no está disponible localmente.
- Iniciar el backend.
- Construir e iniciar el frontend.

### 4. Acceder a la aplicación

Una vez iniciados los contenedores:

- Interfaz de ACTIVA: http://localhost:5500
- Documentación interactiva Swagger: http://localhost:8000/docs
- Esquema OpenAPI: http://localhost:8000/openapi.json

### 5. Detener la aplicación

```bash
docker compose -p api-canchas --env-file .env -f compose.deploy.yaml down
```

Los datos de PostgreSQL se conservan en un volumen persistente de Docker.

## Documentación de la API

La API cuenta con documentación interactiva generada mediante Swagger, que permite consultar los endpoints, sus parámetros y respuestas, y realizar solicitudes directamente desde el navegador.

## Testing

El proyecto incluye pruebas automatizadas para verificar el funcionamiento de la API y la lógica de reservas.

También cuenta con un workflow de GitHub Actions para la ejecución automatizada de pruebas.

## Imagen Docker

- Usuario de Docker Hub: agusnobre
- Imagen: agusnobre/api-canchas:latest

## Repositorio

https://github.com/AgustinaNobre/proyecto-programacion-2

## Proyecto académico

Materia: Programación 2

Licenciatura en Ciencia de Datos
