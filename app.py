"""Aplicación Flask principal.

Este fichero contiene las rutas y vistas del proyecto.
He añadido comentarios explicativos y dejado las líneas de
`@login_required` comentadas (con la marca "TODO: activar login_required")
en cada ruta para poder activarlas fácilmente en el futuro.

Notas:
- Mantén la clave secreta en variables de entorno en producción.
"""

from datetime import datetime, time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from db import *  # funciones de acceso a datos: obtener_eventos, crear_tarea, etc.


# ------------------ CONFIGURACIÓN FLASK ------------------
app = Flask(__name__)
app.secret_key = 'clave_secreta_segura'  # cambiar en producción


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
        usuario = request.form['usuario']
        password = request.form['password']
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


# ----------------- DASHBOARD -----------------

@app.route('/dashboard')
# @login_required                                                        TODO: activar login_required
def dashboard():
    """Vista principal que resume eventos y tareas para el usuario.

    - Filtra eventos y tareas del día actual para mostrarlos en el dashboard.
    - Recupera métricas semanales y eventos de mañana.
    """
    eventos = obtener_eventos()
    tareas = obtener_tareas()
    completadas_semana, total_semana = obtener_resumen_semana()
    eventos_manana = obtener_eventos_manana()
    fecha_hoy = datetime.now().date()

    # --- Filtrar eventos de hoy ---
    eventos_hoy = []
    for e in eventos:
        fecha_evento = e['Fecha_evento']
        if isinstance(fecha_evento, str):
            fecha_evento = datetime.strptime(fecha_evento, '%Y-%m-%d').date()
        if fecha_evento == fecha_hoy:
            eventos_hoy.append(e)

    # --- Filtrar tareas de hoy ---
    tareas_hoy = []
    for t in tareas:
        fecha_limite = t['Fecha_limite']
        if isinstance(fecha_limite, str):
            fecha_limite = datetime.strptime(fecha_limite, '%Y-%m-%d').date()
        if fecha_limite == fecha_hoy:
            tareas_hoy.append(t)

    return render_template(
        'dashboard.html',
        eventos_hoy=eventos_hoy[:5],
        tareas_hoy=tareas_hoy,
        completadas_semana=completadas_semana,
        total_semana=total_semana,
        eventos_manana=eventos_manana,
    )


# ----------------- CALENDARIO ----------------

@app.route('/calendar')
# @login_required                                                        TODO: activar login_required
def calendar():
    """Página con FullCalendar; los eventos se obtienen desde /api/eventos."""
    return render_template('calendar.html')


# ------------------ EVENTOS ------------------

# Ver todos los eventos
@app.route('/eventos')
# @login_required                                                        TODO: activar login_required
def ver_eventos():
    """Lista todos los eventos.

    Plantilla: `eventos.html` espera una lista de eventos.
    """
    eventos = obtener_eventos()
    return render_template('eventos.html', eventos=eventos)


# Crear nuevo evento
@app.route('/eventos/nuevo', methods=['GET', 'POST'])
# @login_required                                                        TODO: activar login_required
def crear_evento_view():
    """Formulario para crear eventos. Si es POST crea el evento y redirige.

    Soporta fecha y hora de inicio; fecha/hora de fin son opcionales.
    """
    if request.method == 'POST':
        usuario_actual = session.get('usuario')
        user = obtener_usuario_por_nombre(usuario_actual)
        creador_id = user['ID'] if user else 1

        # Guardar el evento con fecha/hora de inicio y opcional de fin
        crear_evento(
            nombre=request.form['nombre'],
            fecha_evento=request.form['fecha_evento'],
            hora_evento=request.form['hora_evento'],
            creador_id=creador_id,
            fecha_fin=request.form.get('fecha_fin') or None,
            hora_fin=request.form.get('hora_fin') or None,
            descripcion=request.form.get('descripcion') or None
        )
        return redirect(url_for('dashboard'))

    # Capturar fecha preseleccionada si viene desde FullCalendar
    fecha_preseleccionada = request.args.get('fecha', '')
    return render_template('nuevo_evento.html', fecha_preseleccionada=fecha_preseleccionada)


# Editar evento (página completa eliminada; se usa modal en UI)
@app.route('/eventos/<int:id>/editar', methods=['GET', 'POST'])
# @login_required                                                        TODO: activar login_required
def editar_evento_view(id):
    return redirect(url_for('ver_eventos'))


# Ver evento (modal fragment)
@app.route('/eventos/<int:id>/ver')
# @login_required                                                        TODO: activar login_required
def ver_evento_view(id):
    """Devuelve un fragmento modal con los datos normalizados del evento."""
    evento = next((e for e in obtener_eventos() if e['ID'] == id), None)
    if not evento:
        return ("Evento no encontrado", 404)

    def time_to_str(val):
        """Normaliza diferentes tipos (str, time, timedelta) a 'HH:MM'."""
        if not val:
            return ''
        if isinstance(val, str):
            return val[:5]
        try:
            if isinstance(val, time):
                return val.strftime('%H:%M')
        except Exception:
            pass
        try:
            if hasattr(val, 'total_seconds'):
                total = int(val.total_seconds())
                hours = (total // 3600) % 24
                minutes = (total % 3600) // 60
                return f"{hours:02d}:{minutes:02d}"
        except Exception:
            pass
        return str(val)[:5]

    evento_display = dict(evento)
    evento_display['Hora_evento'] = time_to_str(evento.get('Hora_evento'))
    evento_display['Hora_fin'] = time_to_str(evento.get('Hora_fin'))
    if evento_display.get('Fecha_evento') is not None:
        evento_display['Fecha_evento'] = str(evento_display['Fecha_evento'])
    if evento_display.get('Fecha_fin') is not None:
        evento_display['Fecha_fin'] = str(evento_display['Fecha_fin'])

    return render_template('modal_fragment.html', item=evento_display, tipo='evento')


# Eliminar evento
@app.route('/eventos/<int:id>/eliminar', methods=['POST'])
# @login_required                                                        TODO: activar_login_required
def eliminar_evento_view(id):
    """Elimina un evento y redirige a la lista de eventos."""
    eliminar_evento(id)
    return redirect(url_for('ver_eventos'))


# ------------------ TAREAS (Vistas y API) ------------------


@app.route('/tareas')
# @login_required                                                        TODO: activar_login_required
def ver_tareas():
    """Lista de tareas."""
    tareas = obtener_tareas()
    return render_template('tareas.html', tareas=tareas)


@app.route('/tareas/nueva', methods=['GET', 'POST'])
# @login_required                                                        TODO: activar_login_required
def crear_tarea_view():
    """Crear nueva tarea desde formulario."""
    if request.method == 'POST':
        usuario_actual = session.get('usuario')
        user = obtener_usuario_por_nombre(usuario_actual)
        creador_id = user['ID'] if user else 1

        crear_tarea(
            nombre=request.form['nombre'],
            descripcion=request.form.get('descripcion', ''),
            fecha_limite=request.form['fecha_limite'],
            prioridad=request.form['prioridad'],
            creador_id=creador_id,
            estado=0  # Por defecto
        )
        return redirect(url_for('ver_tareas'))

    return render_template('nueva_tarea.html')


@app.route('/tareas/<int:id>/editar', methods=['GET', 'POST'])
# @login_required                                                        TODO: activar_login_required
def editar_tarea_view(id):
    return redirect(url_for('ver_tareas'))


@app.route('/tareas/<int:id>/eliminar', methods=['POST'])
# @login_required                                                        TODO: activar_login_required
def eliminar_tarea_view(id):
    eliminar_tarea(id)
    return redirect(url_for('ver_tareas'))


@app.route('/tareas/<int:id>/ver')
# @login_required                                                        TODO: activar_login_required
def ver_tarea_view(id):
    """Fragmento/modal para ver detalles de una tarea (normaliza campos)."""
    tarea = next((t for t in obtener_tareas() if t['ID'] == id), None)
    if not tarea:
        return ("Tarea no encontrada", 404)
    tarea_display = dict(tarea)
    # normalize date
    if tarea_display.get('Fecha_limite') is not None:
        tarea_display['Fecha_evento'] = str(tarea_display.get('Fecha_limite'))
    else:
        tarea_display['Fecha_evento'] = ''
    # map common fields expected by modal_fragment
    tarea_display.setdefault('Nombre', tarea_display.get('Nombre', ''))
    tarea_display.setdefault('Descripcion', tarea_display.get('Descripcion', ''))
    tarea_display.setdefault('Hora_evento', '')
    tarea_display.setdefault('Fecha_fin', '')
    tarea_display.setdefault('Hora_fin', '')
    tarea_display.setdefault('Prioridad', tarea_display.get('Prioridad', 1))
    tarea_display.setdefault('Estado', tarea_display.get('Estado', 0))

    return render_template('ver_tarea.html', tarea=tarea_display)


# API para cambiar estado con checkbox (AJAX)
@app.route('/tareas/<int:id>/estado', methods=['POST'])
# @login_required                                                        TODO: activar_login_required
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
# @login_required                                                        TODO: activar_login_required
def api_eventos():
    """Devuelve eventos en formato JSON para FullCalendar.

    Actualmente filtra por eventos del día (comportamiento previo).
    """
    eventos = obtener_eventos()
    eventos_json = []

    fecha_hoy = datetime.today().date()

    for e in eventos:
        # Convertimos la fecha del evento a objeto date
        fecha_evento = datetime.strptime(e['Fecha_evento'], "%Y-%m-%d").date()
        if fecha_evento != fecha_hoy:
            continue  # Saltamos los que no sean de hoy

        # Hora inicio y fin solo HH:MM
        hora_inicio = e.get('Hora_evento', '00:00')[:5]
        hora_fin = e.get('Hora_fin', hora_inicio)[:5]

        eventos_json.append({
            "id": e["ID"],
            "title": e["Nombre"],
            "start": f"{e['Fecha_evento']}T{hora_inicio}",
            "end": f"{e.get('Fecha_fin', e['Fecha_evento'])}T{hora_fin}"
        })

    return jsonify(eventos_json)


@app.route('/api/eventos/<int:evento_id>', methods=['PUT'])
# @login_required                                                        TODO: activar_login_required
def actualizar_evento_api(evento_id):
    """API para actualizar evento desde cliente (JSON PUT).

    Valida fechas básicas y llama a modificar_evento.
    """
    data = request.get_json()
    if not data.get("fecha_evento"):
        return jsonify({"error": "Falta fecha_evento"}), 400

    nombre = data.get("nombre", "")
    descripcion = data.get("descripcion", "")
    fecha_inicio = data["fecha_evento"]
    hora_inicio = data.get("hora_evento", "00:00:00")
    
    # Manejar fecha_fin y hora_fin (pueden ser vacíos o None)
    fecha_fin = data.get("fecha_fin")
    if fecha_fin == '' or fecha_fin == 'null':
        fecha_fin = None
    
    hora_fin = data.get("hora_fin")
    if hora_fin == '' or hora_fin == 'null':
        hora_fin = None
    
    # Si hay fecha_fin pero no hora_fin, usar hora de inicio
    if fecha_fin and not hora_fin:
        hora_fin = hora_inicio

    # Validación simple
    if fecha_fin:
        try:
            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            ff = datetime.strptime(fecha_fin, "%Y-%m-%d")
            if ff < fi:
                return jsonify({"error": "fecha_fin anterior a fecha_evento"}), 400
        except ValueError:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    modificar_evento(
        evento_id,
        nombre,
        fecha_inicio,
        hora_inicio,
        fecha_fin,
        hora_fin,
        descripcion
    )
    eventos = obtener_eventos()
    evento = next((e for e in eventos if e['ID'] == evento_id), None)
    if not evento:
        return jsonify({'error': 'Evento actualizado pero no encontrado'}), 500

    def norm_time(val):
        if not val:
            return ''
        if isinstance(val, str):
            return val[:5]
        try:
            if isinstance(val, time):
                return val.strftime('%H:%M')
        except Exception:
            pass
        try:
            if hasattr(val, 'total_seconds'):
                total = int(val.total_seconds())
                hours = (total // 3600) % 24
                minutes = (total % 3600) // 60
                return f"{hours:02d}:{minutes:02d}"
        except Exception:
            pass
        return str(val)[:5]

    evento_display = dict(evento)
    evento_display['Hora_evento'] = norm_time(evento.get('Hora_evento'))
    evento_display['Hora_fin'] = norm_time(evento.get('Hora_fin'))
    if evento_display.get('Fecha_evento') is not None:
        evento_display['Fecha_evento'] = str(evento_display['Fecha_evento'])
    if evento_display.get('Fecha_fin') is not None:
        evento_display['Fecha_fin'] = str(evento_display['Fecha_fin'])

    return jsonify(evento_display), 200


@app.route('/api/tareas/<int:tarea_id>', methods=['PUT'])
# @login_required                                                        TODO: activar_login_required
def actualizar_tarea_api(tarea_id):
    """API para actualizar una tarea vía JSON (PUT)."""
    data = request.get_json() or {}
    # Map payload to task fields
    nombre = data.get('nombre', '')
    descripcion = data.get('descripcion', '')
    fecha_limite = data.get('fecha_evento') or data.get('fecha_limite') or None
    prioridad = int(data.get('prioridad', 1)) if data.get('prioridad') is not None else 1
    # estado: accept 0/1 or 'Pendiente'/'Completada'
    estado_raw = data.get('estado')
    if estado_raw is None:
        estado = 0
    else:
        try:
            estado = int(estado_raw)
        except Exception:
            estado = 1 if str(estado_raw).lower().startswith('c') else 0

    try:
        modificar_tarea(tarea_id, nombre, descripcion, fecha_limite, prioridad, estado)
        # fetch updated tarea
        tareas = obtener_tareas()
        tarea = next((t for t in tareas if t['ID'] == tarea_id), None)
        if not tarea:
            return jsonify({'error': 'Tarea actualizada pero no encontrada'}), 500

        tarea_display = dict(tarea)

        if tarea_display.get('Fecha_limite') is not None:
            tarea_display['Fecha_limite'] = str(tarea_display['Fecha_limite'])

        tarea_display.setdefault('Nombre', tarea_display.get('Nombre', ''))
        tarea_display.setdefault('Descripcion', tarea_display.get('Descripcion', ''))
        tarea_display.setdefault('Prioridad', tarea_display.get('Prioridad', 1))
        tarea_display.setdefault('Estado', tarea_display.get('Estado', 0))

        return jsonify(tarea_display), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Nota: en producción no usar debug=True y exponer la app directamente.
    app.run(host="0.0.0.0", port=5001, debug=True)  # Escuchar en todas las interfaces, puerto 5001(portatil)