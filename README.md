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

## Registro local de dailies aprobadas

Ale u otro operador puede preparar una daily aprobada como bloque `CEREBRO_DAILY_RECORD` en JSON y registrarla localmente sin tocar servicios de publicación:

```json
{
  "daily_record": {
    "date": "2026-08-21",
    "approved": true,
    "persona_label": "Persona E",
    "area_label": "Operaciones",
    "objetivo_del_dia": "Objetivo público sanitizado del día.",
    "tickets_tareas": ["Tarea demo sin cliente ni identificadores privados"],
    "bloqueos": [],
    "interconsultas": [],
    "estado_aprobacion": "Aprobado"
  }
}
```

Regla de privacidad: no incluir nombres reales, teléfonos, correos, URLs internas, clientes ni cuerpos de conversaciones. Usar `persona_label` / `area_label` ya sanitizados; si sólo existe el dato privado, omitirlo o dejarlo en claves privadas fuera de la salida pública para que el script publique `Dato protegido`.

Ejecutar desde el repositorio:

```bash
python3 scripts/record_daily.py data/examples/cerebro_daily_record.example.json
python3 -m json.tool data/daily_planning.json >/dev/null
python3 -m json.tool data/planning_evolution.json >/dev/null
```

El script valida aprobación, fecha, objetivo y tareas; elimina de los textos públicos patrones básicos de emails, teléfonos y URLs; actualiza `data/daily_planning.json` por upsert, guarda `registro_continuidad` sanitizado para retomar el hilo, marca la fila como `registrado_en_cerebro` y refresca el agregado semanal mínimo en `data/planning_evolution.json`.

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
