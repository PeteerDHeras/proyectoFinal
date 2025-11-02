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
        if (!confirm(`¿Abrir detalles del evento "${info.event.title}"?`)) return;
        // create a temporary button that our delegated click handler will catch
        const tmp = document.createElement('button');
        tmp.style.display = 'none';
        tmp.className = 'btn-view-event';
        tmp.setAttribute('data-id', info.event.id);
        tmp.setAttribute('data-type', 'evento');
        // open directly in view mode; if you want edit mode by default, set data-action="edit"
        document.body.appendChild(tmp);
        tmp.click();
        tmp.remove();
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

  // Helper: show a temporary toast in corner
  function showToast(message, type) {
    const colors = { success: '#16a34a', error: '#dc2626', info: '#0ea5e9' };
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.right = '16px';
    toast.style.top = '16px';
    toast.style.background = colors[type] || '#333';
    toast.style.color = '#fff';
    toast.style.padding = '8px 12px';
    toast.style.borderRadius = '6px';
    toast.style.boxShadow = '0 6px 18px rgba(0,0,0,0.12)';
    toast.style.zIndex = 9999;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 300ms'; }, 1400);
    setTimeout(() => toast.remove(), 2000);
  }

  // Helper: update an event or task on the current page without reload
  function updateItemInDOM(type, id, payload) {
    if (type === 'evento') {
      const btn = document.querySelector(`.btn-view-event[data-id="${id}"]`);
      if (!btn) return;
      const card = btn.closest('[class*="p-4"]') || btn.closest('div');
      if (!card) return;
      const title = card.querySelector('p.text-text-light') || card.querySelector('p');
      if (title) title.textContent = payload.nombre || title.textContent;
      const fecha = card.querySelector('p.text-gray-500');
      const ps = card.querySelectorAll('p.text-gray-500');
      if (ps && ps.length >= 2) {
        ps[0].childNodes && (ps[0].childNodes[ps[0].childNodes.length-1].textContent = ' ' + (payload.fecha_evento || ''));
        ps[1].childNodes && (ps[1].childNodes[ps[1].childNodes.length-1].textContent = ' ' + (payload.hora_evento ? payload.hora_evento.slice(0,5) : ''));
      }
      return true;
    }

    if (type === 'tarea') {
      // Try to locate the card: prefer the checkbox, otherwise the view/edit button
      let anchor = document.querySelector(`.tarea-checkbox[data-tarea-id="${id}"]`);
      if (!anchor) anchor = document.querySelector(`.btn-view-task[data-id="${id}"]`);
      if (!anchor) anchor = document.querySelector(`[data-id="${id}"]`);
      if (!anchor) return;
      // find nearest card-like container
      let card = anchor.closest('.card');
      if (!card) {
        // fallback: maybe different structure, climb to a parent with class containing 'tarea' or a common container
        card = anchor.closest('[class*="tarea"]') || anchor.closest('div');
      }
      if (!card) return;

      // title and description: try common selectors then fallbacks
      const title = card.querySelector('.card-title') || card.querySelector('h6') || card.querySelector('h5') || card.querySelector('p');
      const desc = card.querySelector('.card-text') || card.querySelector('p.card-text') || card.querySelector('p.text-secondary');
      const fechaSpan = card.querySelector('span.text-secondary');
      const prioridadBadge = card.querySelector('span.badge');

      if (title && payload.nombre) title.textContent = payload.nombre;
      if (desc) desc.textContent = payload.descripcion || '';
      if (fechaSpan) fechaSpan.textContent = payload.fecha_evento || '';
      if (prioridadBadge && payload.prioridad) {
        const p = parseInt(payload.prioridad, 10);
        prioridadBadge.textContent = p === 1 ? 'Baja' : (p === 2 ? 'Media' : 'Alta');
      }
      return true;
    }

    return false;
  }

  // Helper: remove element from DOM after delete
  function removeItemFromDOM(type, id) {
    if (type === 'evento') {
      const btn = document.querySelector(`.btn-view-event[data-id="${id}"]`);
      if (!btn) return;
      // remove outer p-4 container if present
      const container = btn.closest('.p-4') || btn.closest('[class*="p-4"]') || btn.closest('div');
      if (container) container.remove();
      return;
    }
    if (type === 'tarea') {
      const checkbox = document.querySelector(`.tarea-checkbox[data-tarea-id="${id}"]`);
      if (!checkbox) return;
      const card = checkbox.closest('.card');
      if (card) card.remove();
    }
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
  // Live search helpers for Tareas and Eventos (debounced)
  const debounce = (fn, ms = 150) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  };

  // Tareas: filter rows inside #tareas-list
  const searchTareasInput = document.getElementById('search-tareas');
  if (searchTareasInput) {
    const tareasList = document.getElementById('tareas-list');
    const filterTareas = () => {
      const q = searchTareasInput.value.trim().toLowerCase();
      if (!tareasList) return;
      const rows = Array.from(tareasList.children);
      rows.forEach(row => {
        const text = (row.innerText || row.textContent || '').toLowerCase();
        row.style.display = q === '' || text.includes(q) ? '' : 'none';
      });
    };
    searchTareasInput.addEventListener('input', debounce(filterTareas, 150));
  }

  // Eventos: filter cards inside #eventos-grid
  const searchEventosInput = document.getElementById('search-eventos');
  if (searchEventosInput) {
    const eventosGrid = document.getElementById('eventos-grid');
    const filterEventos = () => {
      const q = searchEventosInput.value.trim().toLowerCase();
      if (!eventosGrid) return;
      const cards = Array.from(eventosGrid.children);
      cards.forEach(card => {
        const text = (card.innerText || card.textContent || '').toLowerCase();
        card.style.display = q === '' || text.includes(q) ? '' : 'none';
      });
    };
    searchEventosInput.addEventListener('input', debounce(filterEventos, 150));
  }

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

                  // Actualizar el estilo del texto de la tarea
                  const tareaTexto = this.nextElementSibling;
                  if (tareaTexto) {
                      if (completada) {
                          tareaTexto.classList.add('text-gray-500', 'line-through');
                          tareaTexto.classList.remove('text-gray-800');
                      } else {
                          tareaTexto.classList.remove('text-gray-500', 'line-through');
                          tareaTexto.classList.add('text-gray-800');
                      }
                  }

                  // 🔹 Modo 1: card grande (para vista de tareas)
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
            .catch(err => {
              console.error(err);
              alert('No se pudo cargar la vista del evento');
            });
        });

            // Ensure create buttons navigate to the form even if something else intercepts clicks
            document.addEventListener('click', function(e) {
              const a = e.target.closest && e.target.closest('a[href]');
              if (!a) return;
              const href = a.getAttribute('href') || '';
              if (href.includes('/eventos/nuevo') || href.includes('/tareas/nueva')) {
                e.preventDefault();
                // force navigation
                window.location.href = href;
              }
            });

});

// ------------------------
// Modal: Ver / Editar / Eliminar evento
// ------------------------
document.addEventListener('click', function (e) {
  // abrir modal desde botones con clase .btn-view-event, .link-view-event, .btn-view-task
  const target = e.target.closest && e.target.closest('.btn-view-event, .link-view-event, .btn-view-task');
  if (!target) return;
  e.preventDefault();
  const id = target.getAttribute('data-id');
  // determine type (evento/tarea)
  const type = target.getAttribute('data-type') || (target.classList.contains('btn-view-task') ? 'tarea' : 'evento');
  if (!id) return;

  const basePath = type === 'tarea' ? 'tareas' : 'eventos';
  fetch(`/${basePath}/${id}/ver`)
    .then(r => {
      if (!r.ok) throw new Error('No se cargó el evento');
      return r.text();
    })
    .then(html => {
      // insertar fragmento y enlazar handlers
      const wrapper = document.createElement('div');
      wrapper.innerHTML = html;
      document.body.appendChild(wrapper);

      // support both ids used previously
      const overlay = document.getElementById('item-modal-overlay') || document.getElementById('evento-modal-overlay');
      if (!overlay) return;

  const closeBtn = overlay.querySelector('#modal-close');
      const editBtn = overlay.querySelector('#modal-edit');
      const saveBtn = overlay.querySelector('#modal-save');
      const cancelBtn = overlay.querySelector('#modal-cancel');
      const deleteBtn = overlay.querySelector('#modal-delete');
      const form = overlay.querySelector('#modal-form');

      // save original values so we can restore on cancel
      const originalValues = {};
      // store original values for inputs, textareas and selects
      Array.from(form.querySelectorAll('input, textarea, select')).forEach(i => {
        originalValues[i.name] = i.value;
      });

      function closeModal() {
        // remove wrapper (which contains overlay)
        wrapper.remove();
      }

      closeBtn && closeBtn.addEventListener('click', closeModal);
      overlay.addEventListener('click', (ev) => {
        if (ev.target === overlay) closeModal();
      });

      // Edit: enable inputs/selects and switch buttons (use inline styles for compatibility)
      editBtn && editBtn.addEventListener('click', () => {
        Array.from(form.querySelectorAll('input, textarea')).forEach(i => i.removeAttribute('readonly'));
        Array.from(form.querySelectorAll('select')).forEach(s => s.removeAttribute('disabled'));
        // show/hide buttons
        editBtn.style.display = 'none';
        saveBtn.style.display = '';
        cancelBtn.style.display = '';
      });

      // Cancel: restore original values and set readonly/disabled
      cancelBtn && cancelBtn.addEventListener('click', () => {
        Array.from(form.querySelectorAll('input, textarea, select')).forEach(i => {
          if (Object.prototype.hasOwnProperty.call(originalValues, i.name)) {
            i.value = originalValues[i.name];
          }
          if (i.tagName.toLowerCase() === 'select') {
            i.setAttribute('disabled', '');
          } else {
            i.setAttribute('readonly', '');
          }
        });
        // show/hide buttons
        saveBtn.style.display = 'none';
        cancelBtn.style.display = 'none';
        editBtn.style.display = '';
      });

      // Save: send PUT and refresh
      saveBtn && saveBtn.addEventListener('click', () => {
        const formData = new FormData(form);
        const payload = {
          nombre: formData.get('nombre') || '',
          descripcion: formData.get('descripcion') || '',
          fecha_evento: formData.get('fecha_evento') || '',
          hora_evento: formData.get('hora_evento') || '',
          fecha_fin: formData.get('fecha_fin') || null,
          hora_fin: formData.get('hora_fin') || null
        };

        if (type === 'tarea') {
          // add task-specific fields
          payload.prioridad = formData.get('prioridad') || '1';
          payload.estado = formData.get('estado') || '0';
        }

        // Choose endpoint depending on item type
        const saveUrl = type === 'tarea' ? `/api/tareas/${id}` : `/api/eventos/${id}`;
        fetch(saveUrl, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        .then(r => {
          if (!r.ok) return r.json().then(j => Promise.reject(j));
          return r.json();
        })
        .then((data) => {
          // use server-returned object to update DOM (server-authoritative)
          try {
            let normalized = {};
            if (type === 'evento') {
              normalized.nombre = data.Nombre || data.nombre || payload.nombre;
              normalized.descripcion = data.Descripcion || data.descripcion || payload.descripcion || '';
              normalized.fecha_evento = data.Fecha_evento || data.fecha_evento || payload.fecha_evento || '';
              normalized.hora_evento = (data.Hora_evento || data.hora_evento || payload.hora_evento || '').toString().slice(0,5);
              normalized.fecha_fin = data.Fecha_fin || data.fecha_fin || payload.fecha_fin || null;
              normalized.hora_fin = (data.Hora_fin || data.hora_fin || payload.hora_fin || '').toString().slice(0,5);
            } else {
              // tarea
              normalized.nombre = data.Nombre || data.nombre || payload.nombre;
              normalized.descripcion = data.Descripcion || data.descripcion || payload.descripcion || '';
              normalized.fecha_evento = data.Fecha_limite || data.Fecha_evento || data.fecha_evento || payload.fecha_evento || '';
              normalized.hora_evento = '';
              normalized.prioridad = (data.Prioridad || data.prioridad || payload.prioridad || '1').toString();
              normalized.estado = (data.Estado || data.estado || payload.estado || '0').toString();
            }
            const updated = updateItemInDOM(type, id, normalized);
            if (!updated) {
              // fallback: if we couldn't find the card to update, reload to reflect changes
              showToast('Guardado. Recargando para actualizar la vista...', 'info');
              closeModal();
              location.reload();
              return;
            }
            showToast('Guardado correctamente', 'success');
          } catch (e) {
            console.warn('No se pudo actualizar el DOM localmente', e);
          }
          closeModal();
        })
        .catch(err => {
          console.error('Error guardando', err);
          alert((err && err.error) || 'Error al guardar el item');
        });
      });

      // Delete: POST delete route
      deleteBtn && deleteBtn.addEventListener('click', () => {
        if (!confirm('¿Eliminar este elemento? Esta acción no se puede deshacer.')) return;
        const basePath = type === 'tarea' ? 'tareas' : 'eventos';
        fetch(`/${basePath}/${id}/eliminar`, { method: 'POST' })
          .then(r => {
            if (!r.ok) throw new Error('No se pudo eliminar');
            return r.text();
          })
          .then(() => { 
              try {
                removeItemFromDOM(type, id);
                showToast('Elemento eliminado', 'success');
              } catch (e) {
                console.warn('No se pudo eliminar elemento del DOM', e);
              }
              closeModal();
            })
            .catch(err => { console.error(err); alert('Error al eliminar el elemento'); });
      });

      // If the trigger requested to open in edit mode, activate edit immediately
      if (target.getAttribute && target.getAttribute('data-action') === 'edit') {
        editBtn && editBtn.click();
      }

    })
    .catch(err => {
      console.error(err);
      alert('No se pudo cargar la vista del evento');
    });
})
});
