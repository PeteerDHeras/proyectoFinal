from datetime import datetime, timedelta
import mysql.connector
import bcrypt


# Conexión a la base de datos

def get_connection():
    return mysql.connector.connect(
        host="localhost",                   # 192.168.0.120 o localhost (portatil)
        user="pdelasheras",                     
        password="pdelasheras",
        database="myplanner_db",
        autocommit=False,  # Desactivar autocommit para manejar transacciones manualmente
        connection_timeout=10  # Timeout de conexión
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
def crear_evento(nombre, fecha_evento, hora_evento, creador_id, fecha_fin=None, hora_fin=None, descripcion=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO EVENTOS (Nombre, Descripcion, Fecha_creacion, Fecha_evento, Hora_evento, creadorEvento, Fecha_fin, Hora_fin)
            VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nombre, descripcion, fecha_evento, hora_evento, creador_id, fecha_fin, hora_fin))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# MODIFICAR EVENTO
def modificar_evento(evento_id, nombre, fecha_evento, hora_evento, fecha_fin=None, hora_fin=None, descripcion=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE EVENTOS
            SET Nombre=%s, Fecha_evento=%s, Hora_evento=%s, Fecha_fin=%s, Hora_fin=%s, Descripcion=%s
            WHERE ID=%s
        """
        cursor.execute(query, (nombre, fecha_evento, hora_evento, fecha_fin, hora_fin, descripcion, evento_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ELIMINAR EVENTO
def eliminar_evento(evento_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM EVENTOS WHERE ID=%s", (evento_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# OBTENER EVENTOS
def obtener_eventos():  
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM EVENTOS ORDER BY Fecha_evento ASC, Hora_evento ASC")
    eventos = cursor.fetchall()
    conn.close()
    return eventos

# ----------- FUNCIONES PARA GESTIONAR TAREAS ------------------------ 

# Modificar CREAR TAREA para incluir estado
def crear_tarea(nombre, descripcion, fecha_limite, prioridad, creador_id, estado=0):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO TAREAS (Nombre, Descripcion, Fecha_creacion, Fecha_limite, Prioridad, creadorTarea, Estado)
            VALUES (%s, %s, CURDATE(), %s, %s, %s, %s)
        """
        cursor.execute(query, (nombre, descripcion, fecha_limite, prioridad, creador_id, estado))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Modificar MODIFICAR TAREA para incluir estado
def modificar_tarea(tarea_id, nombre, descripcion, fecha_limite, prioridad, estado):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE TAREAS
            SET Nombre=%s, Descripcion=%s, Fecha_limite=%s, Prioridad=%s, Estado=%s
            WHERE ID=%s
        """
        cursor.execute(query, (nombre, descripcion, fecha_limite, prioridad, estado, tarea_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ELIMINAR TAREA
def eliminar_tarea(tarea_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM TAREAS WHERE ID=%s", (tarea_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def actualizar_estado_tarea(tarea_id, estado):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "UPDATE TAREAS SET Estado=%s WHERE ID=%s"
        cursor.execute(query, (estado, tarea_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# OBTENER TAREAS
def obtener_tareas():
    conexion = get_connection()
    with conexion.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM tareas")
        tareas = cursor.fetchall()
        for t in tareas:
            estado = int(t.get('Estado') or t.get('estado') or 0)
            t['Estado'] = estado  # ← Esto es clave para que Jinja lo compare bien
            t['Estado_str'] = 'Pendiente' if estado == 0 else 'Completada'
    conexion.close()
    return tareas

# OBTENER RESUMEN SEMANA
def obtener_resumen_semana():
    """Devuelve el número total de tareas y las completadas en la semana actual."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())       # Lunes
    fin_semana = inicio_semana + timedelta(days=6)            # Domingo

    query_total = """
        SELECT COUNT(*) AS total
        FROM TAREAS
        WHERE Fecha_limite BETWEEN %s AND %s
    """
    query_completadas = """
        SELECT COUNT(*) AS completadas
        FROM TAREAS
        WHERE Estado = 1 AND Fecha_limite BETWEEN %s AND %s
    """

    cursor.execute(query_total, (inicio_semana, fin_semana))
    total = cursor.fetchone()['total']

    cursor.execute(query_completadas, (inicio_semana, fin_semana))
    completadas = cursor.fetchone()['completadas']

    conn.close()
    return completadas, total

# OBTENER EVENTOS DE MAÑANA
def obtener_eventos_manana():
    """Devuelve el número de eventos del día siguiente."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    hoy = datetime.now().date()
    manana = hoy + timedelta(days=1)

    query = "SELECT COUNT(*) AS eventos FROM EVENTOS WHERE Fecha_evento = %s"
    cursor.execute(query, (manana,))
    cantidad = cursor.fetchone()['eventos']

    conn.close()
    return cantidad

