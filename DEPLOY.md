# 🚀 MyPlanner - Guía de Despliegue en Render

## 📋 Configuración de Variables de Entorno en Render

Cuando despliegues tu aplicación en Render, debes configurar las siguientes variables de entorno:

### Variables Requeridas:

```env
DB_HOST=tu-servidor-mysql.aivencloud.com
DB_PORT=22158
DB_USER=tu-usuario
DB_PASSWORD=tu-contraseña-segura
DB_NAME=defaultdb
SECRET_KEY=tu_clave_secreta_generada_aqui
FLASK_ENV=production
```

**⚠️ NOTA**: Usa las credenciales reales de tu base de datos Aiven (las encontrarás en tu archivo `.env` local).

## 🔐 Generar SECRET_KEY Segura

Antes de desplegar, genera una clave secreta aleatoria:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copia el resultado y úsalo como valor de `SECRET_KEY` en Render.

## 🚀 Pasos para Desplegar en Render

### 1. Preparar el Repositorio

```bash
# Añadir todos los cambios
git add .

# Commit con mensaje descriptivo
git commit -m "Preparar proyecto para despliegue en Render con Aiven MySQL"

# Subir a GitHub
git push origin main
```

### 2. Crear Web Service en Render

1. Ve a [render.com](https://render.com) e inicia sesión
2. Click en **"New +"** → **"Web Service"**
3. Conecta tu repositorio de GitHub (`PeteerDHeras/proyectoFinal`)
4. Configura el servicio:
   - **Name**: `myplanner` (o el nombre que prefieras)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: `Free`

### 3. Configurar Variables de Entorno

En la sección **"Environment"** de tu Web Service en Render, añade una por una:

| Variable | Valor |
|----------|-------|
| `DB_HOST` | (tu servidor Aiven MySQL) |
| `DB_PORT` | `22158` |
| `DB_USER` | (tu usuario de Aiven) |
| `DB_PASSWORD` | (tu contraseña de Aiven) |
| `DB_NAME` | `defaultdb` |
| `SECRET_KEY` | (tu clave generada con `secrets.token_hex(32)`) |
| `FLASK_ENV` | `production` |

**💡 TIP**: Copia estos valores de tu archivo `.env` local.

**⚠️ IMPORTANTE**: No uses comillas en los valores de las variables en Render.

### 4. Desplegar

1. Click en **"Create Web Service"**
2. Espera a que se complete el despliegue (puede tardar 5-10 minutos)
3. Render te proporcionará una URL como: `https://myplanner.onrender.com`

## 🗄️ Base de Datos (Aiven)

Tu base de datos MySQL está alojada en Aiven Cloud:

### Características:
- **SSL/TLS**: Conexión cifrada automática (configurada en el código)
- **Puerto personalizado**: 22158
- **Certificado**: No necesitas descargar `ca.pem`, se maneja automáticamente

### Verificar Conexión:

```bash
python test_db_connection.py
```

Este script verifica que la conexión a Aiven funcione correctamente.

## 📝 Archivos Importantes

- **`Procfile`**: Define cómo Render debe iniciar tu app (`gunicorn app:app`)
- **`runtime.txt`**: Especifica la versión de Python (3.11.0)
- **`requirements.txt`**: Lista todas las dependencias necesarias
- **`.env`**: Variables de entorno locales (NO subir a Git)
- **`.env.example`**: Plantilla de variables de entorno (SÍ subir a Git)
- **`.gitignore`**: Protege archivos sensibles

## 🧪 Probar Localmente

Antes de desplegar, prueba la aplicación en tu máquina:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python app.py
```

La aplicación estará disponible en `http://localhost:5001`

## 📦 Dependencias

```
Flask==3.0.0
mysql-connector-python==8.2.0
bcrypt==4.1.2
python-dotenv==1.0.0
Werkzeug==3.0.1
gunicorn==21.2.0
```

## ✅ Checklist de Despliegue

Antes de desplegar, verifica:

- [ ] Variables de entorno configuradas en Render
- [ ] SECRET_KEY generada y diferente de la de desarrollo
- [ ] Base de datos Aiven activa y accesible
- [ ] Archivo `.env` está en `.gitignore`
- [ ] Repositorio GitHub actualizado con último código
- [ ] Archivos `Procfile` y `runtime.txt` presentes
- [ ] `requirements.txt` tiene todas las dependencias con versiones específicas
- [ ] Conexión a base de datos probada con `test_db_connection.py`

## 🐛 Solución de Problemas

### Error de Conexión a MySQL

**Síntoma**: La app no puede conectarse a la base de datos

**Solución**:
1. Verifica que todas las variables `DB_*` estén correctamente escritas en Render
2. Asegúrate de que el puerto sea `22158` (número, no string)
3. Revisa que la base de datos Aiven esté activa
4. Comprueba los logs en Render: **Dashboard → Logs**

### Error 502/503

**Síntoma**: La aplicación no responde

**Solución**:
1. Verifica que el `Procfile` sea correcto: `web: gunicorn app:app`
2. Asegúrate de que `gunicorn` esté en `requirements.txt`
3. Revisa los logs de Render para ver errores específicos
4. Verifica que `app.py` tenga `if __name__ == '__main__':`

### Variables de Entorno No Funcionan

**Síntoma**: La app usa valores por defecto en lugar de los de Render

**Solución**:
1. Asegúrate de haber guardado las variables en Render (botón "Save Changes")
2. Reinicia el servicio después de cambiar variables
3. Verifica que `python-dotenv` esté instalado
4. No uses comillas en los valores de las variables en Render

### Errores de Dependencias

**Síntoma**: El build falla al instalar dependencias

**Solución**:
1. Verifica que todas las versiones en `requirements.txt` sean compatibles
2. Asegúrate de que `python-3.11.0` esté disponible (o cambia versión en `runtime.txt`)
3. Revisa que no haya dependencias faltantes

## 🔄 Actualizar la Aplicación

Para actualizar tu app después del primer despliegue:

```bash
# Hacer cambios en el código
git add .
git commit -m "Descripción de los cambios"
git push origin main
```

Render detectará automáticamente el push y redesplegará la aplicación.

## 📞 Soporte

- **Render Docs**: https://render.com/docs
- **Aiven Docs**: https://docs.aiven.io/
- **Flask Docs**: https://flask.palletsprojects.com/

## 🎉 ¡Listo!

Una vez completados todos los pasos, tu aplicación estará disponible en la URL proporcionada por Render. Puedes compartir el enlace y empezar a usar MyPlanner en producción.

---

**Última actualización**: Noviembre 2025
