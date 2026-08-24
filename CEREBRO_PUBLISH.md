# Publicación del tablero desde Cerebro

Cuando el usuario pida actualizar o publicar **Cerebro Hito en datos**, explicá que la salida pública se sanitiza y pedí confirmación explícita si el mismo mensaje no incluye la orden de publicar.

Con confirmación, ejecutá:

```bash
curl -fsS -X POST http://127.0.0.1:18766/v1/publish
```

El servicio consulta Odoo y GitHub, actualiza `data/activities.json`, regenera `data/recurrences.json`, valida, crea un commit y publica `main`. El radar utiliza la KB histórica configurada en `CEREBRO_RECURRENCE_KB` y el gateway indicado por `CEREBRO_ODOO_GATEWAY`; si cualquiera de esas fuentes falla, la publicación debe fallar de forma visible en lugar de conservar silenciosamente un radar obsoleto.

Después de publicar, verificá que la respuesta sea exitosa, que ambos JSON sean válidos y que GitHub Pages muestre la nueva fecha del radar. Informá por separado actividades, tickets recientes analizados y candidatos recurrentes. Nunca edites los JSON manualmente ni busques credenciales.
