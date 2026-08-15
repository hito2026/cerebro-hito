# Cerebro Hito · Diario de actividades

Primera versión del portal corporativo para consolidar actividad de HitoFusión.

## Estado

La interfaz funciona con datos demostrativos ubicados en `data/activities.json`. No contiene credenciales ni información real de clientes.

## Desarrollo local

```bash
python3 -m http.server 8080
```

Abrir `http://localhost:8080`.

## Fuentes previstas

- Odoo Helpdesk
- Odoo Proyectos
- Odoo CRM
- GitHub
- Daily Meetings

Los recolectores futuros generarán el mismo esquema JSON o alimentarán una API compatible. La capa visual no tendrá acceso directo a credenciales.

## Seguridad

El repositorio es privado. Antes de habilitar GitHub Pages se debe confirmar qué modalidad de acceso ofrece el plan de la organización. No publicar datos corporativos reales en un sitio público.
