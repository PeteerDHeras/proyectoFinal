from flask import Flask, render_template, request, redirect, url_for, session
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
@login_required
def dashboard():
    return render_template('dashboard.html')

# ------------------ TAREAS ------------------

@app.route('/tareas')
@login_required
def ver_tareas():
    tareas = obtener_tareas()
    return render_template('tareas.html', tareas=tareas)

@app.route('/tareas/nueva', methods=['GET', 'POST'])
@login_required
def crear_tarea_view():
    if request.method == 'POST':
        crear_tarea(
            request.form['nombre'],
            request.form['descripcion'],
            request.form['fecha_limite'],
            request.form['prioridad'],
            1  # creador_id fijo por ahora
        )
        return redirect(url_for('ver_tareas'))
    return render_template('nueva_tarea.html')

@app.route('/tareas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
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
@login_required
def eliminar_tarea_view(id):
    eliminar_tarea(id)
    return redirect(url_for('ver_tareas'))

# ------------------ EVENTOS ------------------

@app.route('/eventos')
@login_required
def ver_eventos():
    eventos = obtener_eventos()
    return render_template('eventos.html', eventos=eventos)

@app.route('/eventos/nuevo', methods=['GET', 'POST'])
@login_required
def crear_evento_view():
    if request.method == 'POST':
        crear_evento(
            request.form['nombre'],
            request.form['fecha_evento'],
            request.form['hora_evento'],
            1
        )
        return redirect(url_for('ver_eventos'))
    return render_template('nuevo_evento.html')

@app.route('/eventos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_evento_view(id):
    evento = next((e for e in obtener_eventos() if e['ID'] == id), None)
    if request.method == 'POST':
        modificar_evento(
            id,
            request.form['nombre'],
            request.form['fecha_evento'],
            request.form['hora_evento']
        )
        return redirect(url_for('ver_eventos'))
    return render_template('editar_evento.html', evento=evento)

@app.route('/eventos/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_evento_view(id):
    eliminar_evento(id)
    return redirect(url_for('ver_eventos'))

# ------------------ SUBTAREAS ------------------

@app.route('/subtareas')
@login_required
def ver_subtareas():
    subtareas = obtener_subtareas()
    return render_template('subtareas.html', subtareas=subtareas)

@app.route('/subtareas/nueva', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
def eliminar_subtarea_view(id):
    eliminar_subtarea(id)
    return redirect(url_for('ver_subtareas'))

# ------------------ INICIO ------------------

if __name__ == '__main__':
    app.run(debug=True)
