#!/bin/bash
# Deploy del LMS (RBSoftware) en el VPS.
#
# Compose real de produccion = docker-compose.yml (NO compose.prod.yml).
# La red `robotschool` del compose es external -> robotschool-inventory_robotschool
# (la del nginx); `up` reconecta solo con los alias correctos.
# Las migraciones NO corren al arrancar (el CMD del backend es solo uvicorn):
# se aplican a mano con Alembic.
#
# Orden seguro (evita la ventana donde el codigo nuevo espera un esquema que
# aun no existe): pull -> build (sin recrear) -> migrate (imagen nueva) -> up.
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE="docker compose -f docker-compose.yml"
NGINX_NET=robotschool-inventory_robotschool
LMS_URL=https://lms.miel-robotschool.com

echo '=== 1/5 Git pull ==='
git pull --ff-only

echo '=== 2/5 Build de imagenes (sin recrear contenedores) ==='
$COMPOSE build backend frontend

echo '=== 3/5 Migraciones Alembic (con la imagen nueva, backend viejo sigue sirviendo) ==='
$COMPOSE run --rm backend alembic upgrade head

echo '=== 4/5 Recrear contenedores con el codigo nuevo ==='
$COMPOSE up -d backend frontend

echo '--- asegurar red compartida del nginx (external; normalmente no-op) ---'
for cname in rbsoftware-backend rbsoftware-frontend; do
  if docker network inspect "$NGINX_NET" --format '{{range .Containers}}{{.Name}} {{end}}' | grep -qw "$cname"; then
    echo "$cname ya en $NGINX_NET"
  else
    docker network connect --alias "$cname" "$NGINX_NET" "$cname" && echo "$cname reconectado a $NGINX_NET"
  fi
done

echo '--- reload nginx ---'
docker exec robotschool_nginx nginx -s reload || echo 'WARN: no se pudo recargar nginx'

echo '=== 5/5 Verificacion ==='
sleep 5
STATUS=$(curl -sL -o /dev/null -w '%{http_code}' "$LMS_URL")
echo "LMS HTTP status: $STATUS"
if [ "$STATUS" = "200" ]; then
  echo 'DEPLOY OK'
else
  echo "DEPLOY con status inesperado: $STATUS" >&2
  exit 1
fi
