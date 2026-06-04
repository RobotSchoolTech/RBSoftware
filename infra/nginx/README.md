# nginx — RBSoftware LMS

## Producción: NO se sirve desde este repo

En el VPS el LMS **no** tiene un nginx propio. Lo sirve un **nginx maestro
compartido** (`robotschool_nginx`, puertos 80/443) que enruta todas las apps
del servidor por dominio (LMS, Inventory, Academy, portal, etc.), todas en la
red Docker compartida `robotschool`.

- **Config real del LMS:** repo `robotschool-inventory`,
  `docker/nginx/conf.d/rbsoftware.conf` (montada en `robotschool_nginx`).
- Sirve `lms.miel-robotschool.com` → `rbsoftware-backend:8000` (`/api/`),
  `robotschool_minio:9000` (`/storage/`) y `rbsoftware-frontend:3000` (`/`).
- Usa `resolver 127.0.0.11 valid=30s` + variables en `proxy_pass`, de modo que
  nginx **re-resuelve los upstreams cada 30 s**. Por eso recrear contenedores
  ya **no** provoca un 502 permanente (solo hay que esperar ~30 s, sin reload).

> ⚠️ Por eso aquí **no** existe `default.prod.conf` ni un servicio `nginx` en
> `docker-compose.yml`. Añadir uno competiría por el puerto 80 con
> `robotschool_nginx` y rompería el modelo maestro multi-app.

Para cambiar el ruteo de prod del LMS, editar `rbsoftware.conf` en
`robotschool-inventory` y recargar: `docker exec robotschool_nginx nginx -s reload`.

## Desarrollo local: sí hay nginx propio

`compose.dev.yml` levanta un nginx local que monta `conf.d/default.dev.conf`
(proxy a `backend:8000` / `frontend:3000` / `minio:9000` dentro de la red de
compose). Es solo para el flujo de desarrollo y no aplica a producción.
