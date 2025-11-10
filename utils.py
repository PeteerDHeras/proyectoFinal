"""Funciones auxiliares útiles para toda la aplicación.

Este módulo contiene funciones de ayuda que se usan en múltiples
lugares para evitar duplicación de código.
"""

from datetime import datetime, time
import re

def validar_id(id_valor):
    """Valida que un ID sea un entero positivo.
    
    Args:
        id_valor: Valor a validar
        
    Returns:
        bool: True si es válido
    """
    try:
        id_int = int(id_valor)
        return id_int > 0
    except (ValueError, TypeError):
        return False


def validar_texto_seguro(texto, max_length=200, required=True):
    """Valida que un texto sea seguro y no contenga caracteres peligrosos.
    
    Args:
        texto: String a validar
        max_length: Longitud máxima
        required: Si es requerido (no puede estar vacío)
        
    Returns:
        bool: True si es válido
    """
    if not texto:
        return not required
    
    if not isinstance(texto, str):
        return False
    
    if len(texto) > max_length:
        return False
    
    # Detectar patrones peligrosos básicos
    patrones_peligrosos = [r"<script", r"javascript:", r"onerror=", r"onclick="]
    texto_lower = texto.lower()
    for patron in patrones_peligrosos:
        if re.search(patron, texto_lower):
            return False
    
    return True


def validar_fecha_formato(fecha_str):
    """Valida que una fecha tenga formato YYYY-MM-DD válido.
    
    Args:
        fecha_str: String de fecha
        
    Returns:
        bool: True si es válida
    """
    if not fecha_str:
        return False
    
    try:
        datetime.strptime(fecha_str, '%Y-%m-%d')
        return True
    except (ValueError, TypeError):
        return False


def fecha_a_date(fecha_str):
    """Convierte string YYYY-MM-DD a date o None si inválido."""
    try:
        return datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except Exception:
        return None


def validar_fecha_no_pasada(fecha_str):
    """Valida que la fecha no sea anterior a hoy.

    Args:
        fecha_str (str): Fecha en formato YYYY-MM-DD

    Returns:
        bool: True si la fecha es hoy o posterior.
    """
    if not validar_fecha_formato(fecha_str):
        return False
    f = fecha_a_date(fecha_str)
    if f is None:
        return False
    hoy = datetime.now().date()
    return f >= hoy


def validar_fecha_hora_no_pasada(fecha_str, hora_str):
    """Valida que la fecha y hora no sean anteriores al momento actual.
    
    Si la fecha es futura, retorna True sin importar la hora.
    Si la fecha es hoy, valida que la hora no sea anterior a la hora actual.

    Args:
        fecha_str (str): Fecha en formato YYYY-MM-DD
        hora_str (str): Hora en formato HH:MM

    Returns:
        bool: True si la fecha/hora es actual o posterior.
    """
    if not validar_fecha_formato(fecha_str):
        return False
    
    f = fecha_a_date(fecha_str)
    if f is None:
        return False
    
    ahora = datetime.now()
    hoy = ahora.date()
    
    # Si la fecha es futura, es válida
    if f > hoy:
        return True
    
    # Si la fecha es anterior a hoy, no es válida
    if f < hoy:
        return False
    
    # Si la fecha es hoy, validar la hora
    if not hora_str:
        return True  # Si no hay hora especificada, asumir válido
    
    try:
        hora_evento = datetime.strptime(hora_str, '%H:%M').time()
        hora_actual = ahora.time()
        return hora_evento >= hora_actual
    except (ValueError, TypeError):
        return False


def validar_hora_formato(hora_str):
    """Valida que una hora tenga formato HH:MM válido.
    
    Args:
        hora_str: String de hora
        
    Returns:
        bool: True si es válida
    """
    if not hora_str:
        return False
    
    try:
        datetime.strptime(hora_str, '%H:%M')
        return True
    except (ValueError, TypeError):
        return False


def validar_prioridad(prioridad):
    """Valida que la prioridad sea un valor válido (1, 2 o 3).
    
    Args:
        prioridad: Valor a validar
        
    Returns:
        bool: True si es válida
    """
    try:
        p = int(prioridad)
        return p in [1, 2, 3]
    except (ValueError, TypeError):
        return False


def validar_estado(estado):
    """Valida que el estado sea 0 o 1.
    
    Args:
        estado: Valor a validar
        
    Returns:
        bool: True si es válido
    """
    try:
        e = int(estado)
        return e in [0, 1]
    except (ValueError, TypeError):
        return False


def validar_no_vacio(texto):
    """Retorna True si texto contiene algo distinto a espacios."""
    if texto is None:
        return False
    if not isinstance(texto, str):
        return False
    return texto.strip() != ''


def sanitizar_texto(texto):
    """Devuelve el texto recortado y sin caracteres de control peligrosos básicos."""
    if texto is None:
        return ''
    if not isinstance(texto, str):
        texto = str(texto)
    limpio = texto.strip()
    # Quitar caracteres de control raros
    limpio = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", limpio)
    return limpio


def validar_longitud(texto, max_len, min_len=0):
    """Comprueba longitud mínima y máxima."""
    if texto is None:
        return False
    if not isinstance(texto, str):
        texto = str(texto)
    l = len(texto)
    return min_len <= l <= max_len


def validar_rango_horas(hora_inicio, hora_fin):
    """Valida que hora_fin >= hora_inicio (formato HH:MM) si ambas existen.

    Si falta alguna, se considera válido (responsabilidad de otros checks).
    """
    if not hora_inicio or not hora_fin:
        return True
    if not (validar_hora_formato(hora_inicio) and validar_hora_formato(hora_fin)):
        return False
    try:
        hi = datetime.strptime(hora_inicio, '%H:%M')
        hf = datetime.strptime(hora_fin, '%H:%M')
        return hf >= hi
    except Exception:
        return False



def filtrar_eventos_por_fecha(eventos_data, fecha):
    """Filtra una lista de eventos por fecha específica.
    
    Args:
        eventos_data: Lista de diccionarios con datos de eventos
        fecha: date object para filtrar
        
    Returns:
        list: Lista de diccionarios de eventos que coinciden con la fecha
    """
    from models import Evento
    
    eventos_filtrados = []
    for e_data in eventos_data:
        evento = Evento(e_data)
        if evento.es_de_fecha(fecha):
            eventos_filtrados.append(e_data)
    return eventos_filtrados


def filtrar_tareas_por_fecha(tareas_data, fecha):
    """Filtra una lista de tareas por fecha límite.
    
    Args:
        tareas_data: Lista de diccionarios con datos de tareas
        fecha: date object para filtrar
        
    Returns:
        list: Lista de diccionarios de tareas que coinciden con la fecha
    """
    from models import Tarea
    
    tareas_filtradas = []
    for t_data in tareas_data:
        tarea = Tarea(t_data)
        if tarea.es_de_fecha(fecha):
            tareas_filtradas.append(t_data)
    return tareas_filtradas


def normalizar_hora(hora_val):
    """Normaliza diferentes tipos de hora a formato 'HH:MM'.
    
    Args:
        hora_val: Puede ser str, time, timedelta o None
    
    Returns:
        str: Hora en formato 'HH:MM' o cadena vacía si es None
    """
    if not hora_val:
        return ''
    
    # Si ya es string, tomar solo HH:MM
    if isinstance(hora_val, str):
        return hora_val[:5]
    
    # Si es objeto time
    if isinstance(hora_val, time):
        return hora_val.strftime('%H:%M')
    
    # Si es timedelta (algunas BD devuelven así)
    if hasattr(hora_val, 'total_seconds'):
        total = int(hora_val.total_seconds())
        hours = (total // 3600) % 24
        minutes = (total % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    
    # Último recurso: convertir a string y tomar primeros 5 chars
    return str(hora_val)[:5]


def normalizar_fecha(fecha_val):
    """Normaliza una fecha a string 'YYYY-MM-DD'.
    
    Args:
        fecha_val: Puede ser date, datetime, str o None
    
    Returns:
        str: Fecha en formato 'YYYY-MM-DD' o cadena vacía si es None
    """
    if not fecha_val:
        return ''
    
    # Si ya es string, devolverla
    if isinstance(fecha_val, str):
        return fecha_val
    
    # Si es date o datetime, convertir a string
    return str(fecha_val)


def parsear_fecha(fecha_str):
    """Convierte un string de fecha a objeto date.
    
    Args:
        fecha_str: String en formato 'YYYY-MM-DD'
    
    Returns:
        date: Objeto fecha o None si hay error
    """
    if not fecha_str:
        return None
    
    try:
        return datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return None


def validar_fechas(fecha_inicio, fecha_fin):
    """Valida que fecha_fin no sea anterior a fecha_inicio.
    
    Args:
        fecha_inicio: String o objeto date
        fecha_fin: String o objeto date
    
    Returns:
        bool: True si son válidas, False si fecha_fin < fecha_inicio
    """
    if not fecha_fin:
        return True  # Si no hay fecha fin, es válido
    
    try:
        if isinstance(fecha_inicio, str):
            fi = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        else:
            fi = datetime.combine(fecha_inicio, time.min)
        
        if isinstance(fecha_fin, str):
            ff = datetime.strptime(fecha_fin, "%Y-%m-%d")
        else:
            ff = datetime.combine(fecha_fin, time.min)
        
        return ff >= fi
    except (ValueError, TypeError):
        return False


def limpiar_valor_opcional(valor):
    """Limpia valores opcionales que pueden venir como '', 'null', None.
    
    Args:
        valor: Valor a limpiar
    
    Returns:
        El valor original o None si está vacío/null
    """
    if valor in ('', 'null', None):
        return None
    return valor
