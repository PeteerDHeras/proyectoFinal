document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('calendar');
  if (!calendarEl) return;

  const calendar = new FullCalendar.Calendar(calendarEl, {
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,timeGridDay'
    },
    initialView: 'dayGridMonth',
    firstDay: 1,
    selectable: true,
    editable: true,

    events: '/api/eventos',

    // TODO: Habilitar selección de rango cuando se implemente la funcionalidad de eventos de varios días

    // // SELECCIÓN DE RANGO DE DÍAS

    // select: function(info) {
    //   // Mostrar un prompt para que el usuario nombre el evento
    //   const nombre = prompt(`Nombre del nuevo evento (del ${info.startStr} al ${info.endStr}):`);
      
    //   if (nombre) {
    //     window.location.href = `/eventos/nuevo?fecha_evento=${info.dateStr}?fecha_fin=${info.endStr}nombre=${encodeURIComponent(nombre)}`;
    //   }
    //   // Deselecciona el rango visualmente
    //   calendar.unselect();
    // },


    // CLIC EN UN DÍA DEL CALENDARIO
    dateClick: function(info) {
      const confirmar = confirm(`¿Quieres crear un evento el ${info.dateStr}?`);
      if (confirmar) {
        window.location.href = `/eventos/nuevo?fecha=${info.dateStr}`;
      }
    },

    // CLIC EN UN EVENTO EXISTENTE
    eventClick: function(info) {
      const confirmar = confirm(`¿Quieres editar el evento "${info.event.title}"?`);
      if (confirmar) {
        window.location.href = `/eventos/${info.event.id}/editar`;
      }
    }
  });

  calendar.render();
});