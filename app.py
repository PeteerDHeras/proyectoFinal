"""Aplicación Flask principal.

Este fichero contiene las rutas y vistas del proyecto.
He añadido comentarios explicativos y dejado las líneas de
`@login_required` comentadas (con la marca "TODO: activar login_required")
en cada ruta para poder activarlas fácilmente en el futuro.

Notas:
- Mantén la clave secreta en variables de entorno en producción.
"""

from datetime import datetime, time, timedelta
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, get_flashed_messages
from functools import wraps
from db import *  # funciones de acceso a datos: obtener_eventos, crear_tarea, etc.
from models import Evento, Tarea
from utils import (normalizar_hora, normalizar_fecha, validar_fechas, 
                   limpiar_valor_opcional, filtrar_eventos_por_fecha, 
                   filtrar_tareas_por_fecha, validar_texto_seguro, 
                   validar_fecha_formato, validar_hora_formato, validar_prioridad, validar_estado,
                   validar_fecha_no_pasada, validar_fecha_hora_no_pasada, validar_no_vacio, sanitizar_texto,
                   validar_longitud, validar_rango_horas)
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


# ------------------ CONFIGURACIÓN FLASK ------------------
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave_secreta_segura')

# Sesiones activas (usuario -> {'token': str, 'last_active': datetime})
# Nota: En producción con múltiples procesos/containers conviene usar tabla en BD o Redis.
ACTIVE_USER_SESSIONS = {}
SESSION_TTL_MINUTES = 30  # Expiración de sesión inactiva para permitir reconexión
SESSION_MAX_AGE_HOURS = 24  # Tiempo máximo absoluto de sesión (fuerza re-login)

def cleanup_expired_sessions():
    """Limpia sesiones expiradas del diccionario ACTIVE_USER_SESSIONS.
    
    Se ejecuta automáticamente antes de cada login para evitar bloqueos
    por sesiones huérfanas (browser cerrado sin logout).
    """
    now = datetime.utcnow()
    expired_users = []
    
    for usuario, data in ACTIVE_USER_SESSIONS.items():
        last_active = data.get('last_active')
        if not last_active:
            expired_users.append(usuario)
            continue
            
        # Expirar si excede TTL de inactividad
        inactive_time = now - last_active
        if inactive_time > timedelta(minutes=SESSION_TTL_MINUTES):
            expired_users.append(usuario)
            print(f"[SESSION CLEANUP] Usuario '{usuario}' expirado por inactividad ({inactive_time.total_seconds()/60:.1f} min)")
    
    # Remover sesiones expiradas
    for usuario in expired_users:
        ACTIVE_USER_SESSIONS.pop(usuario, None)
    
    if expired_users:
        print(f"[SESSION CLEANUP] Limpiadas {len(expired_users)} sesiones expiradas")
    
    return len(expired_users)

# Filtro Jinja para mostrar el usuario con primera letra mayúscula sin alterar el resto
@app.template_filter('capitalizar_primera')
def capitalizar_primera(valor):
    if not isinstance(valor, str) or not valor:
        return ''
    return valor[0].upper() + valor[1:]

# Limpieza automática SOLO en desarrollo (cuando debug=True)
# En producción usa el endpoint /admin/limpiar-datos o un cron job externo
if os.getenv('FLASK_ENV', 'development') == 'development':
    try:
        eventos_eliminados, tareas_eliminadas = limpiar_datos_antiguos(dias=3)
        if eventos_eliminados > 0 or tareas_eliminadas > 0:
            print(f"[LIMPIEZA AUTOMÁTICA] Se eliminaron {eventos_eliminados} eventos y {tareas_eliminadas} tareas antiguas (más de 3 días)")
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar la limpieza automática: {e}")


# ------------------ HELPER FUNCTIONS ------------------

def time_to_str(val):
    """
    Convierte un valor de tiempo (string, datetime.time, o timedelta) a formato 'HH:MM'
    MySQL devuelve timedelta para campos TIME
    """
    if not val:
        return ''
    # string like 'HH:MM:SS' or 'HH:MM'
    if isinstance(val, str):
        return val[:5]
    # datetime.time
    if isinstance(val, time):
        return val.strftime('%H:%M')
    # timedelta -> convert to HH:MM
    if hasattr(val, 'total_seconds'):
        total = int(val.total_seconds())
        hours = (total // 3600) % 24
        minutes = (total % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    return str(val)[:5]


# ------------------ AUTORIZACIÓN (decorador) ------------------
def login_required(f):
    """Decorador para rutas que requieren sesión iniciada.

    Actualmente se deja disponible; las rutas contienen la línea
    `# @login_required  TODO: activar login_required` comentada para
    que el equipo pueda activarla rápidamente cuando lo desee.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        usuario = session.get('usuario')
        token = session.get('session_token')
        if not usuario or not token:
            session.clear()
            flash('Sesión expirada. Por favor inicia sesión nuevamente.', 'error')
            return redirect(url_for('login'))
        
        data = ACTIVE_USER_SESSIONS.get(usuario)
        
        # Validar que exista y coincida token
        if not data or data.get('token') != token:
            # Sesión inválida (otro dispositivo inició sesión o limpiada por inactividad)
            session.clear()
            flash('Tu sesión ha sido invalidada. Puede que hayas iniciado sesión en otro dispositivo.', 'error')
            return redirect(url_for('login'))
        
        # Verificar si la sesión ha expirado por inactividad
        last_active = data.get('last_active')
        if not last_active:
            session.clear()
            ACTIVE_USER_SESSIONS.pop(usuario, None)
            flash('Sesión expirada. Por favor inicia sesión nuevamente.', 'error')
            return redirect(url_for('login'))
        
        now = datetime.utcnow()
        inactive_time = now - last_active
        
        if inactive_time > timedelta(minutes=SESSION_TTL_MINUTES):
            # Sesión expirada por inactividad
            session.clear()
            ACTIVE_USER_SESSIONS.pop(usuario, None)
            flash(f'Tu sesión expiró por inactividad ({SESSION_TTL_MINUTES} minutos). Por favor inicia sesión nuevamente.', 'error')
            return redirect(url_for('login'))
        
        # Actualizar last_active
        data['last_active'] = now
        return f(*args, **kwargs)
    return decorated_function


# ------------------ RUTAS PÚBLICAS BÁSICAS ------------------


@app.route('/')
def home():
    """Redirige a la página de login por defecto."""
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja formulario de login y crea la sesión del usuario."""
    # Si ya hay sesión activa válida, ir directo al dashboard
    usuario = session.get('usuario')
    token = session.get('session_token')
    if usuario and token:
        data = ACTIVE_USER_SESSIONS.get(usuario)
        if data and data.get('token') == token:
            # Sesión válida, redirigir a dashboard
            return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        usuario = sanitizar_texto(request.form.get('usuario', ''))
        password = request.form.get('password', '')
        force_login = request.form.get('force_login') == 'true'
        
        # Validaciones básicas login
        errors = []
        if not validar_no_vacio(usuario) or not validar_no_vacio(password):
            errors.append('Usuario y contraseña requeridos')
        if not validar_longitud(usuario, 50, 3):
            errors.append('Usuario debe tener entre 3 y 50 caracteres')
        if errors:
            return render_template('login.html', errors=errors)
        
        # PASO 1: Limpiar sesiones expiradas globalmente
        cleanup_expired_sessions()
        
        # PASO 2: Bloqueo si ya está activo en otro dispositivo y sesión no expirada
        existing = ACTIVE_USER_SESSIONS.get(usuario)
        if existing and not force_login:
            # Comprobar expiración por inactividad (doble verificación)
            last_active = existing.get('last_active')
            if last_active:
                inactive_time = datetime.utcnow() - last_active
                
                # Si la sesión está activa (no expirada)
                if inactive_time < timedelta(minutes=SESSION_TTL_MINUTES):
                    minutes_remaining = SESSION_TTL_MINUTES - int(inactive_time.total_seconds() / 60)
                    return render_template(
                        'login.html',
                        errors=[f'Ya hay una sesión activa para este usuario (expira en ~{minutes_remaining} min). Si eres tú y no puedes acceder desde el otro dispositivo, usa "Forzar inicio de sesión" abajo.'],
                        show_force_login=True,
                        usuario_bloqueado=usuario
                    )
            
            # Si llegamos aquí, la sesión ya expiró -> limpiarla
            ACTIVE_USER_SESSIONS.pop(usuario, None)
        
        # PASO 3: Si force_login=true, cerrar sesión anterior forzadamente
        if force_login and existing:
            print(f"[FORCE LOGIN] Usuario '{usuario}' forzó cierre de sesión anterior")
            ACTIVE_USER_SESSIONS.pop(usuario, None)

        # PASO 4: Verificar credenciales
        if verificar_usuario(usuario, password):
            # Obtener información del usuario incluyendo rol
            user = obtener_usuario_por_nombre(usuario)
            session['usuario'] = usuario
            session['user_rol'] = user.get('rol', 1) if user else 1
            # Generar token único y registrar
            token = secrets.token_urlsafe(16)
            session['session_token'] = token
            ACTIVE_USER_SESSIONS[usuario] = {
                'token': token,
                'last_active': datetime.utcnow()
            }
            print(f"[LOGIN] Usuario '{usuario}' inició sesión exitosamente (token: {token[:8]}...)")
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', errors=['Credenciales inválidas'])
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Cierra la sesión del usuario."""
    usuario = session.get('usuario')
    if usuario:
        if usuario in ACTIVE_USER_SESSIONS:
            ACTIVE_USER_SESSIONS.pop(usuario, None)
            print(f"[LOGOUT] Usuario '{usuario}' cerró sesión correctamente")
    
    # Limpiar completamente la sesión
    session.clear()
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registro sencillo de usuario con rol por defecto 1.

    Validaciones: nombre y contraseña requeridos, longitudes mínimas,
    usuario no existente previamente. Tras registrar redirige a login.
    """
    if request.method == 'POST':
        import re
        usuario = sanitizar_texto(request.form.get('usuario', ''))
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        # Reglas contraseña: min 8, al menos una mayúscula, una minúscula y un número, sin símbolos
        patron_password = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$'

        # Validaciones básicas
        errors = []
        if not validar_no_vacio(usuario) or not validar_no_vacio(password):
            errors.append('Usuario y contraseña son obligatorios')
        if not validar_longitud(usuario, 50, 3):
            errors.append('El usuario debe tener entre 3 y 50 caracteres')
        if not re.match(r'^[a-zA-Z0-9]+$', usuario):
            errors.append('El usuario solo puede contener letras y números')
        if usuario != 'admin' and not re.match(patron_password, password):
            errors.append('La contraseña debe tener mínimo 8 caracteres, incluir mayúscula, minúscula y número')
        if password != confirm:
            errors.append('Las contraseñas no coinciden')
        if errors:
            return render_template('register.html', errors=errors)

        # Usuario existente
        existente = obtener_usuario_por_nombre(usuario)
        if existente:
            return render_template('register.html', errors=['El usuario ya existe'])

        try:
            registrar_usuario(usuario, password, 1)
        except ValueError as e:
            return render_template('register.html', errors=[str(e)])
        except Exception:
            return render_template('register.html', errors=['Error interno registrando usuario'])

        flash('Registro exitoso. Ahora puedes iniciar sesión', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ----------------- DASHBOARD -----------------

@app.route('/dashboard')
@login_required
def dashboard():
    """Vista principal que resume eventos y tareas para el usuario.

    - Filtra eventos del día actual para mostrarlos en el dashboard.
    - Muestra tareas de toda la semana actual.
    - Recupera métricas semanales y eventos de mañana.
    """
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    eventos_data = obtener_eventos(usuario_id)
    tareas_data = obtener_tareas(usuario_id)
    completadas_semana, total_semana = obtener_resumen_semana(usuario_id)  # Filtrado por usuario
    eventos_manana = obtener_eventos_manana(usuario_id)  # Filtrado por usuario
    fecha_hoy = datetime.now().date()
    
    # Calcular inicio y fin de la semana actual
    inicio_semana = fecha_hoy - timedelta(days=fecha_hoy.weekday())  # Lunes
    fin_semana = inicio_semana + timedelta(days=6)  # Domingo

    # Usar funciones de filtrado para hoy
    eventos_hoy = filtrar_eventos_por_fecha(eventos_data, fecha_hoy)

    # NUEVO: Filtrar todos los eventos de la semana (lunes-domingo)
    eventos_semana = []
    for e in eventos_data:
        fecha_str = e.get('fecha_evento') or e.get('fecha_limite')  # por si estructura distinta
        if not fecha_str:
            continue
        try:
            fecha_e = datetime.strptime(str(fecha_str), '%Y-%m-%d').date()
        except Exception:
            continue
        if inicio_semana <= fecha_e <= fin_semana:
            eventos_semana.append(e)

    # Ordenar eventos de la semana por fecha y hora
    def _clave_orden(ev):
        f = ev.get('fecha_evento') or ev.get('fecha_limite') or '2099-12-31'
        h = ev.get('hora_evento') or ev.get('hora_fin') or '23:59'
        return (f, h)
    eventos_semana = sorted(eventos_semana, key=_clave_orden)

    # Etiquetas humanizadas para las fechas de la semana
    hoy = fecha_hoy
    manana = hoy + timedelta(days=1)
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    for ev in eventos_semana:
        fecha_str = ev.get('fecha_evento') or ev.get('fecha_limite')
        try:
            f = datetime.strptime(str(fecha_str), '%Y-%m-%d').date()
        except Exception:
            ev['label_fecha'] = fecha_str
            continue
        if f == hoy:
            ev['label_fecha'] = 'Hoy'
        elif f == manana:
            ev['label_fecha'] = 'Mañana'
        else:
            ev['label_fecha'] = nombres_dias[f.weekday()]

    # Filtrar tareas de toda la semana (ya existente)
    tareas_semana = [
        t for t in tareas_data
        if t.get('fecha_limite') and inicio_semana <= t.get('fecha_limite') <= fin_semana
    ]

    return render_template(
        'dashboard.html',
        eventos_hoy=eventos_hoy[:5],
        tareas_hoy=tareas_semana,  # Tareas de la semana
        eventos_semana=eventos_semana,  # NUEVO: todos los eventos de la semana
        completadas_semana=completadas_semana,
        total_semana=total_semana,
        eventos_manana=eventos_manana,
    )


# ----------------- CALENDARIO ----------------


# ------------------ EVENTOS ------------------

# Ver todos los eventos
@app.route('/eventos')
@login_required
def ver_eventos():
    """Lista todos los eventos.

    Plantilla: `eventos.html` espera una lista de eventos.
    """
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    eventos = obtener_eventos(usuario_id)
    return render_template('eventos.html', eventos=eventos)


# Crear nuevo evento
@app.route('/eventos/nuevo', methods=['GET', 'POST'])
@login_required
def crear_evento_view():
    """Formulario para crear eventos. Si es POST crea el evento y redirige.

    Soporta fecha y hora de inicio; fecha/hora de fin son opcionales.
    """
    # Capturar de dónde viene (referer)
    referer = request.args.get('referer', 'dashboard')
    
    if request.method == 'POST':
        # VALIDAR DATOS DEL FORMULARIO
        nombre = sanitizar_texto(request.form.get('nombre', ''))
        fecha_evento = request.form.get('fecha_evento', '').strip()
        hora_evento_raw = request.form.get('hora_evento', '').strip()
        # Tratar hora vacía como evento all-day -> '00:00'
        hora_evento = (hora_evento_raw or '00:00')[:5]
        descripcion = sanitizar_texto(request.form.get('descripcion', ''))
        fecha_fin = request.form.get('fecha_fin', '').strip() or None
        hora_fin = request.form.get('hora_fin', '').strip() or None
        referer_form = request.form.get('referer', 'dashboard')

        # Validar no vacío y longitud
        errors = []
        if not validar_no_vacio(nombre):
            errors.append('El nombre no puede estar vacío')
        if not validar_longitud(nombre, 100, 3):
            errors.append('Longitud de nombre inválida (3-100)')
        if not validar_texto_seguro(nombre, 100, required=True):
            errors.append('Nombre inválido o demasiado largo')
        if not validar_fecha_no_pasada(fecha_evento):
            errors.append('La fecha del evento no puede ser en el pasado')
        if hora_evento_raw and not validar_fecha_hora_no_pasada(fecha_evento, hora_evento):
            errors.append('No se puede crear un evento con fecha y hora pasadas')
        if hora_fin and not validar_rango_horas(hora_evento[:5], hora_fin[:5]):
            errors.append('La hora fin debe ser posterior a la hora inicio')
        if fecha_fin and not validar_fecha_no_pasada(fecha_fin):
            errors.append('La fecha fin no puede ser en el pasado')
        if errors:
            return render_template('nuevo_evento.html', errors=errors, fecha_preseleccionada=fecha_evento, referer=referer_form)

        usuario_actual = session.get('usuario')
        user = obtener_usuario_por_nombre(usuario_actual)
        creador_id = user['id'] if user else 1

        try:
            crear_evento(
                nombre=nombre,
                fecha_evento=fecha_evento,
                hora_evento=hora_evento,
                creador_id=creador_id,
                fecha_fin=fecha_fin,
                hora_fin=hora_fin,
                descripcion=descripcion or None
            )
            # Redirigir según el origen
            if referer_form == 'eventos':
                return redirect(url_for('ver_eventos'))
            elif referer_form == 'calendar':
                return redirect(url_for('calendar'))
            else:
                return redirect(url_for('dashboard'))
        except ValueError as e:
            return render_template('nuevo_evento.html', errors=[str(e)], fecha_preseleccionada=fecha_evento, referer=referer_form)

    # Capturar fecha preseleccionada si viene desde FullCalendar
    fecha_preseleccionada = request.args.get('fecha', '')
    return render_template('nuevo_evento.html', fecha_preseleccionada=fecha_preseleccionada, referer=referer)


# Editar evento (página completa eliminada; se usa modal en UI)
@app.route('/eventos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_evento_view(id):
    return redirect(url_for('ver_eventos'))


# Ver evento (modal fragment)
@app.route('/eventos/<int:id>/ver')
@login_required
def ver_evento_view(id):
    """Devuelve un fragmento modal con los datos normalizados del evento."""
    evento_data = next((e for e in obtener_eventos() if e.get('id') == id), None)
    if not evento_data:
        return ("Evento no encontrado", 404)

    evento = Evento(evento_data)
    evento_display = evento.to_dict()

    return render_template('modal_fragment.html', item=evento_display, tipo='evento')


# Eliminar evento
@app.route('/eventos/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_evento_view(id):
    """Elimina un evento y redirige a la lista de eventos."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    es_admin = user and user.get('rol', 1) == 3
    evento = next((e for e in obtener_eventos() if e.get('id') == id), None)
    if not evento:
        return "Evento no encontrado", 404
    if not es_admin and evento.get('creador_evento') != usuario_id:
        return "No tienes permiso para eliminar este evento", 403
    # from db import registrar_auditoria  # DESHABILITADO - tabla no existe
    eliminar_evento(id)
    # registrar_auditoria(usuario_actual, 'eliminar', 'evento', id)  # DESHABILITADO
    return redirect(url_for('ver_eventos'))


# ------------------ TAREAS (Vistas y API) ------------------


@app.route('/tareas')
@login_required
def ver_tareas():
    """Lista de tareas."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    tareas = obtener_tareas(usuario_id)
    return render_template('tareas.html', tareas=tareas)


@app.route('/tareas/nueva', methods=['GET', 'POST'])
@login_required
def crear_tarea_view():
    """Crear nueva tarea desde formulario."""
    # Capturar de dónde viene (referer)
    referer = request.args.get('referer', 'dashboard')
    
    if request.method == 'POST':
        # Sanitizar y extraer datos
        nombre = sanitizar_texto(request.form.get('nombre', ''))
        descripcion = sanitizar_texto(request.form.get('descripcion', ''))
        fecha_limite = request.form.get('fecha_limite', '').strip()
        hora_evento = request.form.get('hora_evento', '').strip() or None
        prioridad = request.form.get('prioridad', '').strip()
        referer_form = request.form.get('referer', 'dashboard')

        # Validaciones básicas
        errors = []
        if not validar_no_vacio(nombre):
            errors.append('El nombre no puede estar vacío')
        if not validar_longitud(nombre, 100, 3):
            errors.append('Longitud de nombre inválida (3-100)')
        if not validar_fecha_formato(fecha_limite):
            errors.append('Fecha límite inválida')
        if not validar_fecha_no_pasada(fecha_limite):
            errors.append('La fecha límite no puede ser pasada')
        if not validar_prioridad(prioridad):
            errors.append('Prioridad inválida (debe ser 1, 2 o 3)')
        if descripcion and not validar_longitud(descripcion, 500, 0):
            errors.append('Descripción demasiado larga (máx 500)')
        if errors:
            return render_template('nueva_tarea.html', errors=errors, referer=referer_form)

        usuario_actual = session.get('usuario')
        user = obtener_usuario_por_nombre(usuario_actual)
        creador_id = user['id'] if user else 1

        try:
            crear_tarea(
                nombre=nombre,
                descripcion=descripcion or '',
                fecha_limite=fecha_limite,
                prioridad=int(prioridad),
                creador_id=creador_id,
                estado=0,  # Por defecto
                hora_evento=hora_evento
            )
            # Redirigir según el origen
            if referer_form == 'tareas':
                return redirect(url_for('ver_tareas'))
            elif referer_form == 'calendar':
                return redirect(url_for('calendar'))
            else:
                return redirect(url_for('dashboard'))
        except ValueError as e:
            return render_template('nueva_tarea.html', errors=[str(e)], referer=referer_form)

    return render_template('nueva_tarea.html', referer=referer)


@app.route('/tareas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_tarea_view(id):
    return redirect(url_for('ver_tareas'))


@app.route('/tareas/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_tarea_view(id):
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    es_admin = user and user.get('rol', 1) == 3
    tarea = next((t for t in obtener_tareas() if t.get('id') == id), None)
    if not tarea:
        return "Tarea no encontrada", 404
    if not es_admin and tarea.get('creador_tarea') != usuario_id:
        return "No tienes permiso para eliminar esta tarea", 403
    # from db import registrar_auditoria  # DESHABILITADO - tabla no existe
    eliminar_tarea(id)
    # registrar_auditoria(usuario_actual, 'eliminar', 'tarea', id)  # DESHABILITADO
    return redirect(url_for('ver_tareas'))


@app.route('/tareas/<int:id>/ver')
@login_required
def ver_tarea_view(id):
    """Fragmento/modal para ver detalles de una tarea (normaliza campos)."""
    tarea_data = next((t for t in obtener_tareas() if t.get('id') == id), None)
    if not tarea_data:
        return ("Tarea no encontrada", 404)
    
    tarea = Tarea(tarea_data)
    tarea_display = tarea.to_modal_dict()

    return render_template('ver_tarea.html', tarea=tarea_display)


# API para cambiar estado con checkbox (AJAX)
@app.route('/tareas/<int:id>/estado', methods=['POST'])
@login_required
def actualizar_estado_tarea_view(id):
    data = request.get_json()
    estado = int(data.get('estado', 0))  # Espera 0 o 1

    try:
        actualizar_estado_tarea(id, estado)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------ API JSON EVENTOS ------------------

@app.route('/api/eventos')
@login_required
def api_eventos():
    """Devuelve eventos y tareas para FullCalendar.

    Ahora incluye también las tareas como pequeños puntos en la vista mensual
    y con detalle normal en vistas de semana/día. Las tareas se distinguen por
    la clase CSS `tarea-evento` y usan un prefijo en el ID para evitar colisiones.
    """
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    # Optimización: usar rango solicitado por FullCalendar para limitar datos
    start_param = request.args.get('start')  # formato ISO con timezone
    end_param = request.args.get('end')
    # Extraer solo la parte de fecha (YYYY-MM-DD)
    def extraer_fecha(raw):
        if not raw:
            return None
        return raw.split('T')[0][:10]
    start_date = extraer_fecha(start_param)
    end_date = extraer_fecha(end_param)

    eventos_data = obtener_eventos(usuario_id)
    tareas_data = obtener_tareas(usuario_id)

    # Filtrar por rango si ambos extremos son válidos
    from utils import validar_fecha_formato
    if start_date and end_date and validar_fecha_formato(start_date) and validar_fecha_formato(end_date):
        try:
            from datetime import datetime
            sd = datetime.strptime(start_date, '%Y-%m-%d').date()
            ed = datetime.strptime(end_date, '%Y-%m-%d').date()
            eventos_data = [e for e in eventos_data if e.get('fecha_evento') and sd <= (e.get('fecha_evento') if not isinstance(e.get('fecha_evento'), str) else datetime.strptime(e.get('fecha_evento'), '%Y-%m-%d').date()) <= ed]
            tareas_data = [t for t in tareas_data if t.get('fecha_limite') and sd <= (t.get('fecha_limite') if not isinstance(t.get('fecha_limite'), str) else datetime.strptime(t.get('fecha_limite'), '%Y-%m-%d').date()) <= ed]
        except Exception:
            pass

    eventos_json = []
    for e_data in eventos_data:
        evento = Evento(e_data)
        eventos_json.append(evento.to_fullcalendar())

    # Añadir tareas al calendario
    for t in tareas_data:
        try:
            fecha = t.get('fecha_limite') or t.get('fecha_evento')
            if not fecha:
                continue
            
            # Convertir fecha a string si no lo es
            if not isinstance(fecha, str):
                fecha = str(fecha)
            
            hora = t.get('hora_evento')
            
            # Normalizar hora (puede ser timedelta, time, o string)
            hora_normalizada = None
            if hora:
                if isinstance(hora, str):
                    hora_normalizada = hora[:5] if len(hora) >= 5 else hora
                elif hasattr(hora, 'total_seconds'):  # timedelta
                    total = int(hora.total_seconds())
                    hours = (total // 3600) % 24
                    minutes = (total % 3600) // 60
                    hora_normalizada = f"{hours:02d}:{minutes:02d}"
                elif hasattr(hora, 'strftime'):  # time object
                    hora_normalizada = hora.strftime('%H:%M')
            
            # Si tiene hora, formatear como datetime; si no, marcar como allDay
            if hora_normalizada:
                start_datetime = f"{fecha}T{hora_normalizada}"
                all_day = False
            else:
                start_datetime = fecha
                all_day = True
            
            eventos_json.append({
                'id': f"t-{t.get('id')}",
                'title': t.get('nombre'),
                'start': start_datetime,
                'allDay': all_day,
                'classNames': ['tarea-evento'],
                'extendedProps': {
                    'esTarea': True,
                    'prioridad': t.get('prioridad'),
                    'estado': t.get('estado'),
                    'descripcion': t.get('descripcion') or ''
                }
            })
        except Exception:
            continue

    return jsonify(eventos_json)


@app.route('/api/eventos-semana-count', methods=['GET'])
@login_required
def obtener_eventos_semana_count():
    """API para obtener el conteo de eventos de la semana actual sin recargar."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    
    try:
        from db import obtener_eventos_semana
        count = obtener_eventos_semana(usuario_id)
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/eventos/<int:evento_id>', methods=['PUT'])
@login_required
def actualizar_evento_api(evento_id):
    # from db import registrar_auditoria  # DESHABILITADO - tabla no existe
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    es_admin = user and user.get('rol', 1) == 3
    evento = next((e for e in obtener_eventos() if e.get('id') == evento_id), None)
    if not evento:
        return jsonify({"error": "Evento no encontrado"}), 404
    if not es_admin and evento.get('creador_evento') != usuario_id:
        return jsonify({"error": "No tienes permiso para editar este evento"}), 403
    """API para actualizar evento desde cliente (JSON PUT).

    Valida fechas básicas y llama a modificar_evento.
    """
    data = request.get_json()
    
    # Validar que el JSON existe
    if not data:
        return jsonify({"error": "Datos inválidos"}), 400
    
    # Validar campos
    nombre = sanitizar_texto(data.get("nombre", ""))
    if not validar_texto_seguro(nombre, 100, required=True):
        return jsonify({"error": "Nombre inválido"}), 400

    if not data.get("fecha_evento"):
        return jsonify({"error": "Falta fecha de evento"}), 400

    descripcion = sanitizar_texto(data.get("descripcion", ""))
    fecha_inicio = data["fecha_evento"].strip()
    # Normalizar hora de inicio: si viene vacía -> considerar evento "all-day" y usar 00:00
    hora_inicio_raw = data.get("hora_evento")
    hora_inicio = (hora_inicio_raw or "00:00").strip()[:5]
    
    # Validar formatos
    if not validar_fecha_formato(fecha_inicio):
        return jsonify({"error": "Formato de fecha inválido"}), 400
    if not validar_fecha_no_pasada(fecha_inicio):
        return jsonify({"error": "Fecha de evento debe ser posterior a hoy"}), 400
    
    # Validar que la fecha y hora no sean del pasado
    if hora_inicio_raw and not validar_fecha_hora_no_pasada(fecha_inicio, hora_inicio):
        return jsonify({"error": "No se puede crear un evento con fecha y hora pasadas"}), 400
    
    # Validar formato sólo si la hora existe (siempre existirá tras normalización). Si se quiere permitir all-day sin hora,
    # se podría omitir esta validación cuando hora_inicio == '00:00' y fecha_fin/hora_fin son None.
    if hora_inicio and not validar_hora_formato(hora_inicio):
        return jsonify({"error": "Hora de evento inválida"}), 400
    
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        return jsonify({"error": "Descripción inválida"}), 400
    
    # Limpiar valores opcionales
    fecha_fin = limpiar_valor_opcional(data.get("fecha_fin"))
    hora_fin_raw = limpiar_valor_opcional(data.get("hora_fin"))
    # Tratar hora fin vacía como None
    hora_fin = hora_fin_raw[:5] if hora_fin_raw else None
    # Validar rango de horas si ambas existen
    if hora_fin and not validar_rango_horas(hora_inicio, hora_fin):
        return jsonify({"error": "La hora fin debe ser posterior a la hora inicio"}), 400
    
    # Validar opcionales si existen
    if fecha_fin and not validar_fecha_formato(fecha_fin):
        return jsonify({"error": "Formato de fecha fin inválido"}), 400
    if fecha_fin and not validar_fecha_no_pasada(fecha_fin):
        return jsonify({"error": "Fecha de fin debe ser posterior a hoy"}), 400
    
    if hora_fin and not validar_hora_formato(hora_fin):
        return jsonify({"error": "Formato de hora fin inválido"}), 400
    
    # Si hay fecha_fin pero no hora_fin, usar hora de inicio
    if fecha_fin and not hora_fin:
        hora_fin = hora_inicio

    # Validación de fechas
    if not validar_fechas(fecha_inicio, fecha_fin):
        return jsonify({"error": "Fecha de fin debe ser posterior a fecha de inicio"}), 400

    try:
        modificar_evento(
            evento_id,
            nombre,
            fecha_inicio,
            hora_inicio,
            fecha_fin,
            hora_fin,
            descripcion or None
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    eventos_data = obtener_eventos(usuario_id)
    evento_data = next((e for e in eventos_data if e.get('id') == evento_id), None)
    if not evento_data:
        return jsonify({'error': 'Evento actualizado pero no encontrado'}), 500

    evento = Evento(evento_data)
    return jsonify(evento.to_dict()), 200


@app.route('/api/eventos', methods=['POST'])
@login_required
def crear_evento_api():
    """API para crear evento rápido desde el calendario (JSON POST).

    Espera en el body JSON: nombre, fecha_evento, hora_evento opcional,
    fecha_fin/hora_fin opcionales, descripcion opcional.
    Devuelve el evento creado en formato FullCalendar para inyección directa.
    """
    data = request.get_json()
    print(f"[DEBUG] crear_evento_api raw data: {data}")
    if not data:
        return jsonify({'error': 'JSON inválido'}), 400

    nombre = sanitizar_texto(data.get('nombre', ''))
    descripcion = sanitizar_texto(data.get('descripcion', '')) or None
    fecha_evento = (data.get('fecha_evento') or '').strip()
    hora_evento = (data.get('hora_evento') or '00:00')[:5]
    fecha_fin = limpiar_valor_opcional(data.get('fecha_fin'))
    hora_fin = limpiar_valor_opcional(data.get('hora_fin'))
    if hora_fin:
        hora_fin = hora_fin[:5]

    # Validaciones básicas
    if not validar_texto_seguro(nombre, 100, required=True):
        print("[DEBUG] Nombre inválido", nombre)
        return jsonify({'error': 'Nombre inválido'}), 400
    if not validar_fecha_formato(fecha_evento):
        print("[DEBUG] Fecha inválida", fecha_evento)
        return jsonify({'error': 'Fecha inválida'}), 400
    if not validar_fecha_no_pasada(fecha_evento):
        print("[DEBUG] Fecha pasada", fecha_evento)
        return jsonify({'error': 'Fecha debe ser hoy o futura'}), 400
    # Validar que la fecha y hora no sean del pasado
    if data.get('hora_evento') and not validar_fecha_hora_no_pasada(fecha_evento, hora_evento):
        print("[DEBUG] Fecha y hora pasadas", fecha_evento, hora_evento)
        return jsonify({'error': 'No se puede crear un evento con fecha y hora pasadas'}), 400
    if hora_evento and not validar_hora_formato(hora_evento):
        print("[DEBUG] Hora inválida", hora_evento)
        return jsonify({'error': 'Hora inválida'}), 400
    if fecha_fin and not validar_fecha_formato(fecha_fin):
        print("[DEBUG] Fecha fin inválida", fecha_fin)
        return jsonify({'error': 'Fecha fin inválida'}), 400
    if fecha_fin and not validar_fechas(fecha_evento, fecha_fin):
        print("[DEBUG] Rango fecha inválido", fecha_evento, fecha_fin)
        return jsonify({'error': 'Fecha fin debe ser posterior a inicio'}), 400
    if hora_fin and not validar_hora_formato(hora_fin):
        print("[DEBUG] Hora fin inválida", hora_fin)
        return jsonify({'error': 'Hora fin inválida'}), 400
    if hora_fin and not validar_rango_horas(hora_evento, hora_fin):
        print("[DEBUG] Rango hora inválido", hora_evento, hora_fin)
        return jsonify({'error': 'Hora fin debe ser posterior a hora inicio'}), 400
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        print("[DEBUG] Descripción inválida", descripcion)
        return jsonify({'error': 'Descripción inválida'}), 400

    # Obtener usuario
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    creador_id = user['id'] if user else 1

    try:
        crear_evento(
            nombre=nombre,
            fecha_evento=fecha_evento,
            hora_evento=hora_evento,  # Ya está en formato HH:MM
            creador_id=creador_id,
            fecha_fin=fecha_fin,
            hora_fin=hora_fin,  # Ya está en formato HH:MM
            descripcion=descripcion or None
        )
    except ValueError as e:
        print(f"[DEBUG] ValueError creando evento: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as ex:
        print(f"[DEBUG] Exception creando evento: {ex}")
        return jsonify({'error': 'Error interno creando evento'}), 500

    # Recuperar el evento recién creado (tomar el último por fecha/hora y nombre)
    eventos_data = obtener_eventos()
    # Recuperar evento recién creado usando SOLO claves minúsculas
    creado = next((e for e in reversed(eventos_data) if e.get('nombre') == nombre and str(e.get('fecha_evento')) == fecha_evento), None)
    if not creado:
        return jsonify({'error': 'Evento creado pero no localizado'}), 500

    evento_obj = Evento(creado)
    return jsonify(evento_obj.to_fullcalendar()), 201


@app.route('/api/tareas/<int:tarea_id>', methods=['PUT'])
@login_required
def actualizar_tarea_api(tarea_id):
    # from db import registrar_auditoria  # DESHABILITADO - tabla no existe
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    es_admin = user and user.get('rol', 1) == 3
    tarea = next((t for t in obtener_tareas() if t.get('id') == tarea_id), None)
    if not tarea:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    if not es_admin and tarea.get('creador_tarea') != usuario_id:
        return jsonify({'error': 'No tienes permiso para editar esta tarea'}), 403
    """API para actualizar una tarea vía JSON (PUT)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON inválido'}), 400

    # Extraer y normalizar campos
    nombre = sanitizar_texto(data.get('nombre', ''))
    descripcion = sanitizar_texto(data.get('descripcion', ''))
    fecha_limite = (data.get('fecha_evento') or data.get('fecha_limite') or '').strip()
    hora_evento_raw = (data.get('hora_evento') or '').strip()
    # Normalizar hora a HH:MM si viene con segundos HH:MM:SS
    if hora_evento_raw and len(hora_evento_raw) == 8 and hora_evento_raw.count(':') == 2:
        hora_evento = hora_evento_raw[:5]
    else:
        hora_evento = hora_evento_raw or None
    prioridad_raw = data.get('prioridad', 1)
    estado_raw = data.get('estado')

    # Ajuste: si viene '00:00' desde un drag de un evento allDay y la tarea original NO tenía hora, lo tratamos como None
    if hora_evento == '00:00' and not tarea.get('hora_evento'):
        hora_evento = None

    # Validar nombre
    if not validar_no_vacio(nombre):
        return jsonify({'error': 'Nombre vacío'}), 400
    if not validar_longitud(nombre, 100, 3):
        return jsonify({'error': 'Nombre demasiado corto (mínimo 3) o largo (máximo 100)'}), 400

    # Validar fecha
    if not validar_fecha_formato(fecha_limite):
        return jsonify({'error': 'Fecha límite inválida'}), 400
    # Relajamos la validación para permitir mover tareas a días pasados vía drag & drop
    # (Se mantiene sólo el formato correcto y se deja decisión de negocio a otra capa si hiciera falta)


    # Validar prioridad
    try:
        prioridad = int(prioridad_raw)
    except (ValueError, TypeError):
        return jsonify({'error': 'Prioridad inválida'}), 400
    if not validar_prioridad(prioridad):
        return jsonify({'error': 'Prioridad inválida (1,2,3)'}), 400

    # Validar estado
    if estado_raw is None:
        estado = 0
    else:
        try:
            estado = int(estado_raw)
        except Exception:
            estado = 1 if str(estado_raw).lower().startswith('c') else 0
    if not validar_estado(estado):
        return jsonify({'error': 'Estado inválido (0 o 1)'}), 400

    # Validar descripción opcional
    if descripcion and not validar_longitud(descripcion, 500, 0):
        return jsonify({'error': 'Descripción demasiado larga (máx 500)'}), 400

    # DEBUG: Log de entrada
    print(f"[DEBUG] PUT /api/tareas/{tarea_id} payload={{'nombre': '{nombre}', 'fecha_limite': '{fecha_limite}', 'hora_evento': '{hora_evento}', 'prioridad': {prioridad}, 'estado': {estado}}}")
    try:
        modificar_tarea(tarea_id, nombre, descripcion or '', fecha_limite, prioridad, estado, hora_evento)
        print(f"[DEBUG] Tarea {tarea_id} modificada correctamente")
    except ValueError as e:
        print(f"[DEBUG] ValueError modificando tarea {tarea_id}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"[DEBUG] Exception modificando tarea {tarea_id}: {e}")
        return jsonify({'error': 'Error interno'}), 500

    # Obtener tarea actualizada
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    tareas_data = obtener_tareas(usuario_id)
    tarea_data = next((t for t in tareas_data if t.get('id') == tarea_id), None)
    if not tarea_data:
        return jsonify({'error': 'Tarea actualizada pero no encontrada'}), 500

    tarea = Tarea(tarea_data)
    return jsonify(tarea.to_dict()), 200


# ------------------ (Eliminado) Ruta ajustes_admin unificada en ajustes_usuario ------------------

def _build_admin_data():
    """Helper para construir datos administrativos si el usuario es admin."""
    from db import obtener_usuarios, obtener_eventos, obtener_tareas
    usuarios = obtener_usuarios()
    eventos_raw = obtener_eventos()
    tareas_raw = obtener_tareas()
    usuarios_map = {u['id']: u['usuario'] for u in usuarios}
    for e in eventos_raw:
        e['creador_nombre'] = usuarios_map.get(e.get('creador_evento'), 'Desconocido')
    for t in tareas_raw:
        t['creador_nombre'] = usuarios_map.get(t.get('creador_tarea'), 'Desconocido')
    return {
        'usuarios': usuarios,
        'eventos': eventos_raw,
        'tareas': tareas_raw
    }


@app.route('/admin/limpiar-datos', methods=['POST'])
@login_required
def limpiar_datos_admin():
    """
    Endpoint administrativo para ejecutar la limpieza de datos antiguos manualmente.
    Solo accesible por administradores (rol==3).
    
    Puede ser llamado:
    - Manualmente desde un botón en la interfaz de administración
    - Por un cron job externo en producción
    - Por un scheduler como Heroku Scheduler
    """
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    
    # Solo admin (rol==3)
    if not user or user.get('rol', 1) != 3:
        flash('No tienes permisos de administrador', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Obtener días desde parámetro o usar 7 por defecto
        dias = int(request.form.get('dias', 7))
        if dias < 1 or dias > 365:
            flash('El número de días debe estar entre 1 y 365', 'error')
            return redirect(url_for('ajustes_usuario'))
        
        eventos_eliminados, tareas_eliminadas = limpiar_datos_antiguos(dias=dias)
        
        flash(f'Limpieza completada: {eventos_eliminados} eventos y {tareas_eliminadas} tareas eliminadas (>{dias} días)', 'success')
        return redirect(url_for('ajustes_usuario'))
    except Exception as e:
        flash(f'Error al limpiar datos: {str(e)}', 'error')
        return redirect(url_for('ajustes_usuario'))


@app.route('/admin/eliminar-usuario', methods=['POST'])
@login_required
def eliminar_usuario_admin():
    """Eliminar un usuario (solo admin)."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    
    if not user or user.get('rol', 1) != 3:
        flash('No tienes permisos de administrador', 'error')
        return redirect(url_for('dashboard'))
    
    usuario_id = request.form.get('usuario_id')
    if not usuario_id:
        flash('ID de usuario no proporcionado', 'error')
        return redirect(url_for('ajustes_admin'))
    
    try:
        from db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Verificar que no sea admin (tabla real: usuario)
        cursor.execute("SELECT rol FROM usuario WHERE id = %s", (usuario_id,))
        result = cursor.fetchone()
        if result and result[0] == 3:
            flash('No puedes eliminar a otro administrador', 'error')
            cursor.close(); conn.close()
            return redirect(url_for('ajustes_usuario'))

        # Eliminar eventos y tareas del usuario primero (columnas reales: creador_evento / creador_tarea)
        cursor.execute("DELETE FROM eventos WHERE creador_evento = %s", (usuario_id,))
        cursor.execute("DELETE FROM tareas WHERE creador_tarea = %s", (usuario_id,))

        # Eliminar usuario (tabla real: usuario)
        cursor.execute("DELETE FROM usuario WHERE id = %s", (usuario_id,))
        conn.commit()

        cursor.close()
        conn.close()

        flash('Usuario eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar usuario: {str(e)}', 'error')
    
    return redirect(url_for('ajustes_usuario'))


@app.route('/admin/eliminar-evento', methods=['POST'])
@login_required
def eliminar_evento_admin():
    """Eliminar un evento (solo admin)."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    
    if not user or user.get('rol', 1) != 3:
        flash('No tienes permisos de administrador', 'error')
        return redirect(url_for('dashboard'))
    
    evento_id = request.form.get('evento_id')
    if not evento_id:
        flash('ID de evento no proporcionado', 'error')
        return redirect(url_for('ajustes_usuario'))
    
    try:
        eliminar_evento(int(evento_id))
        flash('Evento eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar evento: {str(e)}', 'error')
    
    return redirect(url_for('ajustes_usuario'))


@app.route('/admin/eliminar-tarea', methods=['POST'])
@login_required
def eliminar_tarea_admin():
    """Eliminar una tarea (solo admin)."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    
    if not user or user.get('rol', 1) != 3:
        flash('No tienes permisos de administrador', 'error')
        return redirect(url_for('dashboard'))
    
    tarea_id = request.form.get('tarea_id')
    if not tarea_id:
        flash('ID de tarea no proporcionado', 'error')
        return redirect(url_for('ajustes_usuario'))
    
    try:
        eliminar_tarea(int(tarea_id))
        flash('Tarea eliminada correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar tarea: {str(e)}', 'error')
    
    return redirect(url_for('ajustes_usuario'))


@app.route('/admin/cerrar-sesion-usuario', methods=['POST'])
@login_required
def cerrar_sesion_usuario_admin():
    """Cerrar la sesión activa de un usuario específico (solo admin)."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    
    if not user or user.get('rol', 1) != 3:
        flash('No tienes permisos de administrador', 'error')
        return redirect(url_for('dashboard'))
    
    usuario_objetivo = request.form.get('usuario')
    if not usuario_objetivo:
        flash('Usuario no especificado', 'error')
        return redirect(url_for('ajustes_usuario'))
    
    if usuario_objetivo in ACTIVE_USER_SESSIONS:
        ACTIVE_USER_SESSIONS.pop(usuario_objetivo, None)
        flash(f'Sesión de "{usuario_objetivo}" cerrada correctamente', 'success')
        print(f"[ADMIN] {usuario_actual} cerró la sesión de {usuario_objetivo}")
    else:
        flash(f'El usuario "{usuario_objetivo}" no tiene sesión activa', 'error')
    
    return redirect(url_for('ajustes_usuario'))


# ------------------ AJUSTES DE USUARIO ------------------

@app.route('/ajustes-usuario', methods=['GET'])
@login_required
def ajustes_usuario():
    """Página de ajustes del usuario: cambiar nombre y contraseña. Si es admin, muestra también opciones de administración."""
    from db import obtener_usuarios, obtener_eventos, obtener_tareas
    
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    es_admin = user and user.get('rol', 1) == 3
    
    admin_data = _build_admin_data() if es_admin else {}
    
    # Si es admin, añadir info de sesiones activas
    if es_admin:
        sesiones_activas = []
        now = datetime.utcnow()
        for usuario, data in ACTIVE_USER_SESSIONS.items():
            last_active = data.get('last_active')
            if last_active:
                inactive_minutes = int((now - last_active).total_seconds() / 60)
                sesiones_activas.append({
                    'usuario': usuario,
                    'last_active': last_active.strftime('%Y-%m-%d %H:%M:%S'),
                    'inactive_minutes': inactive_minutes,
                    'token_preview': data.get('token', '')[:8] + '...'
                })
        admin_data['sesiones_activas'] = sesiones_activas
    
    return render_template('ajustes_usuario.html', es_admin=es_admin, admin_data=admin_data)


@app.route('/cambiar-nombre', methods=['POST'])
@login_required
def cambiar_nombre_usuario():
    """Cambiar el nombre de usuario actual."""
    from db import obtener_usuario_por_nombre
    import bcrypt
    
    usuario_actual = session.get('usuario')
    nuevo_nombre = request.form.get('nuevo_nombre', '').strip()
    password_confirmar = request.form.get('password_confirmar', '').strip()
    
    errors = []
    
    # Validaciones
    if not validar_no_vacio(nuevo_nombre):
        errors.append('El nuevo nombre no puede estar vacío')
    if not validar_longitud(nuevo_nombre, 50, 3):
        errors.append('El nombre debe tener entre 3 y 50 caracteres')
    if not validar_texto_seguro(nuevo_nombre, 50, required=True):
        errors.append('El nombre contiene caracteres no permitidos')
    
    # Verificar que el nuevo nombre no exista
    user_existente = obtener_usuario_por_nombre(nuevo_nombre)
    if user_existente and user_existente.get('usuario') != usuario_actual:
        errors.append('Este nombre de usuario ya está en uso')
    
    # Verificar contraseña actual
    user = obtener_usuario_por_nombre(usuario_actual)
    if not user:
        errors.append('Usuario no encontrado')
    else:
        password_hash = user.get('password')
        if not bcrypt.checkpw(password_confirmar.encode('utf-8'), password_hash.encode('utf-8')):
            errors.append('La contraseña actual es incorrecta')
    
    if errors:
        # Reconstruir contexto admin si aplica
        user = obtener_usuario_por_nombre(usuario_actual)
        es_admin = user and user.get('rol', 1) == 3
        admin_data = _build_admin_data() if es_admin else {}
        return render_template('ajustes_usuario.html', errors=errors, es_admin=es_admin, admin_data=admin_data)
    
    # Actualizar el nombre de usuario
    try:
        # Nota: necesitarías una función modificar_usuario en db.py
        # Por ahora voy a usar una consulta directa
        from db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuario SET usuario = %s WHERE usuario = %s", (nuevo_nombre, usuario_actual))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Actualizar la sesión
        session['usuario'] = nuevo_nombre
        # Mantener sesión activa moviendo el token al nuevo nombre
        token = session.get('session_token')
        if token:
            ACTIVE_USER_SESSIONS.pop(usuario_actual, None)
            ACTIVE_USER_SESSIONS[nuevo_nombre] = {
                'token': token,
                'last_active': datetime.utcnow()
            }
        # Re-armar contexto ajustes
        es_admin = user and user.get('rol', 1) == 3
        admin_data = _build_admin_data() if es_admin else {}
        return render_template('ajustes_usuario.html', success='Nombre de usuario actualizado correctamente', es_admin=es_admin, admin_data=admin_data)
    except Exception as e:
        es_admin = user and user.get('rol', 1) == 3
        admin_data = _build_admin_data() if es_admin else {}
        return render_template('ajustes_usuario.html', errors=[f'Error al actualizar el nombre: {str(e)}'], es_admin=es_admin, admin_data=admin_data)


@app.route('/cambiar-password', methods=['POST'])
@login_required
def cambiar_password():
    """Cambiar la contraseña del usuario actual."""
    from db import obtener_usuario_por_nombre, get_connection
    import bcrypt
    
    usuario_actual = session.get('usuario')
    password_actual = request.form.get('password_actual', '').strip()
    password_nueva = request.form.get('password_nueva', '').strip()
    password_nueva_confirmar = request.form.get('password_nueva_confirmar', '').strip()
    
    errors = []
    
    # Validaciones
    if not validar_no_vacio(password_actual):
        errors.append('Debes ingresar tu contraseña actual')
    if not validar_no_vacio(password_nueva):
        errors.append('La nueva contraseña no puede estar vacía')
    if not validar_longitud(password_nueva, 100, 6):
        errors.append('La nueva contraseña debe tener entre 6 y 100 caracteres')
    if password_nueva != password_nueva_confirmar:
        errors.append('Las contraseñas nuevas no coinciden')
    
    # Verificar contraseña actual
    user = obtener_usuario_por_nombre(usuario_actual)
    if not user:
        errors.append('Usuario no encontrado')
    else:
        password_hash = user.get('password')
        if not bcrypt.checkpw(password_actual.encode('utf-8'), password_hash.encode('utf-8')):
            errors.append('La contraseña actual es incorrecta')
    
    if errors:
        es_admin = user and user.get('rol', 1) == 3
        admin_data = _build_admin_data() if es_admin else {}
        return render_template('ajustes_usuario.html', errors=errors, es_admin=es_admin, admin_data=admin_data)
    
    # Actualizar la contraseña
    try:
        nueva_hash = bcrypt.hashpw(password_nueva.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuario SET password = %s WHERE usuario = %s", (nueva_hash, usuario_actual))
        conn.commit()
        cursor.close()
        conn.close()
        es_admin = user and user.get('rol', 1) == 3
        admin_data = _build_admin_data() if es_admin else {}
        return render_template('ajustes_usuario.html', success='Contraseña actualizada correctamente', es_admin=es_admin, admin_data=admin_data)
    except Exception as e:
        es_admin = user and user.get('rol', 1) == 3
        admin_data = _build_admin_data() if es_admin else {}
        return render_template('ajustes_usuario.html', errors=[f'Error al actualizar la contraseña: {str(e)}'], es_admin=es_admin, admin_data=admin_data)


# ------------------ PÁGINAS INFORMATIVAS ------------------

@app.route('/ayuda')
def ayuda():
    """Página de ayuda con información básica del sistema."""
    return render_template('ayuda.html')


@app.route('/contacto')
def contacto():
    """Página de contacto simple."""
    return render_template('contacto.html')


if __name__ == '__main__':
    # Nota: en producción no usar debug=True y exponer la app directamente.
    app.run(host="0.0.0.0", port=int(os.getenv('PORT', 5001)), debug=os.getenv('FLASK_ENV', 'development') != 'production')
