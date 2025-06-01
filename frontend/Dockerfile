FROM node:20-alpine

WORKDIR /app

# Instala http-server globalmente
RUN npm install -g http-server

# Copia los archivos estáticos del frontend
COPY . .

# Expone el puerto que http-server usará
EXPOSE 8080

# Ejecuta http-server
CMD ["http-server", "-p", "8080", "-c-1"]

