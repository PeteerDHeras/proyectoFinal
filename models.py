"""Modelos simples para Eventos y Tareas.

Este módulo contiene las clases que representan los datos
de eventos y tareas de forma más organizada.
"""

from datetime import datetime, time


class Evento:
    """Representación de un evento usando SOLO claves minúsculas del esquema actual."""

    def __init__(self, data):
        # IDs
        self.id = data.get('id')
        # Campos básicos
        self.nombre = data.get('nombre', '')
        self.descripcion = data.get('descripcion', '')
        # Fechas y horas
        self.fecha_evento = data.get('fecha_evento')
        self.hora_evento = data.get('hora_evento')
        self.fecha_fin = data.get('fecha_fin')
        self.hora_fin = data.get('hora_fin')
        # Creador
        self.creador_id = data.get('creador_evento')
        # Timestamp creación
        self.fecha_creacion = data.get('fecha_creacion')

    def to_dict(self):
        """Convierte el evento a un diccionario con claves en minúsculas."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'fecha_evento': str(self.fecha_evento) if self.fecha_evento else '',
            'hora_evento': self._normalizar_hora(self.hora_evento),
            'fecha_fin': str(self.fecha_fin) if self.fecha_fin else '',
            'hora_fin': self._normalizar_hora(self.hora_fin),
            'creador_evento': self.creador_id,
            'fecha_creacion': self.fecha_creacion
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
            'id': self.id,
            'title': self.nombre,
            'start': f"{self.fecha_evento}T{hora_inicio}",
            'end': f"{fecha_fin}T{hora_fin}",
            'extendedProps': {
                'descripcion': self.descripcion or '',
                'fecha_evento': str(self.fecha_evento) if self.fecha_evento else '',
                'fecha_fin': str(fecha_fin) if fecha_fin else '',
            }
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
    """Representación de una tarea usando SOLO claves minúsculas del esquema actual."""

    def __init__(self, data):
        self.id = data.get('id')
        self.nombre = data.get('nombre', '')
        self.descripcion = data.get('descripcion', '')
        self.fecha_limite = data.get('fecha_limite')
        self.hora_evento = data.get('hora_evento')
        self.prioridad = data.get('prioridad', 1)
        estado_raw = data.get('estado', 0)
        try:
            self.estado = int(estado_raw)
        except Exception:
            self.estado = 0
        self.creador_id = data.get('creador_tarea')
        self.fecha_creacion = data.get('fecha_creacion')

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

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'fecha_limite': str(self.fecha_limite) if self.fecha_limite else '',
            'hora_evento': self._normalizar_hora(self.hora_evento),
            'prioridad': int(self.prioridad) if str(self.prioridad).isdigit() else self.prioridad,
            'estado': self.estado,
            'estado_str': 'Completada' if self.estado == 1 else 'Pendiente',
            'creador_tarea': self.creador_id,
            'fecha_creacion': self.fecha_creacion
        }
    
    def esta_completada(self):
        """Devuelve True si la tarea está completada."""
        return self.estado == 1
    
    def to_modal_dict(self):
        """Convierte la tarea a formato compatible con el modal (como evento)."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'fecha_evento': str(self.fecha_limite) if self.fecha_limite else '',
            'hora_evento': self._normalizar_hora(self.hora_evento),
            'fecha_fin': '',
            'hora_fin': '',
            'prioridad': self.prioridad,
            'estado': self.estado,
            'estado_str': 'Completada' if self.estado == 1 else 'Pendiente'
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
