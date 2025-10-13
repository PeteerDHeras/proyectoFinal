from db import registrar_usuario, verificar_usuario, get_connection

prueba = get_connection()
print("FUNCIONA")
#registrar_usuario("admin", "admin", 3)     Ya creado no descomentar de momento

if(verificar_usuario("dmin", "admin")):
    print("Usuario verificado")
else:
    print("Usuario no verificado")
prueba.close()