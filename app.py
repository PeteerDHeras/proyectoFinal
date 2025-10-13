from db import registrar_usuario, verificar_usuario, get_connection

# Ejemplo de uso:
# registrar_usuario("usuario", "contraseña")
# print(verificar_usuario("usuario", "contraseña"))

prueba = get_connection()
print("FUNCIONA")
prueba.close()