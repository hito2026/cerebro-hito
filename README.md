# Cerebro Hito · Diario de actividades

Primera versión del portal corporativo para consolidar actividad de HitoFusión.

## Estado

El portal publica dos datasets sanitizados:

- `data/activities.json`, generado desde las fuentes operativas permitidas;
- `data/recurrences.json`, un radar automático de temas recurrentes de desarrollo.

El radar combina la base histórica de patrones con metadatos recientes de Helpdesk. Sólo considera familias `BUG`, `CONFIG` e `INTEGRATION`, elimina nombres de clientes de la salida pública y marca sus resultados como candidatos que requieren validación humana. El chatter de Odoo todavía no está disponible, por lo que la cobertura se declara parcial en el propio informe.

## Desarrollo local

```bash
python3 -m http.server 8080
```

Abrir `http://localhost:8080`.

## Fuentes

- Odoo Helpdesk mediante el gateway de sólo lectura
- Base histórica `jinzo-soporte/knowledge/patterns/index.json`
- Odoo Proyectos
- GitHub

La actualización diaria ejecuta `scripts/update_dashboard.py`, que a su vez regenera el radar con `scripts/generate_recurrences.py`. La capa visual no tiene acceso directo a credenciales.

Para probar solamente el generador del radar:

```bash
python3 scripts/generate_recurrences.py \
  --kb /ruta/a/jinzo-soporte/knowledge/patterns/index.json \
  --gateway http://127.0.0.1:18765 \
  --output /tmp/recurrences-preview.json
```

Las variables `CEREBRO_RECURRENCE_KB` y `CEREBRO_ODOO_GATEWAY` permiten cambiar las rutas operativas sin modificar el código.

## Seguridad

La publicación es pública. El radar no expone nombres de clientes, cuerpos de tickets ni credenciales; usa etiquetas genéricas y métricas agregadas. Todo cambio de fuentes debe conservar esa sanitización.
