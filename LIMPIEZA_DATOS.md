# Limpieza Automática de Datos Antiguos

Este documento explica cómo funciona la limpieza automática de eventos y tareas antiguas.

## 🔧 Funcionamiento

La aplicación incluye una función `limpiar_datos_antiguos(dias=3)` que elimina:
- **Eventos** con más de X días de antigüedad (basado en `fecha_evento`)
- **Tareas** con más de X días de antigüedad (basado en `fecha_limite`)

Por defecto, se eliminan datos con más de **3 días** de antigüedad.

## 🏠 En Desarrollo Local

La limpieza se ejecuta **automáticamente al iniciar la aplicación** cuando:
- `FLASK_ENV=development` (valor por defecto)

Verás un mensaje en la consola:
```
[LIMPIEZA AUTOMÁTICA] Se eliminaron X eventos y Y tareas antiguas (más de 3 días)
```

## 🚀 En Producción

### Opción 1: Endpoint Administrativo (Recomendado)

La aplicación expone un endpoint que solo los administradores pueden usar:

**URL:** `POST /admin/limpiar-datos`

**Autenticación:** Requiere sesión activa con rol de administrador (rol==3)

**Parámetros (opcionales):**
- `dias`: Número de días de antigüedad (por defecto 3)

**Ejemplo de uso con curl:**
```bash
curl -X POST https://tu-app.com/admin/limpiar-datos \
  -H "Cookie: session=tu_cookie_de_sesion" \
  -d "dias=3"
```

**Respuesta exitosa:**
```json
{
  "success": true,
  "eventos_eliminados": 5,
  "tareas_eliminadas": 12,
  "mensaje": "Se eliminaron 5 eventos y 12 tareas con más de 3 días de antigüedad"
}
```

### Opción 2: Cron Job en el Servidor

Si tienes acceso al servidor, puedes configurar un cron job:

```bash
# Ejecutar limpieza todos los días a las 3:00 AM
0 3 * * * curl -X POST https://tu-app.com/admin/limpiar-datos -H "Cookie: session=COOKIE_ADMIN"
```

### Opción 3: Heroku Scheduler

Si usas Heroku, puedes usar [Heroku Scheduler](https://elements.heroku.com/addons/scheduler):

1. Añade el addon Scheduler a tu app
2. Configura un trabajo diario con este comando:
```bash
curl -X POST https://tu-app.herokuapp.com/admin/limpiar-datos -H "Cookie: session=$ADMIN_SESSION_COOKIE"
```

### Opción 4: Railway Cron Jobs

Si usas Railway, puedes configurar cron jobs nativos en el dashboard.

### Opción 5: GitHub Actions (Gratis)

Crea `.github/workflows/cleanup.yml`:

```yaml
name: Limpieza Automática de Datos

on:
  schedule:
    - cron: '0 3 * * *'  # Todos los días a las 3:00 AM UTC
  workflow_dispatch:  # Permite ejecutar manualmente

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - name: Ejecutar limpieza
        run: |
          curl -X POST ${{ secrets.APP_URL }}/admin/limpiar-datos \
            -H "Cookie: session=${{ secrets.ADMIN_SESSION_COOKIE }}" \
            -d "dias=3"
```

**Configurar en GitHub:**
1. Ve a Settings > Secrets and variables > Actions
2. Añade secrets:
   - `APP_URL`: URL de tu aplicación
   - `ADMIN_SESSION_COOKIE`: Cookie de sesión de un admin

## 🔐 Seguridad

- El endpoint requiere **autenticación** (sesión activa)
- Solo usuarios con **rol de administrador (rol==3)** pueden ejecutarlo
- Los datos se eliminan **permanentemente** de la base de datos

## ⚙️ Configuración

Para cambiar el número de días de antigüedad:

**En el código:**
```python
# En db.py
limpiar_datos_antiguos(dias=7)  # Cambiar a 7 días
```

**O mediante el endpoint:**
```bash
curl -X POST https://tu-app.com/admin/limpiar-datos -d "dias=7"
```

## 📊 Monitoreo

Puedes ver en los logs cuántos registros se eliminaron:
- En desarrollo: Se muestra en la consola al iniciar
- En producción: El endpoint devuelve la cantidad eliminada

## ⚠️ Importante

- **No hay deshacer**: Los datos eliminados no se pueden recuperar
- **Prueba primero**: Ejecuta manualmente para verificar el comportamiento
- **Ajusta los días**: Según tus necesidades (1 día, 3 días, 1 semana, etc.)
- **Revisa los logs**: Comprueba que la limpieza funciona correctamente

## 🔄 Cambiar de 3 días a otro valor

Si quieres cambiar el periodo por defecto de 3 días a otro valor:

1. **En desarrollo (al iniciar la app):**
   ```python
   # app.py línea ~32
   limpiar_datos_antiguos(dias=7)  # Cambiar de 3 a 7
   ```

2. **En el endpoint (producción):**
   ```bash
   curl -X POST https://tu-app.com/admin/limpiar-datos -d "dias=7"
   ```

3. **En la función (por defecto):**
   ```python
   # db.py línea ~479
   def limpiar_datos_antiguos(dias=7):  # Cambiar de 3 a 7
   ```
