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
    "public_sanitized": true,
    "persona_label": "Persona E",
    "area_label": "Operaciones",
    "identity": {
      "source": "whatsapp",
      "verification_status": "empleado_provisional",
      "declared_name": "Dato privado local; no se publica crudo"
    },
    "objetivo_del_dia": "Objetivo público sanitizado del día.",
    "tickets_tareas": ["Tarea demo sin cliente ni identificadores privados"],
    "bloqueos": [],
    "interconsultas": [],
    "estado_aprobacion": "Aprobado",
    "item_evidence": [
      {
        "item": "Tarea demo sin cliente ni identificadores privados",
        "tipo": "project_task",
        "referencia": "Referencia sanitizada o Dato protegido",
        "estado_evidencia": "declarado_por_usuario",
        "fuente": "usuario",
        "observacion": "Nota sanitizada"
      }
    ]
  }
}
```

Regla de privacidad: no incluir nombres reales, teléfonos, correos, URLs internas, clientes, repositorios privados ni cuerpos de conversaciones en campos públicos. Los JSON publicados son assets estáticos y pueden consultarse directamente; por eso el script exige `public_sanitized: true`. Usar `persona_label` / `area_label` ya sanitizados. `identity.declared_name` puede existir en el payload privado local, pero el script no publica ese nombre crudo: publica la etiqueta pública sanitizada.

Flujo recomendado con inbox local:

1. Ale emite el bloque aprobado `CEREBRO_DAILY_RECORD`.
2. Guardar cada JSON como archivo local en `inbox/daily/`. No commitear esos JSON.
3. Validar sin escribir ni mover:

   ```bash
   python3 scripts/process_daily_inbox.py --dry-run
   ```

4. Procesar el inbox:

   ```bash
   python3 scripts/process_daily_inbox.py
   ```

   Cada registro correcto actualiza los datasets públicos sanitizados y mueve el JSON original a `archive/daily/YYYY-MM/`. Si un archivo falla, queda en `inbox/daily/` y el error se reporta por consola. El log local `logs/daily_inbox_processing.log` queda ignorado por Git porque puede contener nombres de archivos o contexto operativo.

5. Validar las salidas sanitizadas y revisar qué se va a publicar:

   ```bash
   python3 -m json.tool data/daily_planning.json >/dev/null
   python3 -m json.tool data/planning_evolution.json >/dev/null
   git status --short
   ```

6. Commitear/publicar sólo los archivos intencionales: scripts, documentación, placeholders y datasets sanitizados. No publicar `inbox/`, `archive/` ni logs con datos privados.

También se puede registrar un archivo individual de ejemplo:

```bash
python3 scripts/record_daily.py data/examples/cerebro_daily_record.example.json
```

Los scripts validan aprobación, fecha, objetivo y tareas; eliminan de los textos públicos patrones básicos de emails, teléfonos y URLs; actualizan `data/daily_planning.json` por upsert, guardan `registro_continuidad` sanitizado para retomar el hilo, marcan la fila como `registrado_en_cerebro` y refrescan el agregado semanal mínimo en `data/planning_evolution.json`.

## Fuentes

- Odoo Helpdesk mediante el gateway de sólo lectura
- Base histórica privada de patrones operativos
- Odoo Proyectos
- GitHub

La actualización diaria ejecuta `scripts/update_dashboard.py`, que a su vez regenera el radar con `scripts/generate_recurrences.py`. La capa visual no tiene acceso directo a credenciales.

Para probar solamente el generador del radar:

```bash
python3 scripts/generate_recurrences.py \
  --kb /ruta/a/base-historica-privada/patterns/index.json \
  --gateway http://127.0.0.1:18765 \
  --output /tmp/recurrences-preview.json
```

Las variables `CEREBRO_RECURRENCE_KB` y `CEREBRO_ODOO_GATEWAY` permiten cambiar las rutas operativas sin modificar el código.

## Seguridad

La publicación es pública. El radar no expone nombres de clientes, cuerpos de tickets ni credenciales; usa etiquetas genéricas y métricas agregadas. Todo cambio de fuentes debe conservar esa sanitización.
