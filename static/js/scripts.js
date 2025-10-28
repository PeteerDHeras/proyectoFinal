document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('calendar');
  if (!calendarEl) return;

  const calendar = new FullCalendar.Calendar(calendarEl, {
    themeSystem: 'bootstrap5',
    bootstrapFontAwesome: {
      prev: 'fa-solid fa-chevron-left',
      next: 'fa-solid fa-chevron-right',
      today: 'fa-solid fa-calendar-day'
    },
    buttonIcons: false,
    headerToolbar: { 
      left: 'prev,next today', 
      center: 'title', 
      right: 'dayGridMonth,timeGridWeek,timeGridDay' 
    },
    height: 850,
    buttonText: { today: 'Hoy', month: 'Mes', week: 'Semana', day: 'Día' },
    initialView: 'dayGridMonth',
    firstDay: 1,
    selectable: true,
    selectMirror: true,
    editable: true,              // permite drag & resize
    eventResizableFromStart: true,
    dragScroll: true,
    timeZone: 'Europe/Madrid',
    locale: 'es',
    defaultTimedEventDuration: '00:30:00',
    eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
    events: '/api/eventos',

    // Selección de rango para crear evento (día único o varios días)
    select: function(info) {
      // info.startStr y info.endStr (end es exclusivo)
      const start = info.startStr;
      // Ajustar end exclusivo (FullCalendar da end sin incluir el último día en dayGrid)
      let end = info.endStr;
      // Para selección de solo un día end = siguiente día -> si quieres día único pasa solo start
      const params = new URLSearchParams();
      params.set('fecha_evento', start);
      // Si la selección abarca más de un día, añadir fecha_fin
      if (info.end && info.end > info.start) {
        // restar un día al end exclusivo para que coincida con tu semántica
        const endDate = new Date(info.end.getTime() - 24 * 60 * 60 * 1000);
        const yyyy = endDate.getFullYear();
        const mm = String(endDate.getMonth() + 1).padStart(2, '0');
        const dd = String(endDate.getDate()).padStart(2, '0');
        const endInclusive = `${yyyy}-${mm}-${dd}`;
        params.set('fecha_fin', endInclusive);
      }
      window.location.href = `/eventos/nuevo?${params.toString()}`;
    },

    // Click en un día para evento rápido (mantengo tu lógica)
    dateClick: function(info) {
      const params = new URLSearchParams();
      params.set('fecha_evento', info.dateStr);
      window.location.href = `/eventos/nuevo?${params.toString()}`;
    },

    // Click en un evento existente
    eventClick: function(info) {
      if (confirm(`¿Quieres editar el evento "${info.event.title}"?`)) {
        window.location.href = `/eventos/${info.event.id}/editar`;
      }
    },

    // Arrastrar evento a otro día/hora
    eventDrop: function(info) {
      if (!confirm('¿Guardar nueva fecha/hora del evento?')) {
        info.revert();
        return;
      }
      actualizarEventoDesdeCalendario(info, /*esResize*/ false);
    },

    // Redimensionar evento (cambiar fin)
    eventResize: function(info) {
      if (!confirm('¿Guardar nueva duración del evento?')) {
        info.revert();
        return;
      }
      actualizarEventoDesdeCalendario(info, /*esResize*/ true);
    },

    // Mostrar tooltip simple al pasar (opcional)
    eventMouseEnter: function(info) {
      const el = info.el;
      const e = info.event;
      const start = e.startStr.replace('T', ' ');
      const end = e.end ? e.endStr.replace('T', ' ') : '';
      el.setAttribute('title', end ? `${e.title}\nInicio: ${start}\nFin: ${end}` : `${e.title}\nInicio: ${start}`);
    }
  });

  calendar.render();

  // Función auxiliar para formatear fechas/hora
  function splitDateTime(dateObj) {
    // dateObj es Date
    const yyyy = dateObj.getFullYear();
    const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
    const dd = String(dateObj.getDate()).padStart(2, '0');
    const hh = String(dateObj.getHours()).padStart(2, '0');
    const mi = String(dateObj.getMinutes()).padStart(2, '0');
    const ss = String(dateObj.getSeconds()).padStart(2, '0');
    return {
      fecha: `${yyyy}-${mm}-${dd}`,
      hora: `${hh}:${mi}:${ss}`
    };
  }

  function actualizarEventoDesdeCalendario(info, esResize) {
    const event = info.event;

    const startParts = splitDateTime(event.start);
    let endParts = null;
    if (event.end) {
      endParts = splitDateTime(event.end);
    } else if (esResize) {
      // si se intenta resize pero no hay end previo, calculamos algo por defecto
      const fallbackEnd = new Date(event.start.getTime() + 30 * 60 * 1000);
      endParts = splitDateTime(fallbackEnd);
    }

    // Validación simple: si hay end y es anterior al start -> revert
    if (endParts) {
      const startDate = new Date(`${startParts.fecha}T${startParts.hora}`);
      const endDate = new Date(`${endParts.fecha}T${endParts.hora}`);
      if (endDate <= startDate) {
        alert('La fecha/hora de fin no puede ser anterior o igual a la de inicio.');
        info.revert();
        return;
      }
    }

    // Payload para tu endpoint PUT
    const payload = {
      nombre: event.title,
      fecha_evento: startParts.fecha,
      hora_evento: startParts.hora,
      fecha_fin: endParts ? endParts.fecha : null,
      hora_fin: endParts ? endParts.hora : null
    };

    fetch(`/api/eventos/${event.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(r => {
      if (!r.ok) throw new Error('Error al actualizar en servidor');
      return r.json();
    })
    .then(data => {
      // Opcional: mostrar notificación
      // console.log('Evento actualizado', data);
    })
    .catch(err => {
      console.error(err);
      alert('No se pudo actualizar el evento. Se revierte el cambio.');
      info.revert();
    });
  }
});