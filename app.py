"""Aplicación Flask principal.

Este fichero contiene las rutas y vistas del proyecto.
He añadido comentarios explicativos y dejado las líneas de
`@login_required` comentadas (con la marca "TODO: activar login_required")
en cada ruta para poder activarlas fácilmente en el futuro.

Notas:
- Mantén la clave secreta en variables de entorno en producción.
"""

from datetime import datetime, time, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
from db import *  # funciones de acceso a datos: obtener_eventos, crear_tarea, etc.
from models import Evento, Tarea
from utils import (normalizar_hora, normalizar_fecha, validar_fechas, 
                   limpiar_valor_opcional, filtrar_eventos_por_fecha, 
                   filtrar_tareas_por_fecha, validar_texto_seguro, 
                   validar_fecha_formato, validar_hora_formato, validar_prioridad, validar_estado,
                   validar_fecha_no_pasada, validar_no_vacio, sanitizar_texto,
                   validar_longitud, validar_rango_horas)
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


# ------------------ CONFIGURACIÓN FLASK ------------------
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave_secreta_segura')

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
        if 'usuario' not in session:
            return redirect(url_for('login'))
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
    if request.method == 'POST':
        usuario = sanitizar_texto(request.form.get('usuario', ''))
        password = request.form.get('password', '')
        # Validaciones básicas login
        if not validar_no_vacio(usuario) or not validar_no_vacio(password):
            return render_template('login.html', error='Usuario y contraseña requeridos')
        if not validar_longitud(usuario, 50, 3):
            return render_template('login.html', error='Usuario debe tener entre 3 y 50 caracteres')
        if verificar_usuario(usuario, password):
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Credenciales inválidas')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Cierra la sesión del usuario."""
    session.pop('usuario', None)
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
        if not validar_no_vacio(usuario) or not validar_no_vacio(password):
            return render_template('register.html', error='Usuario y contraseña son obligatorios')
        if not validar_longitud(usuario, 50, 3):
            return render_template('register.html', error='El usuario debe tener entre 3 y 50 caracteres')
        if not re.match(r'^[a-zA-Z0-9]+$', usuario):
            return render_template('register.html', error='El usuario solo puede contener letras y números')
        if usuario != 'admin' and not re.match(patron_password, password):
            return render_template('register.html', error='La contraseña debe tener mínimo 8 caracteres, incluir mayúscula, minúscula y número')
        if password != confirm:
            return render_template('register.html', error='Las contraseñas no coinciden')

        # Usuario existente
        existente = obtener_usuario_por_nombre(usuario)
        if existente:
            return render_template('register.html', error='El usuario ya existe')

        try:
            registrar_usuario(usuario, password, 1)
        except ValueError as e:
            return render_template('register.html', error=str(e))
        except Exception:
            return render_template('register.html', error='Error interno registrando usuario')

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

    # Usar funciones de filtrado
    eventos_hoy = filtrar_eventos_por_fecha(eventos_data, fecha_hoy)
    
    # Filtrar tareas de toda la semana
    tareas_semana = [
        t for t in tareas_data
        if t.get('fecha_limite') and inicio_semana <= t.get('fecha_limite') <= fin_semana
    ]

    return render_template(
        'dashboard.html',
        eventos_hoy=eventos_hoy[:5],
        tareas_hoy=tareas_semana,  # Cambiado a tareas de la semana
        completadas_semana=completadas_semana,
        total_semana=total_semana,
        eventos_manana=eventos_manana,
    )


# ----------------- CALENDARIO ----------------

@app.route('/calendar')
@login_required
def calendar():
    """Página con FullCalendar; los eventos se obtienen desde /api/eventos."""
    return render_template('calendar.html')


# ------------------ EVENTOS ------------------

# Ver todos los eventos
@app.route('/eventos')
#@login_required
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
    if request.method == 'POST':
        # VALIDAR DATOS DEL FORMULARIO
        nombre = sanitizar_texto(request.form.get('nombre', ''))
        fecha_evento = request.form.get('fecha_evento', '').strip()
        hora_evento = request.form.get('hora_evento', '').strip()
        descripcion = sanitizar_texto(request.form.get('descripcion', ''))
        fecha_fin = request.form.get('fecha_fin', '').strip() or None
        hora_fin = request.form.get('hora_fin', '').strip() or None

        # Validar no vacío y longitud
        if not validar_no_vacio(nombre):
            return render_template('nuevo_evento.html', error='El nombre no puede estar vacío', fecha_preseleccionada=fecha_evento)
        if not validar_longitud(nombre, 100, 3):
            return render_template('nuevo_evento.html', error='Longitud de nombre inválida (3-100)', fecha_preseleccionada=fecha_evento)
        if not validar_texto_seguro(nombre, 100, required=True):
            return render_template('nuevo_evento.html', 
                                 error='Nombre inválido o demasiado largo',
                                 fecha_preseleccionada=fecha_evento)
        # No permitir fecha anterior a hoy
        if not validar_fecha_no_pasada(fecha_evento):
            return render_template('nuevo_evento.html', 
                                 error='La fecha del evento no puede ser en el pasado',
                                 fecha_preseleccionada=fecha_evento)

        # Validar rango de horas si hay fin
        if hora_fin and not validar_rango_horas(hora_evento[:5], hora_fin[:5]):
            return render_template('nuevo_evento.html', error='La hora fin debe ser posterior a la hora inicio', fecha_preseleccionada=fecha_evento)

        if fecha_fin and not validar_fecha_no_pasada(fecha_fin):
            return render_template('nuevo_evento.html', 
                                 error='La fecha fin no puede ser en el pasado',
                                 fecha_preseleccionada=fecha_evento)

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
            return redirect(url_for('dashboard'))
        except ValueError as e:
            return render_template('nuevo_evento.html', 
                                 error=str(e),
                                 fecha_preseleccionada=fecha_evento)

    # Capturar fecha preseleccionada si viene desde FullCalendar
    fecha_preseleccionada = request.args.get('fecha', '')
    return render_template('nuevo_evento.html', fecha_preseleccionada=fecha_preseleccionada)


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
    if request.method == 'POST':
        # Sanitizar y extraer datos
        nombre = sanitizar_texto(request.form.get('nombre', ''))
        descripcion = sanitizar_texto(request.form.get('descripcion', ''))
        fecha_limite = request.form.get('fecha_limite', '').strip()
        prioridad = request.form.get('prioridad', '').strip()

        # Validaciones básicas
        if not validar_no_vacio(nombre):
            return render_template('nueva_tarea.html', error='El nombre no puede estar vacío')
        if not validar_longitud(nombre, 100, 3):
            return render_template('nueva_tarea.html', error='Longitud de nombre inválida (3-100)')
        if not validar_fecha_formato(fecha_limite):
            return render_template('nueva_tarea.html', error='Fecha límite inválida')
        if not validar_fecha_no_pasada(fecha_limite):
            return render_template('nueva_tarea.html', error='La fecha límite no puede ser pasada')
        if not validar_prioridad(prioridad):
            return render_template('nueva_tarea.html', error='Prioridad inválida (debe ser 1, 2 o 3)')
        if descripcion and not validar_longitud(descripcion, 500, 0):
            return render_template('nueva_tarea.html', error='Descripción demasiado larga (máx 500)')

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
                estado=0  # Por defecto
            )
            return redirect(url_for('ver_tareas'))
        except ValueError as e:
            return render_template('nueva_tarea.html', error=str(e))

    return render_template('nueva_tarea.html')


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
    """Devuelve TODOS los eventos para FullCalendar en formato JSON.

    Antes se filtraban únicamente los del día. Para el calendario completo
    necesitamos todos para que FullCalendar pueda mostrarlos y permitir
    arrastrar entre días sin que desaparezcan.
    """
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    usuario_id = user['id'] if user else None
    eventos_data = obtener_eventos(usuario_id)

    eventos_json = []
    for e_data in eventos_data:
        evento = Evento(e_data)
        eventos_json.append(evento.to_fullcalendar())

    return jsonify(eventos_json)


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
    hora_inicio = data.get("hora_evento", "00:00:00").strip()[:5]
    
    # Validar formatos
    if not validar_fecha_formato(fecha_inicio):
        return jsonify({"error": "Formato de fecha inválido"}), 400
    if not validar_fecha_no_pasada(fecha_inicio):
        return jsonify({"error": "Fecha de evento debe ser posterior a hoy"}), 400
    
    if not validar_hora_formato(hora_inicio):
        return jsonify({"error": "Formato de hora inválido"}), 400
    
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        return jsonify({"error": "Descripción inválida"}), 400
    
    # Limpiar valores opcionales
    fecha_fin = limpiar_valor_opcional(data.get("fecha_fin"))
    hora_fin = limpiar_valor_opcional(data.get("hora_fin"))
    if hora_fin:
        hora_fin = hora_fin[:5]
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
        return jsonify({'error': 'Nombre inválido'}), 400
    if not validar_fecha_formato(fecha_evento):
        return jsonify({'error': 'Fecha inválida'}), 400
    if not validar_fecha_no_pasada(fecha_evento):
        return jsonify({'error': 'Fecha debe ser hoy o futura'}), 400
    if hora_evento and not validar_hora_formato(hora_evento):
        return jsonify({'error': 'Hora inválida'}), 400
    if fecha_fin and not validar_fecha_formato(fecha_fin):
        return jsonify({'error': 'Fecha fin inválida'}), 400
    if fecha_fin and not validar_fechas(fecha_evento, fecha_fin):
        return jsonify({'error': 'Fecha fin debe ser posterior a inicio'}), 400
    if hora_fin and not validar_hora_formato(hora_fin):
        return jsonify({'error': 'Hora fin inválida'}), 400
    if hora_fin and not validar_rango_horas(hora_evento, hora_fin):
        return jsonify({'error': 'Hora fin debe ser posterior a hora inicio'}), 400
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        return jsonify({'error': 'Descripción inválida'}), 400

    # Obtener usuario
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    creador_id = user['id'] if user else 1

    try:
        crear_evento(
            nombre=nombre,
            fecha_evento=fecha_evento,
            hora_evento=hora_evento+":00",  # asegurar formato completo HH:MM:SS para la BD
            creador_id=creador_id,
            fecha_fin=fecha_fin,
            hora_fin=hora_fin+":00" if hora_fin else None,
            descripcion=descripcion
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
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
    prioridad_raw = data.get('prioridad', 1)
    estado_raw = data.get('estado')

    # Validar nombre
    if not validar_no_vacio(nombre):
        return jsonify({'error': 'Nombre vacío'}), 400
    if not validar_longitud(nombre, 100, 3):
        return jsonify({'error': 'Nombre demasiado corto (mínimo 3) o largo (máximo 100)'}), 400

    # Validar fecha
    if not validar_fecha_formato(fecha_limite):
        return jsonify({'error': 'Fecha límite inválida'}), 400
    if not validar_fecha_no_pasada(fecha_limite):
        return jsonify({'error': 'Fecha límite debe ser posterior a hoy'}), 400

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

    try:
        modificar_tarea(tarea_id, nombre, descripcion or '', fecha_limite, prioridad, estado)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
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


# ------------------ AJUSTES ADMIN ------------------

@app.route('/ajustes', methods=['GET', 'POST'])
@login_required
def ajustes_admin():
    """Vista de ajustes para admin: permite ver eventos/tareas de cualquier usuario."""
    usuario_actual = session.get('usuario')
    user = obtener_usuario_por_nombre(usuario_actual)
    # Solo admin (rol==3)
    if not user or user.get('rol', 1) != 3:
        return redirect(url_for('dashboard'))

    from db import obtener_usuarios, obtener_eventos, obtener_tareas, obtener_auditoria
    usuarios = obtener_usuarios()
    usuario_id = request.form.get('usuario_id') if request.method == 'POST' else None
    eventos = obtener_eventos(usuario_id) if usuario_id else obtener_eventos()
    tareas = obtener_tareas(usuario_id) if usuario_id else obtener_tareas()
    auditoria = obtener_auditoria()
    return render_template('ajustes.html', usuarios=usuarios, usuario_id=usuario_id, eventos=eventos, tareas=tareas, auditoria=auditoria)


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
        return jsonify({'error': 'No tienes permisos de administrador'}), 403
    
    try:
        # Obtener días desde parámetro o usar 3 por defecto
        dias = int(request.form.get('dias', 3))
        if dias < 1 or dias > 365:
            return jsonify({'error': 'El número de días debe estar entre 1 y 365'}), 400
        
        eventos_eliminados, tareas_eliminadas = limpiar_datos_antiguos(dias=dias)
        
        return jsonify({
            'success': True,
            'eventos_eliminados': eventos_eliminados,
            'tareas_eliminadas': tareas_eliminadas,
            'mensaje': f'Se eliminaron {eventos_eliminados} eventos y {tareas_eliminadas} tareas con más de {dias} días de antigüedad'
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error al limpiar datos: {str(e)}'}), 500


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
