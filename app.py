from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from db import *

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
    return render_template('base.html')

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

@app.route('/dashboard')
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def dashboard():
    return render_template('dashboard.html')

# ------------------ TAREAS ------------------

@app.route('/tareas')
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def ver_tareas():
    tareas = obtener_tareas()
    return render_template('tareas.html', tareas=tareas)

@app.route('/tareas/nueva', methods=['GET', 'POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def crear_tarea_view():
    if request.method == 'POST':
        usuario_actual = session.get('usuario')
        user = obtener_usuario_por_nombre(usuario_actual)
        creador_id = user['ID'] if user else 1

        crear_tarea(
            request.form['nombre'],
            request.form['descripcion'],
            request.form['fecha_limite'],
            request.form['prioridad'],
            creador_id
        )
        return redirect(url_for('ver_tareas'))
    return render_template('nueva_tarea.html')

@app.route('/tareas/<int:id>/editar', methods=['GET', 'POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def editar_tarea_view(id):
    tarea = next((t for t in obtener_tareas() if t['ID'] == id), None)
    if request.method == 'POST':
        modificar_tarea(
            id,
            request.form['nombre'],
            request.form['descripcion'],
            request.form['fecha_limite'],
            request.form['prioridad']
        )
        return redirect(url_for('ver_tareas'))
    return render_template('editar_tarea.html', tarea=tarea)

@app.route('/tareas/<int:id>/eliminar', methods=['POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def eliminar_tarea_view(id):
    eliminar_tarea(id)
    return redirect(url_for('ver_tareas'))

# ------------------ EVENTOS ------------------

@app.route('/eventos')
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def ver_eventos():
    eventos = obtener_eventos()
    return render_template('eventos.html', eventos=eventos)

@app.route('/eventos/nuevo', methods=['GET', 'POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def crear_evento_view():
    if request.method == 'POST':
        usuario_actual = session.get('usuario')
        user = obtener_usuario_por_nombre(usuario_actual)
        creador_id = user['ID'] if user else 1

        crear_evento(
            request.form['nombre'],
            request.form['fecha_evento'],
            request.form['hora_evento'],
            creador_id,
            # request.form.get('fecha_fin')  # TODO: manejar fecha_fin si es necesario
        )
        return redirect(url_for('dashboard'))

    # Capturar la fecha preseleccionada desde la URL (si viene del calendario)
    fecha_preseleccionada = request.args.get('fecha', '')
    return render_template('nuevo_evento.html', fecha_preseleccionada=fecha_preseleccionada)



@app.route('/eventos/<int:id>/editar', methods=['GET', 'POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def editar_evento_view(id):
    evento = next((e for e in obtener_eventos() if e['ID'] == id), None)
    if request.method == 'POST':
        modificar_evento(
            id,
            request.form['nombre'],
            request.form['fecha_evento'],
            request.form['hora_evento'],
            # request.form.get('fecha_fin') # TODO: manejar fecha_fin si es necesario
        )
        return redirect(url_for('dashboard'))
    return render_template('editar_evento.html', evento=evento)

@app.route('/eventos/<int:id>/eliminar', methods=['POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def eliminar_evento_view(id):
    eliminar_evento(id)
    return redirect(url_for('ver_eventos'))

# ------------------ API JSON ------------------

@app.route('/api/eventos')
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def api_eventos():
    eventos = obtener_eventos()
    eventos_json = [
        {
            "id": e["ID"],
            "title": e["Nombre"],
            "start": f"{e['Fecha_evento']}T{e['Hora_evento']}",
            "end": f"{e['Fecha_fin']}T{e['Hora_evento']}" if e.get("Fecha_fin") else None,
        }
        for e in eventos
    ]
    return jsonify(eventos_json)

@app.route('/api/eventos/<int:evento_id>', methods=['PUT'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def actualizar_evento_api(evento_id):
    data = request.get_json()

    if not data.get("fecha_evento"):
        return jsonify({"error": "Faltan datos"}), 400

    modificar_evento(
        evento_id,
        data.get("nombre", ""),  # opcional
        data["fecha_evento"],
        data.get("hora_evento", "00:00:00"),
        data.get("fecha_fin")
    )

    return jsonify({"message": "Evento actualizado correctamente"}), 200

# ------------------ SUBTAREAS ------------------

@app.route('/subtareas')
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def ver_subtareas():
    subtareas = obtener_subtareas()
    return render_template('subtareas.html', subtareas=subtareas)

@app.route('/subtareas/nueva', methods=['GET', 'POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def crear_subtarea_view():
    if request.method == 'POST':
        crear_subtarea(
            request.form['nombre'],
            request.form['descripcion'],
            request.form['fecha_limite'],
            request.form['tarea_padre_id'],
            1
        )
        return redirect(url_for('ver_subtareas'))
    return render_template('nueva_subtarea.html')

@app.route('/subtareas/<int:id>/editar', methods=['GET', 'POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def editar_subtarea_view(id):
    subtarea = next((s for s in obtener_subtareas() if s['ID'] == id), None)
    if request.method == 'POST':
        modificar_subtarea(
            id,
            request.form['nombre'],
            request.form['descripcion'],
            request.form['fecha_limite']
        )
        return redirect(url_for('ver_subtareas'))
    return render_template('editar_subtarea.html', subtarea=subtarea)

@app.route('/subtareas/<int:id>/eliminar', methods=['POST'])
# @login_required DESCOMENTAR PARA AUTH TODO: activar login_required
def eliminar_subtarea_view(id):
    eliminar_subtarea(id)
    return redirect(url_for('ver_subtareas'))

# ------------------ INICIO ------------------

if __name__ == '__main__':
    app.run(debug=True)
