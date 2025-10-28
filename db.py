import mysql.connector
import bcrypt


# Conexión a la base de datos

def get_connection():
    return mysql.connector.connect(
        host="192.168.0.120",                   # TODO: Cambiar de localhost a "myplanner.com" para simulación producción
        user="pdelasheras",                     # TODO: Hacer que esta información viaje en ssl (Apache)
        password="pdelasheras",
        database="myplanner_db"
    )

# ----------- FUNCIONES PARA GESTIONAR USUARIOS -------------------

# REGISTRAR USUARIO
def registrar_usuario(nombre, contraseña, rol_id):
    conn = get_connection()
    cursor = conn.cursor()
    hashed = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt())
    query = "INSERT INTO USUARIO (usuario, password, rol) VALUES (%s, %s, %s)"
    cursor.execute(query, (nombre, hashed.decode('utf-8'), rol_id))
    conn.commit()
    conn.close()

# VERIFICAR USUARIO
def verificar_usuario(nombre, contraseña):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM USUARIO WHERE usuario=%s", (nombre,))
    result = cursor.fetchone()
    conn.close()
    if result and bcrypt.checkpw(contraseña.encode('utf-8'), result[0].encode('utf-8')):
        return True
    return False

# Obtener usuario por nombre
def obtener_usuario_por_nombre(nombre):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ID FROM USUARIO WHERE usuario = %s", (nombre,))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

#--------------------- FUNCIONES PARA GESTIONAR EVENTOS ------------------------------

# CREAR EVENTO
def crear_evento(nombre, fecha_evento, hora_evento, creador_id, fecha_fin=None, hora_fin=None):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO EVENTOS (Nombre, Fecha_creacion, Fecha_evento, Hora_evento, creadorEvento, Fecha_fin, Hora_fin)
        VALUES (%s, CURDATE(), %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (nombre, fecha_evento, hora_evento, creador_id, fecha_fin, hora_fin))
    conn.commit()
    conn.close()

# MODIFICAR EVENTO
def modificar_evento(evento_id, nombre, fecha_evento, hora_evento, fecha_fin=None, hora_fin=None):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        UPDATE EVENTOS
        SET Nombre=%s, Fecha_evento=%s, Hora_evento=%s, Fecha_fin=%s, Hora_fin=%s
        WHERE ID=%s
    """
    cursor.execute(query, (nombre, fecha_evento, hora_evento, fecha_fin, hora_fin, evento_id))
    conn.commit()
    conn.close()


# ELIMINAR EVENTO
def eliminar_evento(evento_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM EVENTOS WHERE ID=%s", (evento_id,))
    conn.commit()
    conn.close()

# OBTENER EVENTOS
def obtener_eventos():  
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM EVENTOS ORDER BY Fecha_evento ASC, Hora_evento ASC")
    eventos = cursor.fetchall()
    conn.close()
    return eventos




















# ----------- FUNCIONES PARA GESTIONAR TAREAS ------------------------ TODO: IMPLEMENTAR EN APP.PY

# Modificar CREAR TAREA para incluir estado
def crear_tarea(nombre, descripcion, fecha_limite, prioridad, creador_id, estado='Pendiente'):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO TAREAS (Nombre, Descripcion, Fecha_creacion, Fecha_limite, Prioridad, creadorTarea, Estado)
        VALUES (%s, %s, CURDATE(), %s, %s, %s, %s)
    """
    cursor.execute(query, (nombre, descripcion, fecha_limite, prioridad, creador_id, estado))
    conn.commit()
    conn.close()

# Modificar MODIFICAR TAREA para incluir estado
def modificar_tarea(tarea_id, nombre, descripcion, fecha_limite, prioridad, estado):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        UPDATE TAREAS
        SET Nombre=%s, Descripcion=%s, Fecha_limite=%s, Prioridad=%s, Estado=%s
        WHERE ID=%s
    """
    cursor.execute(query, (nombre, descripcion, fecha_limite, prioridad, estado, tarea_id))
    conn.commit()
    conn.close()

# ELIMINAR TAREA
def eliminar_tarea(tarea_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM TAREAS WHERE ID=%s", (tarea_id,))
    conn.commit()
    conn.close()

def actualizar_estado_tarea(tarea_id, estado):
    conn = get_connection()
    cursor = conn.cursor()
    query = "UPDATE TAREAS SET Estado=%s WHERE ID=%s"
    cursor.execute(query, (estado, tarea_id))
    conn.commit()
    conn.close()

# OBTENER TAREAS
def obtener_tareas():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM TAREAS")
    tareas = cursor.fetchall()
    conn.close()
    return tareas


# FUNCIONES PARA GESTIONAR SUBTAREAS ------------------------------ TODO: IMPLEMENTAR EN APP.PY (SI ES NECESARIO)

# CREAR SUBTAREA
def crear_subtarea(nombre, descripcion, fecha_limite, tarea_padre_id, creador_id):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO SUBTAREAS (Nombre, Descripcion, Fecha_limite, tareaPadre, creadorSub)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (nombre, descripcion, fecha_limite, tarea_padre_id, creador_id))
    conn.commit()
    conn.close()

# MODIFICAR SUBTAREA
def modificar_subtarea(subtarea_id, nombre, descripcion, fecha_limite):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        UPDATE SUBTAREAS
        SET Nombre=%s, Descripcion=%s, Fecha_limite=%s
        WHERE ID=%s
    """
    cursor.execute(query, (nombre, descripcion, fecha_limite, subtarea_id))
    conn.commit()
    conn.close()

# ELIMINAR SUBTAREA
def eliminar_subtarea(subtarea_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM SUBTAREAS WHERE ID=%s", (subtarea_id,))
    conn.commit()
    conn.close()
    
# OBTENER SUBTAREAS
def obtener_subtareas():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM SUBTAREAS")
    subtareas = cursor.fetchall()
    conn.close()
    return subtareas
