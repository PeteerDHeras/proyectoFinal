from datetime import datetime, timedelta
import mysql.connector
import bcrypt
import re
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


# ----------- FUNCIONES DE VALIDACIÓN Y SEGURIDAD -------------------

def validar_input_texto(texto, max_length=100, allow_blank=False):
    """Validador simplificado.

    Se basa en:
    - Tipo string
    - Longitud máxima
    - Opcional permitir vacío
    - No intenta reconocer patrones SQL (porque usamos consultas parametrizadas).

    Esto reduce falsos positivos y hace más sencillo el flujo.
    """
    if texto is None:
        return allow_blank
    if not isinstance(texto, str):
        return False
    if not texto.strip():
        return allow_blank
    if len(texto) > max_length:
        return False
    return True


def validar_usuario_password(usuario, password):
    """Valida usuario y contraseña de forma básica.

    - Usuario: obligatorio, <=50, caracteres permitidos alfanumérico + _ - @ .
    - Password: obligatorio, <=100. (La complejidad se comprueba en app.py para registro.)
    """
    if not isinstance(usuario, str) or not isinstance(password, str):
        return False
    if not usuario or not password:
        return False
    if len(usuario) > 50 or len(password) > 100:
        return False
    if not re.match(r'^[a-zA-Z0-9_\-@.]+$', usuario):
        return False
    # No chequeamos SQL keywords porque usamos consultas parametrizadas.
    return True


# Conexión a la base de datos

def get_connection():
    """
    Crea una conexión segura a la base de datos MySQL.
    Usa variables de entorno para las credenciales.
    Compatible con Aiven MySQL con SSL/TLS.
    """
    # Obtener credenciales de variables de entorno
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', 3306))
    db_user = os.getenv('DB_USER', 'pdelasheras')
    db_password = os.getenv('DB_PASSWORD', 'pdelasheras')
    db_name = os.getenv('DB_NAME', 'myplanner_db')
    
    # Configurar conexión con o sin SSL según el host
    connection_config = {
        'host': db_host,
        'port': db_port,
        'user': db_user,
        'password': db_password,
        'database': db_name,
        'autocommit': False,
        'connection_timeout': 10
    }
    
    # Si es Aiven (contiene aivencloud.com), habilitar SSL sin verificación para desarrollo local
    if 'aivencloud.com' in db_host:
        # Para desarrollo local: SSL habilitado pero sin verificar certificados
        connection_config['ssl_disabled'] = False
        connection_config['ssl_verify_cert'] = False
        connection_config['ssl_verify_identity'] = False
    
    return mysql.connector.connect(**connection_config)

# ----------- FUNCIONES PARA GESTIONAR USUARIOS -------------------

# REGISTRAR USUARIO
def registrar_usuario(nombre, contraseña, rol_id):
    # VALIDAR ANTES DE CONECTAR
    if not validar_usuario_password(nombre, contraseña):
        raise ValueError("Datos de usuario inválidos o sospechosos")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        hashed = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt())
        # Tabla real en el esquema: usuario (minúsculas)
        query = "INSERT INTO usuario (usuario, password, rol) VALUES (%s, %s, %s)"
        cursor.execute(query, (nombre, hashed.decode('utf-8'), rol_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# VERIFICAR USUARIO
def verificar_usuario(nombre, contraseña):
    # VALIDAR ANTES DE CONECTAR - PROTECCIÓN SQL INJECTION
    if not validar_usuario_password(nombre, contraseña):
        return False
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Tabla real: usuario
        cursor.execute("SELECT password FROM usuario WHERE usuario=%s", (nombre,))
        result = cursor.fetchone()
        if not result:
            return False
        return bcrypt.checkpw(contraseña.encode('utf-8'), result[0].encode('utf-8'))
    except Exception:
        return False
    finally:
        conn.close()

# Obtener usuario por nombre
def obtener_usuario_por_nombre(nombre):
    # VALIDAR ANTES DE CONECTAR
    if not nombre or not validar_input_texto(nombre, 50):
        return None
    
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, usuario, rol FROM usuario WHERE usuario = %s", (nombre,))
        usuario = cursor.fetchone()
        return usuario
    except Exception:
        return None
    finally:
        conn.close()

#--------------------- FUNCIONES PARA GESTIONAR EVENTOS ------------------------------

# CREAR EVENTO
def crear_evento(nombre, fecha_evento, hora_evento, creador_id, fecha_fin=None, hora_fin=None, descripcion=None):
    # VALIDAR DATOS ANTES DE CONECTAR
    from utils import validar_texto_seguro, validar_fecha_formato, validar_hora_formato, validar_id
    
    if not validar_texto_seguro(nombre, 100, required=True):
        raise ValueError("Nombre de evento inválido")
    
    if not validar_fecha_formato(fecha_evento):
        raise ValueError("Fecha de evento inválida")
    
    if not validar_hora_formato(hora_evento):
        raise ValueError("Hora de evento inválida")
    
    if not validar_id(creador_id):
        raise ValueError("ID de creador inválido")
    
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        raise ValueError("Descripción inválida")
    
    if fecha_fin and not validar_fecha_formato(fecha_fin):
        raise ValueError("Fecha fin inválida")
    
    if hora_fin and not validar_hora_formato(hora_fin):
        raise ValueError("Hora fin inválida")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # fecha_creacion ahora es TIMESTAMP con DEFAULT CURRENT_TIMESTAMP
        query = """
            INSERT INTO eventos (nombre, descripcion, fecha_evento, hora_evento, creador_evento, fecha_fin, hora_fin)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
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
    # VALIDAR DATOS ANTES DE CONECTAR
    from utils import validar_texto_seguro, validar_fecha_formato, validar_hora_formato, validar_id
    
    if not validar_id(evento_id):
        raise ValueError("ID de evento inválido")
    
    if not validar_texto_seguro(nombre, 100, required=True):
        raise ValueError("Nombre de evento inválido")
    
    if not validar_fecha_formato(fecha_evento):
        raise ValueError("Fecha de evento inválida")
    
    if not validar_hora_formato(hora_evento):
        raise ValueError("Hora de evento inválida")
    
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        raise ValueError("Descripción inválida")
    
    if fecha_fin and not validar_fecha_formato(fecha_fin):
        raise ValueError("Fecha fin inválida")
    
    if hora_fin and not validar_hora_formato(hora_fin):
        raise ValueError("Hora fin inválida")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE eventos
            SET nombre=%s, fecha_evento=%s, hora_evento=%s, fecha_fin=%s, hora_fin=%s, descripcion=%s
            WHERE id=%s
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
    # VALIDAR ID ANTES DE CONECTAR
    from utils import validar_id
    
    if not validar_id(evento_id):
        raise ValueError("ID de evento inválido")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM eventos WHERE id=%s", (evento_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# OBTENER EVENTOS
def obtener_eventos(usuario_id=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if usuario_id:
        cursor.execute("SELECT * FROM eventos WHERE creador_evento = %s ORDER BY fecha_evento ASC, hora_evento ASC", (usuario_id,))
    else:
        cursor.execute("SELECT * FROM eventos ORDER BY fecha_evento ASC, hora_evento ASC")
    eventos = cursor.fetchall()
    conn.close()
    return eventos

# ----------- FUNCIONES PARA GESTIONAR TAREAS ------------------------ 

# Modificar CREAR TAREA para incluir estado
def crear_tarea(nombre, descripcion, fecha_limite, prioridad, creador_id, estado=0):
    # VALIDAR DATOS ANTES DE CONECTAR
    from utils import validar_texto_seguro, validar_fecha_formato, validar_id, validar_prioridad, validar_estado
    
    if not validar_texto_seguro(nombre, 100, required=True):
        raise ValueError("Nombre de tarea inválido")
    
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        raise ValueError("Descripción inválida")
    
    if not validar_fecha_formato(fecha_limite):
        raise ValueError("Fecha límite inválida")
    
    if not validar_prioridad(prioridad):
        raise ValueError("Prioridad inválida (debe ser 1, 2 o 3)")
    
    if not validar_id(creador_id):
        raise ValueError("ID de creador inválido")
    
    if not validar_estado(estado):
        raise ValueError("Estado inválido (debe ser 0 o 1)")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # fecha_creacion ahora es TIMESTAMP con DEFAULT CURRENT_TIMESTAMP
        query = """
            INSERT INTO tareas (nombre, descripcion, fecha_limite, prioridad, creador_tarea, estado)
            VALUES (%s, %s, %s, %s, %s, %s)
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
    # VALIDAR DATOS ANTES DE CONECTAR
    from utils import validar_texto_seguro, validar_fecha_formato, validar_id, validar_prioridad, validar_estado
    
    if not validar_id(tarea_id):
        raise ValueError("ID de tarea inválido")
    
    if not validar_texto_seguro(nombre, 100, required=True):
        raise ValueError("Nombre de tarea inválido")
    
    if descripcion and not validar_texto_seguro(descripcion, 500, required=False):
        raise ValueError("Descripción inválida")
    
    if not validar_fecha_formato(fecha_limite):
        raise ValueError("Fecha límite inválida")
    
    if not validar_prioridad(prioridad):
        raise ValueError("Prioridad inválida (debe ser 1, 2 o 3)")
    
    if not validar_estado(estado):
        raise ValueError("Estado inválido (debe ser 0 o 1)")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE tareas
            SET nombre=%s, descripcion=%s, fecha_limite=%s, prioridad=%s, estado=%s
            WHERE id=%s
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
    # VALIDAR ID ANTES DE CONECTAR
    from utils import validar_id
    
    if not validar_id(tarea_id):
        raise ValueError("ID de tarea inválido")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tareas WHERE id=%s", (tarea_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def actualizar_estado_tarea(tarea_id, estado):
    # VALIDAR DATOS ANTES DE CONECTAR
    from utils import validar_id, validar_estado
    
    if not validar_id(tarea_id):
        raise ValueError("ID de tarea inválido")
    
    if not validar_estado(estado):
        raise ValueError("Estado inválido (debe ser 0 o 1)")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "UPDATE tareas SET estado=%s WHERE id=%s"
        cursor.execute(query, (estado, tarea_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# OBTENER TAREAS
def obtener_tareas(usuario_id=None):
    conexion = get_connection()
    with conexion.cursor(dictionary=True) as cursor:
        if usuario_id:
            cursor.execute("SELECT * FROM tareas WHERE creador_tarea = %s", (usuario_id,))
        else:
            cursor.execute("SELECT * FROM tareas")
        tareas = cursor.fetchall()
        for t in tareas:
            estado_val = t.get('estado', 0)
            try:
                estado_int = int(estado_val)
            except (TypeError, ValueError):
                estado_int = 0
            t['estado'] = estado_int  # asegurar tipo
            t['estado_str'] = 'Pendiente' if estado_int == 0 else 'Completada'
    conexion.close()
    return tareas

# OBTENER RESUMEN SEMANA
def obtener_resumen_semana(usuario_id=None):
    """Devuelve el número total de tareas y las completadas en la semana actual del usuario."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    hoy = datetime.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())       # Lunes
    fin_semana = inicio_semana + timedelta(days=6)            # Domingo

    if usuario_id:
        query_total = """
            SELECT COUNT(*) AS total
            FROM tareas
            WHERE fecha_limite BETWEEN %s AND %s AND creador_tarea = %s
        """
        query_completadas = """
            SELECT COUNT(*) AS completadas
            FROM tareas
            WHERE estado = 1 AND fecha_limite BETWEEN %s AND %s AND creador_tarea = %s
        """
        cursor.execute(query_total, (inicio_semana, fin_semana, usuario_id))
        total = cursor.fetchone()['total']

        cursor.execute(query_completadas, (inicio_semana, fin_semana, usuario_id))
        completadas = cursor.fetchone()['completadas']
    else:
        query_total = """
            SELECT COUNT(*) AS total
            FROM tareas
            WHERE fecha_limite BETWEEN %s AND %s
        """
        query_completadas = """
            SELECT COUNT(*) AS completadas
            FROM tareas
            WHERE estado = 1 AND fecha_limite BETWEEN %s AND %s
        """
        cursor.execute(query_total, (inicio_semana, fin_semana))
        total = cursor.fetchone()['total']

        cursor.execute(query_completadas, (inicio_semana, fin_semana))
        completadas = cursor.fetchone()['completadas']

    conn.close()
    return completadas, total

# OBTENER EVENTOS DE MAÑANA
def obtener_eventos_manana(usuario_id=None):
    """Devuelve el número de eventos del día siguiente del usuario."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    hoy = datetime.now().date()
    manana = hoy + timedelta(days=1)

    if usuario_id:
        query = "SELECT COUNT(*) AS eventos FROM eventos WHERE fecha_evento = %s AND creador_evento = %s"
        cursor.execute(query, (manana, usuario_id))
    else:
        query = "SELECT COUNT(*) AS eventos FROM eventos WHERE fecha_evento = %s"
        cursor.execute(query, (manana,))
    
    cantidad = cursor.fetchone()['eventos']

    conn.close()
    return cantidad

def obtener_usuarios():
    """Devuelve la lista de usuarios (id y nombre) para el admin."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, usuario FROM usuario ORDER BY usuario ASC")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def limpiar_datos_antiguos(dias=3):
    """
    Elimina eventos y tareas que hayan pasado hace más de X días.
    Por defecto elimina los que tengan más de 3 días de antigüedad.
    
    Args:
        dias (int): Número de días después de los cuales se eliminan los datos antiguos
    
    Returns:
        tuple: (eventos_eliminados, tareas_eliminadas)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Calcular fecha límite (hace X días)
        fecha_limite = datetime.now().date() - timedelta(days=dias)
        
        # Eliminar eventos antiguos (basado en fecha_evento)
        query_eventos = """
            DELETE FROM eventos 
            WHERE fecha_evento < %s
        """
        cursor.execute(query_eventos, (fecha_limite,))
        eventos_eliminados = cursor.rowcount
        
        # Eliminar tareas antiguas (basado en fecha_limite)
        query_tareas = """
            DELETE FROM tareas 
            WHERE fecha_limite < %s
        """
        cursor.execute(query_tareas, (fecha_limite,))
        tareas_eliminadas = cursor.rowcount
        
        conn.commit()
        
        return eventos_eliminados, tareas_eliminadas
        
    except Exception as e:
        conn.rollback()
        print(f"Error al limpiar datos antiguos: {e}")
        return 0, 0
    finally:
        conn.close()

def registrar_auditoria(usuario, accion, tipo, objeto_id):
    """Registra una acción en la tabla auditoria. DESHABILITADA - tabla no existe."""
    # TODO: Crear tabla auditoria en la base de datos
    pass
    # conn = get_connection()
    # cursor = conn.cursor()
    # query = "INSERT INTO auditoria (usuario, accion, tipo, objeto_id, fecha) VALUES (%s, %s, %s, %s, NOW())"
    # cursor.execute(query, (usuario, accion, tipo, objeto_id))
    # conn.commit()
    # conn.close()

def obtener_auditoria():
    """Devuelve las últimas acciones registradas en auditoria. DESHABILITADA - tabla no existe."""
    # TODO: Crear tabla auditoria en la base de datos
    return []
    # conn = get_connection()
    # cursor = conn.cursor(dictionary=True)
    # cursor.execute("SELECT * FROM auditoria ORDER BY fecha DESC LIMIT 50")
    # registros = cursor.fetchall()
    # conn.close()
    # return registros

