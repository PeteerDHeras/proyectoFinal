import mysql.connector
import bcrypt


# Conexión a la base de datos

def get_connection():
    return mysql.connector.connect(
        host="192.168.0.120",
        user="pdelasheras",
        password="pdelasheras",
        database="myplanner_db"
    )

# FUNCIONES PARA GESTIONAR USUARIOS ------------------------------

# Registrar usuario
def registrar_usuario(nombre, contraseña):
    conn = get_connection()
    cursor = conn.cursor()
    hashed = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt())
    query = "INSERT INTO usuarios (nombre, password) VALUES (%s, %s)"
    cursor.execute(query, (nombre, hashed))
    conn.commit()
    conn.close()

# Verificar usuario
def verificar_usuario(nombre, contraseña):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM usuarios WHERE nombre=%s", (nombre,))
    result = cursor.fetchone()
    conn.close()
    if result and bcrypt.checkpw(contraseña.encode('utf-8'), result[0].encode('utf-8')):
        return True
    return False