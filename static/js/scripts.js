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
    buttonText: { today: 'Hoy', month: 'Mes', week: 'Semana', day: 'Día' },
    initialView: 'dayGridMonth',
    firstDay: 1,
    selectable: true,
    editable: true,
    timeZone: 'Europe/Madrid',
    locale: 'es',
    defaultTimedEventDuration: '00:01:00',
    eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
    events: '/api/eventos',
    
    // Click en un día/fecha

    dateClick: function(info) {
      
      const params = new URLSearchParams();
      params.set('fecha_evento', info.dateStr);
      if (info.timeStr) params.set('hora_evento', info.timeStr);
      window.location.href = `/eventos/nuevo?${params.toString()}`;
    },

    // Click en un evento existente
    eventClick: function(info) {
      if (confirm(`¿Quieres editar el evento "${info.event.title}"?`)) {
        window.location.href = `/eventos/${info.event.id}/editar`;
      }
    }
  });

  calendar.render();
});
