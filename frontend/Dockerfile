
# Imagen liviana de Python para ejecutar el frontend
FROM python:3.13-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiamos los archivos del frontend
COPY . .

# Puerto utilizado por el servidor web
EXPOSE 5500

# Iniciamos el servidor y permitimos conexiones desde Docker
CMD ["python", "servidor.py", "--host", "0.0.0.0", "--puerto", "5500"]
