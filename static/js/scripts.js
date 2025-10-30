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
    defaultTimedEventDuration: '00:00:10',
    eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
    events: '/api/eventos',
    
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
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tarea-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const tareaId = this.getAttribute('data-tarea-id');
            const completada = this.checked;
            const estado = completada ? 1 : 0;
            
            fetch(`/tareas/${tareaId}/estado`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ estado: estado })
                })
                .then(response => response.json())
                .then(data => {
                  if (!data.success) throw new Error(data.error || 'Error desconocido');

                  // 🔹 Modo 1: card grande
                  const card = this.closest('.card');
                  if (card) {
                    const estadoBadge = card.querySelector('.estado-badge');
                    const title = card.querySelector('.card-title');
                    const desc = card.querySelector('.card-text');

                    if (estadoBadge) {
                      estadoBadge.textContent = completada ? 'Completada' : 'Pendiente';
                      estadoBadge.classList.toggle('bg-success', completada);
                      estadoBadge.classList.toggle('bg-secondary', !completada);
                    }

                    if (title) title.classList.toggle('text-decoration-line-through', completada);
                    if (title) title.classList.toggle('text-muted', completada);
                    if (desc) desc.classList.toggle('text-decoration-line-through', completada);
                  }

                  // 🔹 Actualizar contador de tareas completadas
                  const contador = document.getElementById('contador-tareas');
                  if (contador) {
                      // Parseamos los valores actuales
                      let [actualCompletadas, total] = contador.textContent.split('/').map(Number);
                      if (completada) {
                          actualCompletadas += 1;
                      } else {
                          actualCompletadas -= 1;
                      }
                      contador.textContent = `${actualCompletadas}/${total}`;
                  }
                })
            .catch(error => {
                console.error('Error:', error);
                alert('Error al actualizar el estado de la tarea');
                this.checked = !completada;
            });
        });
    });
});
