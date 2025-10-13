from db import registrar_usuario, verificar_usuario, get_connection

prueba = get_connection()
print("FUNCIONA")
registrar_usuario("admin", "admin", 3)
prueba.close()