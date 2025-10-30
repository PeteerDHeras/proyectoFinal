from datetime import datetime, time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from db import *

# ------------------ FLASK ------------------
app = Flask(__name__)
app.secret_key = 'clave_secreta_segura'


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ------------------ INICIO ------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

# ------------------ AUTENTICACIÓN ------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
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
    session.pop('usuario', None)
    return redirect(url_for('login'))

# ----------------- DASHBOARD -----------------

@app.route('/dashboard')
def dashboard():
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
    # Página con FullCalendar; los eventos se obtienen desde /api/eventos
    return render_template('calendar.html')


# ------------------ EVENTOS ------------------

# Ver todos los eventos
@app.route('/eventos')
# @login_required                                                        TODO: activar login_required
def ver_eventos():
    eventos = obtener_eventos()
    return render_template('eventos.html', eventos=eventos)

# Crear nuevo evento
@app.route('/eventos/nuevo', methods=['GET', 'POST'])
# @login_required                                                        TODO: activar login_required
def crear_evento_view():
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
            hora_fin=request.form.get('hora_fin') or None
        )
        return redirect(url_for('dashboard'))

    # Capturar fecha preseleccionada si viene desde FullCalendar        TODO: mejorar manejo de fechas
    fecha_preseleccionada = request.args.get('fecha', '')
    return render_template('nuevo_evento.html', fecha_preseleccionada=fecha_preseleccionada)

# Editar evento
@app.route('/eventos/<int:id>/editar', methods=['GET', 'POST'])
# @login_required                                                        TODO: activar login_required
def editar_evento_view(id):
    evento = next((e for e in obtener_eventos() if e['ID'] == id), None)
    if request.method == 'POST':
        nombre = request.form['nombre']
        fecha_inicio = request.form['fecha_evento']
        hora_inicio = request.form['hora_evento']
        fecha_fin = request.form.get('fecha_fin') or None
        hora_fin = request.form.get('hora_fin') or hora_inicio

        modificar_evento(
            id,
            nombre,
            fecha_inicio,
            hora_inicio,
            fecha_fin,
            hora_fin
        )
        return redirect(url_for('dashboard'))

    return render_template('editar_evento.html', evento=evento)

# Eliminar evento
@app.route('/eventos/<int:id>/eliminar', methods=['POST'])
# @login_required                                                        TODO: activar login_required
def eliminar_evento_view(id):
    eliminar_evento(id)
    return redirect(url_for('ver_eventos'))

# ------------------ API JSON EVENTOS ------------------

@app.route('/api/eventos')
def api_eventos():
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
# @login_required                                                        TODO: activar login_required
def actualizar_evento_api(evento_id):
    data = request.get_json()
    if not data.get("fecha_evento"):
        return jsonify({"error": "Falta fecha_evento"}), 400

    nombre = data.get("nombre", "")
    fecha_inicio = data["fecha_evento"]
    hora_inicio = data.get("hora_evento", "00:00:00")
    fecha_fin = data.get("fecha_fin") or None
    hora_fin = data.get("hora_fin") or hora_inicio

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
        hora_fin
    )
    return jsonify({"message": "Evento actualizado correctamente"}), 200



# MAPEO EN INGLES                                                   TODO: Mirar si vale la pena mantener estas rutas en inglés
@app.route('/events')
def events():
    # Use existing Spanish view
    return redirect(url_for('ver_eventos'))


@app.route('/events/new', methods=['GET', 'POST'])
def new_event():
    return crear_evento_view()


@app.route('/events/<int:id>/edit', methods=['GET', 'POST'])
def edit_event(id):
    return editar_evento_view(id)


@app.route('/events/<int:id>/delete', methods=['POST'])
def delete_event(id):
    return eliminar_evento_view(id)





# ------------------ TAREAS ------------------


@app.route('/tareas')
# @login_required
def ver_tareas():
    tareas = obtener_tareas()
    return render_template('tareas.html', tareas=tareas)

@app.route('/tareas/nueva', methods=['GET', 'POST'])
# @login_required
def crear_tarea_view():
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
# @login_required
def editar_tarea_view(id):
    tareas = obtener_tareas()
    tarea = next((t for t in tareas if t['ID'] == id), None)
    
    if request.method == 'POST':
        estado = 1 if request.form.get('estado') == 'Completada' else 0
        modificar_tarea(
            tarea_id=id,
            nombre=request.form['nombre'],
            descripcion=request.form.get('descripcion', ''),
            fecha_limite=request.form['fecha_limite'],
            prioridad=request.form['prioridad'],
            estado=estado
        )
        return redirect(url_for('ver_tareas'))
    
    return render_template('editar_tarea.html', tarea=tarea)

@app.route('/tareas/<int:id>/eliminar', methods=['POST'])
# @login_required
def eliminar_tarea_view(id):
    eliminar_tarea(id)
    return redirect(url_for('ver_tareas'))

# API para cambiar estado con checkbox
@app.route('/tareas/<int:id>/estado', methods=['POST'])
def actualizar_estado_tarea_view(id):
    data = request.get_json()
    estado = int(data.get('estado', 0))  # Espera 0 o 1
    
    try:
        actualizar_estado_tarea(id, estado)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



# ------------------ SUBTAREAS (Archivadas) ------------------
# Rutas de subtareas deshabilitadas temporalmente; redirigen al dashboard.

@app.route('/subtareas')
def ver_subtareas():
    return redirect(url_for('dashboard'))

@app.route('/subtareas/nueva', methods=['GET', 'POST'])
def crear_subtarea_view():
    return redirect(url_for('dashboard'))

@app.route('/subtareas/<int:id>/editar', methods=['GET', 'POST'])
def editar_subtarea_view(id):
    return redirect(url_for('dashboard'))

@app.route('/subtareas/<int:id>/eliminar', methods=['POST'])
def eliminar_subtarea_view(id):
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True) # Escuchar en todas las interfaces