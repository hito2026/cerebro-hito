# Publicación del tablero desde Cerebro

Cuando el usuario pida actualizar o publicar **Cerebro Hito en datos**, explicá que la salida pública se sanitiza y pedí confirmación explícita si el mismo mensaje no incluye la orden de publicar.

Con confirmación, ejecutá:

```bash
curl -fsS -X POST http://127.0.0.1:18766/v1/publish
```

Informá el número de actividades y personas devuelto. El servicio consulta Odoo y GitHub, actualiza el JSON, valida, crea un commit y publica `main`. Nunca edites el JSON manualmente ni busques credenciales.
