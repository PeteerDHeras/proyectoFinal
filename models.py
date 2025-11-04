"""Modelos simples para Eventos y Tareas.

Este módulo contiene las clases que representan los datos
de eventos y tareas de forma más organizada.
"""

from datetime import datetime, time


class Evento:
    """Clase simple para representar un evento."""
    
    def __init__(self, data):
        """Inicializa un evento a partir de un diccionario de la BD."""
        self.id = data.get('ID')
        self.nombre = data.get('Nombre', '')
        self.descripcion = data.get('Descripcion', '')
        self.fecha_evento = data.get('Fecha_evento')
        self.hora_evento = data.get('Hora_evento')
        self.fecha_fin = data.get('Fecha_fin')
        self.hora_fin = data.get('Hora_fin')
        self.creador_id = data.get('creadorEvento')
        self.fecha_creacion = data.get('Fecha_creacion')
    
    def to_dict(self):
        """Convierte el evento a un diccionario normalizado."""
        return {
            'ID': self.id,
            'Nombre': self.nombre,
            'Descripcion': self.descripcion,
            'Fecha_evento': str(self.fecha_evento) if self.fecha_evento else '',
            'Hora_evento': self._normalizar_hora(self.hora_evento),
            'Fecha_fin': str(self.fecha_fin) if self.fecha_fin else '',
            'Hora_fin': self._normalizar_hora(self.hora_fin),
            'creadorEvento': self.creador_id,
            'Fecha_creacion': self.fecha_creacion
        }
    
    def _normalizar_hora(self, hora_val):
        """Normaliza diferentes tipos de hora a formato 'HH:MM'."""
        if not hora_val:
            return ''
        if isinstance(hora_val, str):
            return hora_val[:5]
        if isinstance(hora_val, time):
            return hora_val.strftime('%H:%M')
        # Para timedelta
        if hasattr(hora_val, 'total_seconds'):
            total = int(hora_val.total_seconds())
            hours = (total // 3600) % 24
            minutes = (total % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return str(hora_val)[:5]
    
    def to_fullcalendar(self):
        """Convierte el evento al formato JSON de FullCalendar."""
        hora_inicio = self._normalizar_hora(self.hora_evento) or '00:00'
        hora_fin = self._normalizar_hora(self.hora_fin) or hora_inicio
        fecha_fin = self.fecha_fin or self.fecha_evento
        
        return {
            "id": self.id,
            "title": self.nombre,
            "start": f"{self.fecha_evento}T{hora_inicio}",
            "end": f"{fecha_fin}T{hora_fin}"
        }
    
    def es_de_fecha(self, fecha):
        """Verifica si el evento es de una fecha específica.
        
        Args:
            fecha: date object para comparar
            
        Returns:
            bool: True si el evento coincide con esa fecha
        """
        fecha_evento = self.fecha_evento
        if isinstance(fecha_evento, str):
            fecha_evento = datetime.strptime(fecha_evento, '%Y-%m-%d').date()
        return fecha_evento == fecha


class Tarea:
    """Clase simple para representar una tarea."""
    
    def __init__(self, data):
        """Inicializa una tarea a partir de un diccionario de la BD."""
        self.id = data.get('ID')
        self.nombre = data.get('Nombre', '')
        self.descripcion = data.get('Descripcion', '')
        self.fecha_limite = data.get('Fecha_limite')
        self.prioridad = data.get('Prioridad', 1)
        self.estado = int(data.get('Estado', 0))
        self.creador_id = data.get('creadorTarea')
        self.fecha_creacion = data.get('Fecha_creacion')
    
    def to_dict(self):
        """Convierte la tarea a un diccionario normalizado."""
        return {
            'ID': self.id,
            'Nombre': self.nombre,
            'Descripcion': self.descripcion,
            'Fecha_limite': str(self.fecha_limite) if self.fecha_limite else '',
            'Prioridad': self.prioridad,
            'Estado': self.estado,
            'Estado_str': 'Completada' if self.estado == 1 else 'Pendiente',
            'creadorTarea': self.creador_id,
            'Fecha_creacion': self.fecha_creacion
        }
    
    def esta_completada(self):
        """Devuelve True si la tarea está completada."""
        return self.estado == 1
    
    def to_modal_dict(self):
        """Convierte la tarea a formato compatible con el modal (como evento)."""
        return {
            'ID': self.id,
            'Nombre': self.nombre,
            'Descripcion': self.descripcion,
            'Fecha_evento': str(self.fecha_limite) if self.fecha_limite else '',
            'Hora_evento': '',
            'Fecha_fin': '',
            'Hora_fin': '',
            'Prioridad': self.prioridad,
            'Estado': self.estado
        }
    
    def es_de_fecha(self, fecha):
        """Verifica si la tarea tiene fecha límite en una fecha específica.
        
        Args:
            fecha: date object para comparar
            
        Returns:
            bool: True si la tarea tiene esa fecha límite
        """
        fecha_limite = self.fecha_limite
        if isinstance(fecha_limite, str):
            fecha_limite = datetime.strptime(fecha_limite, '%Y-%m-%d').date()
        return fecha_limite == fecha
