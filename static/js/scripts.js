/**
 * SCRIPTS.JS - JavaScript Principal del Proyecto
 * 
 * Responsabilidad: Orquestar toda la interacción cliente (UX y sincronización ligera)
 * sin framework adicional. Mantiene el DOM consistente frente a cambios de estado
 * usando "optimistic updates" y sólo recarga cuando es estrictamente necesario.
 * 
 * Incluye:
 * - Calendario (FullCalendar) + drag & drop + resize + creación rápida.
 * - Búsqueda en vivo (eventos / tareas) con debounce.
 * - Actualización de estado de tareas (checkbox) + contador.
 * - Sistema de modales reutilizable (ver / editar / eliminar) inyectado dinámicamente.
 * - Toasts ligeros para feedback inmediato.
 * 
 * Patrones clave:
 * - "Prefijos de ID": Las tareas en el calendario se distinguen por id "t-<id>".
 * - "Server authoritative" tras guardar: se normalizan datos usando la respuesta del backend.
 * - "Optimistic UI": Se modifica el DOM antes de confirmación del servidor y se revierte si falla.
 * - "Single overlay policy": Antes de abrir un modal se elimina cualquier overlay previo para evitar fugas.
 * 
 * Estructura del archivo:
 * 1. Helpers globales (toast, updateItemInDOM, removeItemFromDOM).
 * 2. FullCalendar: configuración, ciclo de vida y sincronización con API.
 * 3. Live Search: filtros instantáneos con debounce.
 * 4. Checkboxes de tareas: estado + feedback + reversión.
 * 5. Modales dinámicos: ver / editar / eliminar.
 */

// ============================================================================
// SECCIÓN 1: FUNCIONES HELPER GLOBALES
// ============================================================================
// Estas funciones están en el scope global para ser accesibles desde todos 
// los event listeners y handlers, incluyendo los que se crean dinámicamente

/**
 * Muestra una notificación temporal en la esquina superior derecha
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo de toast: 'success', 'error', 'info'
 */
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

/**
 * Actualiza un evento o tarea en el DOM sin recargar la página
 * Implementa "optimistic updates" para una experiencia más fluida
 * 
 * @param {string} type - Tipo de item: 'evento' o 'tarea'
 * @param {string|number} id - ID del elemento a actualizar
 * @param {Object} payload - Objeto con los nuevos datos del elemento
 * @returns {boolean} - true si se actualizó correctamente, false si no se encontró el elemento
 */
function updateItemInDOM(type, id, payload) {
  if (type === 'evento') {
    // --- ACTUALIZACIÓN DE EVENTOS ---
    // Buscar el botón del evento en el DOM
    const btn = document.querySelector(`.btn-view-event[data-id="${id}"]`);
    if (!btn) {
      console.warn('No se encontró el botón del evento para actualizar');
      return false;
    }
    // Navegar al contenedor del card
    const card = btn.closest('.flex.flex-col.items-stretch') || btn.closest('[class*="p-4"]');
    if (!card) {
      console.warn('No se encontró el contenedor del evento');
      return false;
    }
    
    // Actualizar título del evento
    const title = card.querySelector('p.text-text-light.text-lg.font-bold') || card.querySelector('p.text-lg') || card.querySelector('h3');
    if (title && payload.nombre) {
      title.textContent = payload.nombre;
    }
    
    // Actualizar fecha - buscar el párrafo que contiene el icono calendar_today
    const parrafos = card.querySelectorAll('p.text-gray-500.text-sm');
    if (parrafos && parrafos.length >= 2) {
      // Primer párrafo: fecha (icono calendar_today)
      if (payload.fecha_evento) {
        const fechaText = parrafos[0].childNodes;
        // El texto está después del span del icono
        if (fechaText.length > 1) {
          fechaText[fechaText.length - 1].textContent = ' ' + payload.fecha_evento;
        }
      }
      // Segundo párrafo: hora (icono schedule)
      if (payload.hora_evento) {
        const horaText = parrafos[1].childNodes;
        if (horaText.length > 1) {
          const horaFormateada = payload.hora_evento.toString().slice(0, 5);
          horaText[horaText.length - 1].textContent = ' ' + horaFormateada;
        }
      }
    }
    return true;
  }

  if (type === 'tarea') {
    // --- ACTUALIZACIÓN DE TAREAS ---
    // Intentar localizar la tarea: preferir checkbox, sino botón de ver/editar
    let anchor = document.querySelector(`.tarea-checkbox[data-tarea-id="${id}"]`);
    if (!anchor) anchor = document.querySelector(`.btn-view-task[data-id="${id}"]`);
    if (!anchor) anchor = document.querySelector(`[data-id="${id}"]`);
    if (!anchor) {
      console.warn('No se encontró la tarea para actualizar');
      return false;
    }
    
    // Buscar el contenedor de la fila (nueva estructura con flex)
    let row = anchor.closest('.flex.items-center.gap-4');
    if (!row) {
      // fallback: estructura antigua con cards
      row = anchor.closest('.card');
    }
    if (!row) {
      console.warn('No se encontró el contenedor de la tarea');
      return false;
    }

    // Actualizar título (h3)
    const title = row.querySelector('h3.text-lg') || row.querySelector('.card-title') || row.querySelector('h6') || row.querySelector('h5');
    if (title && payload.nombre) {
      title.textContent = payload.nombre;
      // mantener estilo de línea si está completada
      const isCompleted = title.classList.contains('line-through');
      if (!isCompleted && payload.estado && parseInt(payload.estado) === 1) {
        title.classList.add('line-through', 'text-gray-500');
      } else if (isCompleted && (!payload.estado || parseInt(payload.estado) === 0)) {
        title.classList.remove('line-through', 'text-gray-500');
      }
    }
    
    // Actualizar descripción
    const desc = row.querySelector('p.text-gray-500.text-sm.mt-1') || row.querySelector('.card-text') || row.querySelector('p.text-secondary');
    if (desc && payload.descripcion !== undefined) {
      desc.textContent = payload.descripcion;
    }
    
    // Actualizar fecha
    const fechaSpan = row.querySelector('span.flex.items-center.text-gray-500') || row.querySelector('span.text-secondary');
    if (fechaSpan && payload.fecha_evento) {
      // El texto está después del icono
      const textNode = Array.from(fechaSpan.childNodes).find(n => n.nodeType === Node.TEXT_NODE);
      if (textNode) {
        textNode.textContent = ' ' + payload.fecha_evento;
      }
    }
    
    // Actualizar badge de prioridad
    if (payload.prioridad) {
      const prioBadges = row.querySelectorAll('span.inline-flex.items-center.px-2\\.5');
      const prioBadge = prioBadges[0]; // el primero suele ser prioridad
      if (prioBadge) {
        const p = parseInt(payload.prioridad, 10);
        prioBadge.textContent = p === 1 ? 'Baja' : (p === 2 ? 'Media' : 'Alta');
        // actualizar colores
        prioBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ';
        if (p === 1) {
          prioBadge.className += 'bg-green-100 text-green-800';
        } else if (p === 2) {
          prioBadge.className += 'bg-blue-100 text-blue-800';
        } else {
          prioBadge.className += 'bg-yellow-100 text-yellow-800';
        }
      }
    }
    
    // Actualizar badge de estado
    if (payload.estado !== undefined) {
      const badges = row.querySelectorAll('span.inline-flex.items-center.px-2\\.5');
      const estadoBadge = badges.length > 1 ? badges[badges.length - 1] : null; // el último suele ser estado
      if (estadoBadge) {
        const estado = parseInt(payload.estado, 10);
        estadoBadge.textContent = estado === 1 ? 'Completada' : 'Pendiente';
        estadoBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ';
        estadoBadge.className += estado === 1 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800';
      }
    }
    
    return true;
  }

  return false;
}

/**
 * Elimina un elemento (evento o tarea) del DOM después de ser eliminado del servidor
 * Navega por la estructura del DOM para encontrar y eliminar el contenedor completo
 * 
 * @param {string} type - Tipo de item: 'evento' o 'tarea'
 * @param {string|number} id - ID del elemento a eliminar
 */
function removeItemFromDOM(type, id) {
  if (type === 'evento') {
    // --- ELIMINACIÓN DE EVENTOS ---
    const btn = document.querySelector(`.btn-view-event[data-id="${id}"]`);
    if (!btn) {
      console.warn('No se encontró el botón del evento en el DOM');
      return;
    }
    // Buscar el contenedor navegando hacia arriba desde el botón
    // La estructura es: div.p-4 > div.flex (card) > div (contenido) > div (botones) > button
    // Subimos 5 niveles para llegar al .p-4
    let container = btn.parentElement; // div de botones
    if (container) container = container.parentElement; // div de contenido
    if (container) container = container.parentElement; // div.flex (card completo)
    if (container) container = container.parentElement; // div.p-4
    
    if (container) {
      console.log('Eliminando contenedor del evento (método parentElement):', container);
      container.remove();
      return;
    }
    
    // fallback: buscar por clase
    console.warn('Método parentElement falló, intentando con closest');
    container = btn.closest('[class*="p-4"]');
    if (container) {
      console.log('Eliminando contenedor del evento (método closest):', container);
      container.remove();
      return;
    }
    
    console.error('No se pudo encontrar el contenedor para eliminar');
    return;
  }
  if (type === 'tarea') {
    // --- ELIMINACIÓN DE TAREAS ---
    const checkbox = document.querySelector(`.tarea-checkbox[data-tarea-id="${id}"]`);
    if (!checkbox) {
      console.warn('No se encontró el checkbox de la tarea en el DOM');
      return;
    }
    // En tareas la estructura es un div.flex que contiene todo
    const row = checkbox.closest('.flex.items-center.gap-4');
    if (row) {
      row.remove();
      return;
    }
    // fallback para estructura antigua con cards
    const card = checkbox.closest('.card');
    if (card) card.remove();
  }
}

// ============================================================================
// SECCIÓN 2: INICIALIZACIÓN DEL CALENDARIO (FullCalendar)
// ============================================================================
// Configuración y renderizado del calendario interactivo con drag & drop y resize.
// Ciclo de vida:
//   - Se inicializa en DOMContentLoaded si existe #calendar.
//   - Obtiene datos desde /api/eventos (que mezcla eventos y tareas).
//   - Al mover (drop/resize) se envía PUT inmediato (sin modal) para persistir.
//   - Se distinguen tareas vs eventos por prefijo de id ("t-"), evitando más
//     llamadas de detalle para categorizar.
// Notas de rendimiento:
//   - Refetch de eventos tras crear/editar para asegurar coherencia sin recargar.
//   - Posible mejora futura: aplicar cache por rango + parámetros start/end ya soportados.

document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('calendar');
  if (!calendarEl) return;

  // ================= FULLCALENDAR RESET BÁSICO =================
  // Configuración mínima y clara: muestra todos los eventos, permite moverlos
  // entre días y abre el modal de detalle al hacer click.
  const calendar = new FullCalendar.Calendar(calendarEl, {
    locale: 'es',
    initialView: 'dayGridMonth',
    firstDay: 1,
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,timeGridDay'
    },
    height: 760,
    editable: true,          // permite drag & drop
    selectable: true,
    // Rango de horas visible en vistas semana/día
    slotMinTime: '06:00:00',      // empezar a las 06:00
    slotMaxTime: '24:00:00',      // mostrar hasta medianoche (FullCalendar corta slots vacíos al final)
    scrollTime: '06:00:00',       // al entrar en vista week/day hace scroll inicial a las 06:00
    slotDuration: '00:30:00',     // intervalos de media hora (puedes cambiar a '01:00:00')
    slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
  events: '/api/eventos',  // ahora devuelve eventos + tareas (ver backend)
    eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },

    // Crear nuevo evento al hacer click en un día vacío -> modal rápido
    dateClick: function(info) {
      abrirModalCreacionRapida(info.dateStr);
    },

    // Abrir modal de evento o tarea directamente al hacer click
    eventClick: function(info) {
      const tmp = document.createElement('button');
      tmp.style.display = 'none';
      
      // Detectar si es tarea o evento por el prefijo del ID
      // RACIONAL: Reutilizamos el mismo listener delegado de modales que espera
      // botones con clases .btn-view-event / .btn-view-task. En lugar de duplicar
      // lógica aquí, creamos un botón oculto, disparamos el click y luego lo
      // eliminamos. Esto mantiene un único flujo de apertura de modales.
      const eventId = info.event.id;
      const isTarea = eventId.startsWith('t-');
      
      if (isTarea) {
        // Es una tarea - extraer el ID numérico (quitar el prefijo 't-')
        const tareaId = eventId.substring(2);
        tmp.className = 'btn-view-task';
        tmp.setAttribute('data-id', tareaId);
        tmp.setAttribute('data-type', 'tarea');
      } else {
        // Es un evento
        tmp.className = 'btn-view-event';
        tmp.setAttribute('data-id', eventId);
        tmp.setAttribute('data-type', 'evento');
      }
      
      document.body.appendChild(tmp);
      tmp.click();
      tmp.remove();
    },

    // Drag & drop: mover a otro día (o semana/día). Persistir sin confirmación.
    eventDrop: function(info) {
      actualizarEventoDesdeCalendario(info, false);
    },

    // Resize opcional (si se usan rangos de tiempo). Se mantiene para coherencia.
    eventResize: function(info) {
      actualizarEventoDesdeCalendario(info, true);
    }
  });

  calendar.render();
  // Exponer para otros handlers (edición) y refetch
  window.calendar = calendar;

  // ============== MODAL CREACIÓN RÁPIDA ==============
  function abrirModalCreacionRapida(fechaStr) {
    // Evitar abrir múltiples modales
    if (document.getElementById('quick-event-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'quick-event-overlay';
    overlay.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[1060] animate-[fadeIn_0.25s_ease]';

    const modal = document.createElement('div');
    modal.className = 'relative bg-white w-full max-w-lg rounded-2xl shadow-2xl p-6 overflow-hidden animate-[slideUp_0.35s_ease]';
    modal.innerHTML = `
      <div class="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 -m-6 mb-6 px-6 py-4 rounded-t-2xl flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="material-symbols-outlined text-white text-3xl">event</span>
          <h3 class="text-white text-xl font-semibold m-0">Nuevo evento rápido</h3>
        </div>
        <button type="button" id="quick-close" class="text-white/80 hover:text-white transition" aria-label="Cerrar">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>
      <form id="quick-event-form" class="space-y-4">
        <div>
          <label class="block text-sm font-semibold text-gray-700 mb-1">Nombre *</label>
          <input name="nombre" type="text" maxlength="100" required
            class="w-full rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2 text-gray-900 placeholder-gray-400" placeholder="Reunión semanal" />
        </div>
        <div>
          <label class="block text-sm font-semibold text-gray-700 mb-1">Descripción</label>
          <textarea name="descripcion" rows="2" maxlength="500"
            class="w-full rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2 text-gray-900 placeholder-gray-400 resize-none" placeholder="Opcional"></textarea>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-semibold text-gray-700 mb-1">Fecha inicio *</label>
            <input name="fecha_evento" type="date" value="${fechaStr}" required
              class="w-full rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2 text-gray-900" />
          </div>
          <div>
            <label class="block text-sm font-semibold text-gray-700 mb-1">Fecha fin</label>
            <input name="fecha_fin" type="date"
              class="w-full rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2 text-gray-900" />
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-semibold text-gray-700 mb-1">Hora inicio</label>
            <input name="hora_evento" type="time"
              class="w-full rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2 text-gray-900" />
          </div>
          <div>
            <label class="block text-sm font-semibold text-gray-700 mb-1">Hora fin</label>
            <input name="hora_fin" type="time"
              class="w-full rounded-lg border border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2 text-gray-900" />
          </div>
        </div>
        <div id="quick-error" class="hidden rounded-lg border border-red-300 bg-red-50 text-red-700 text-sm px-3 py-2"></div>
        <div class="flex justify-end gap-3 pt-2">
          <button type="button" id="quick-cancel" class="px-4 py-2 rounded-lg bg-gray-200 text-gray-700 hover:bg-gray-300 transition font-medium">Cancelar</button>
          <button type="submit" class="px-5 py-2 rounded-lg bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white font-semibold shadow hover:from-blue-500 hover:via-indigo-500 hover:to-purple-500 focus:ring-2 focus:ring-indigo-500 transition">Crear evento</button>
        </div>
        <p class="text-xs text-gray-500">Puedes editar más detalles después haciendo click en el evento.</p>
      </form>
    `;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Cerrar
    const cerrar = () => overlay.remove();
    modal.querySelector('#quick-close').addEventListener('click', cerrar);
    modal.querySelector('#quick-cancel').addEventListener('click', cerrar);
    overlay.addEventListener('click', e => { if (e.target === overlay) cerrar(); });

    // Submit
    const form = modal.querySelector('#quick-event-form');
    form.addEventListener('submit', function(e){
      e.preventDefault();
      const fd = new FormData(form);
      const nombre = (fd.get('nombre') || '').trim();
      if (!nombre) {
        mostrarError('El nombre es obligatorio');
        return;
      }
      if (nombre.length < 3) { mostrarError('Nombre mínimo 3 caracteres'); return; }
      const fecha_evento = fd.get('fecha_evento');
      const hora_evento = fd.get('hora_evento') || '00:00';
      const fecha_fin = fd.get('fecha_fin') || null;
      const hora_fin = fd.get('hora_fin') || null;
      const descripcion = (fd.get('descripcion') || '').trim();

      // Validación simple hora fin > inicio si ambas
      if (hora_evento && hora_fin) {
        if (hora_fin <= hora_evento) { mostrarError('Hora fin debe ser posterior'); return; }
      }
      // Validación simple fecha fin >= inicio
      if (fecha_fin && fecha_fin < fecha_evento) { mostrarError('Fecha fin debe ser posterior'); return; }

      const payload = { nombre, fecha_evento, hora_evento, fecha_fin: fecha_fin || null, hora_fin: hora_fin || null, descripcion };
      fetch('/api/eventos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(r => r.json().then(j => ({ ok: r.ok, body: j })))
      .then(res => {
        if (!res.ok) { mostrarError(res.body.error || 'Error creando evento'); return; }
        // Recargar eventos desde servidor para asegurar coherencia
        if (window.calendar) window.calendar.refetchEvents();
        showToast('Evento creado', 'success');
        cerrar();
      })
      .catch(err => { console.error(err); mostrarError('Error de red creando evento'); });
    });

    function mostrarError(msg){
      const box = modal.querySelector('#quick-error');
      box.textContent = msg;
      box.classList.remove('hidden');
    }
  }

  // --- FUNCIÓN AUXILIAR: Formatear fecha/hora ---
  // Convierte un objeto Date en formato separado para fecha y hora
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

  /**
     * Actualiza un evento o tarea en el servidor después de drag/drop o resize
   * Valida fechas y envía PUT request al backend
   * 
   * @param {Object} info - Información del evento de FullCalendar
   * @param {boolean} esResize - true si es un resize, false si es drag
   */
  function actualizarEventoDesdeCalendario(info, esResize) {
    const event = info.event;
      const eventId = event.id;
      const isTarea = eventId.startsWith('t-');
      const numericId = isTarea ? eventId.substring(2) : eventId;
      // RACIONAL: Prefijo "t-" evita colisiones numéricas y permite distinguir
      // la naturaleza del item sin propiedades adicionales en FullCalendar.

    const startParts = splitDateTime(event.start);
    let endParts = null;
    if (event.end) {
      endParts = splitDateTime(event.end);
    } else if (esResize) {
      // Si se intenta resize pero no hay fecha fin previa, calcular una por defecto (30 min)
      const fallbackEnd = new Date(event.start.getTime() + 30 * 60 * 1000);
      endParts = splitDateTime(fallbackEnd);
      // RACIONAL: Proporcionar un fin sintético evita revert inmediato y
      // ofrece una duración mínima coherente para eventos redimensionados.
    }

    // Validación: la fecha/hora de fin no puede ser anterior o igual al inicio
    if (endParts) {
      const startDate = new Date(`${startParts.fecha}T${startParts.hora}`);
      const endDate = new Date(`${endParts.fecha}T${endParts.hora}`);
      if (endDate <= startDate) {
        alert('La fecha/hora de fin no puede ser anterior o igual a la de inicio.');
        info.revert();
        return;
      }
    }

      // Construir payload según si es tarea o evento
      let endpoint, payload;
    
      if (isTarea) {
        // Para tareas: actualizar fecha_limite y hora_evento
        endpoint = `/api/tareas/${numericId}`;
        payload = {
          nombre: event.title,
          fecha_limite: startParts.fecha,
          hora_evento: startParts.hora || null,
          prioridad: event.extendedProps?.prioridad || 'media',
          estado: event.extendedProps?.estado || 'pendiente',
          descripcion: event.extendedProps?.descripcion || null
        };
      } else {
        // Para eventos: actualizar con fecha_evento, hora_evento, fecha_fin, hora_fin
        endpoint = `/api/eventos/${numericId}`;
        payload = {
          nombre: event.title,
          fecha_evento: startParts.fecha,
          hora_evento: startParts.hora,
          fecha_fin: endParts ? endParts.fecha : null,
          hora_fin: endParts ? endParts.hora : null,
          descripcion: event.extendedProps?.descripcion || null
        };
      }
      // NOTA: Se confía en datos "extendedProps" existentes; si el backend cambia
      // estructura la UI seguirá funcionando (gracia a valores por defecto).

    // Enviar actualización al servidor
      fetch(endpoint, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(r => {
      if (!r.ok) throw new Error('Error al actualizar en servidor');
      return r.json();
    })
    .then(data => {
        // Actualizado correctamente
        showToast(isTarea ? 'Tarea actualizada' : 'Evento actualizado', 'success');
    })
    .catch(err => {
      console.error(err);
        alert('No se pudo actualizar. Se revierte el cambio.');
      info.revert(); // Revertir cambios visuales si falla el servidor
    });
  }
});

// ============================================================================
// SECCIÓN 3: BÚSQUEDA EN VIVO (Live Search)
// ============================================================================
// Filtrado en tiempo real de tareas y eventos según el texto de búsqueda
// Utiliza debounce para reducir trabajo en cada pulsación (actual 150ms).
// Escala O(n) sobre elementos renderizados; si el volumen creciera se podría
// migrar a filtrado por atributos data-* o preindexación.

document.addEventListener('DOMContentLoaded', function() {
  // Función debounce para evitar ejecuciones excesivas durante escritura rápida
  const debounce = (fn, ms = 150) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  };

  // --- BÚSQUEDA EN TAREAS ---
  // Filtra las filas dentro de #tareas-list según el texto ingresado
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

  // --- BÚSQUEDA EN EVENTOS ---
  // Filtra las tarjetas dentro de #eventos-grid según el texto ingresado
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

  // ============================================================================
  // SECCIÓN 4: GESTIÓN DE CHECKBOXES DE TAREAS
  // ============================================================================
  // Maneja el cambio de estado de tareas (completada/pendiente)
  // Implementa "optimistic updates" aplicando clases y badges antes de respuesta.
  // Si el servidor falla se revierte completamente el DOM, manteniendo consistencia.
  // Funciona tanto en tareas.html como en dashboard.html

  document.querySelectorAll('.tarea-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      const tareaId = this.getAttribute('data-tarea-id');
      const completada = this.checked;
      const estado = completada ? 1 : 0;
      
      // Buscar el contenedor de la tarea (tareas.html usa gap-4, dashboard.html usa gap-3)
      const tareaRow = this.closest('.flex.items-center.gap-4') || this.closest('.flex.items-center.gap-3');
      
      // Actualizar estilos INMEDIATAMENTE antes de enviar al servidor (optimistic update)
      // Esto proporciona feedback instantáneo al usuario
      if (tareaRow) {
        // Actualizar título (h3 en tareas.html o p en dashboard.html)
        const title = tareaRow.querySelector('h3.text-lg') || tareaRow.querySelector('p');
        if (title) {
          if (completada) {
            title.classList.add('line-through', 'text-gray-500');
            title.classList.remove('text-gray-900', 'text-gray-800');
          } else {
            title.classList.remove('line-through', 'text-gray-500');
            // Restaurar color original (gray-900 en tareas.html, gray-800 en dashboard)
            if (!title.classList.contains('text-gray-900') && !title.classList.contains('text-gray-800')) {
              title.classList.add('text-gray-800');
            }
          }
        }
        
        // Actualizar descripción (solo presente en tareas.html, no en dashboard)
        const desc = tareaRow.querySelector('p.text-gray-500.text-sm.mt-1');
        if (desc) {
          if (completada) {
            desc.classList.add('line-through');
          } else {
            desc.classList.remove('line-through');
          }
        }
        
        // Actualizar badge de estado (solo presente en tareas.html, no en dashboard)
        const estadoBadges = tareaRow.querySelectorAll('span.inline-flex.items-center.px-2\\.5');
        const estadoBadge = Array.from(estadoBadges).find(badge => 
          badge.textContent.includes('Completada') || badge.textContent.includes('Pendiente')
        );
        if (estadoBadge) {
          estadoBadge.textContent = completada ? 'Completada' : 'Pendiente';
          if (completada) {
            estadoBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800';
          } else {
            estadoBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800';
          }
        }
      }
      
      // Enviar actualización al servidor
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

        // Actualizar contador de tareas completadas (si existe)
        const contador = document.getElementById('contador-tareas');
        if (contador) {
          let [actualCompletadas, total] = contador.textContent.split('/').map(Number);
          if (completada) {
            actualCompletadas += 1;
          } else {
            actualCompletadas -= 1;
          }
          contador.textContent = `${actualCompletadas}/${total}`;
        }
        
        // Mostrar confirmación breve
        showToast(completada ? 'Tarea completada' : 'Tarea reactivada', 'success');
      })
      .catch(err => {
        console.error(err);
        // --- REVERSIÓN DE CAMBIOS ---
        // Si el servidor falla, revertir todos los cambios visuales
        this.checked = !completada;
        if (tareaRow) {
          const title = tareaRow.querySelector('h3.text-lg');
          const desc = tareaRow.querySelector('p.text-gray-500.text-sm');
          const estadoBadges = tareaRow.querySelectorAll('span.inline-flex.items-center.px-2\\.5');
          const estadoBadge = Array.from(estadoBadges).find(badge => 
            badge.textContent.includes('Completada') || badge.textContent.includes('Pendiente')
          );
          
          if (title) {
            if (!completada) {
              title.classList.add('line-through', 'text-gray-500');
              title.classList.remove('text-gray-900');
            } else {
              title.classList.remove('line-through', 'text-gray-500');
              title.classList.add('text-gray-900');
            }
          }
          
          if (desc) {
            if (!completada) {
              desc.classList.add('line-through');
            } else {
              desc.classList.remove('line-through');
            }
          }
          
          if (estadoBadge) {
            estadoBadge.textContent = !completada ? 'Completada' : 'Pendiente';
            if (!completada) {
              estadoBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800';
            } else {
              estadoBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800';
            }
          }
        }
        showToast('Error al actualizar el estado de la tarea', 'error');
      });
    });
  });
});

// ============================================================================
// SECCIÓN 5: SISTEMA DE MODALES (Ver / Editar / Eliminar)
// ============================================================================
// Gestiona la apertura y funcionalidad de modales para eventos y tareas
// Utiliza event delegation para capturar clicks en botones dinámicos
// Soporta modo visualización y edición con validación de datos.
// Memoria / Limpieza: Antes de inyectar un nuevo modal se elimina el wrapper
// previo (single overlay) evitando acumulación de nodos no referenciados.
// Mejorable: Podría centralizarse en un ModalManager para reutilizar transiciones.

// Event listener delegado a nivel de documento para capturar clicks en botones de ver/editar
document.addEventListener('click', function (e) {
  // Buscar si el click fue en un botón de ver evento/tarea
  const target = e.target.closest && e.target.closest('.btn-view-event, .link-view-event, .btn-view-task');
  if (!target) return;
  e.preventDefault();
  const id = target.getAttribute('data-id');
  // Determinar el tipo (evento/tarea) según atributo o clase del botón
  const type = target.getAttribute('data-type') || (target.classList.contains('btn-view-task') ? 'tarea' : 'evento');
  if (!id) return;

  // Construir la ruta del endpoint para obtener el fragmento HTML del modal
  const basePath = type === 'tarea' ? 'tareas' : 'eventos';
  fetch(`/${basePath}/${id}/ver`)
    .then(r => {
      if (!r.ok) throw new Error('No se cargó el evento');
      return r.text();
    })
    .then(html => {
      // Evitar duplicados: si ya hay un overlay previo, eliminar su contenedor
      const existingOverlay = document.getElementById('item-modal-overlay');
      if (existingOverlay && existingOverlay.parentElement) {
        existingOverlay.parentElement.remove();
      }
      // Insertar el nuevo fragmento HTML del modal en el documento
      const wrapper = document.createElement('div');
      wrapper.innerHTML = html;
      document.body.appendChild(wrapper);

      // Obtener referencias a los elementos del modal (soporta ambos IDs por compatibilidad)
      const overlay = document.getElementById('item-modal-overlay') || document.getElementById('evento-modal-overlay');
      if (!overlay) return;

      // Obtener referencias a los botones y formulario del modal
  const closeBtn = overlay.querySelector('#modal-close');
      const editBtn = overlay.querySelector('#modal-edit');
      const saveBtn = overlay.querySelector('#modal-save');
      const cancelBtn = overlay.querySelector('#modal-cancel');
      const deleteBtn = overlay.querySelector('#modal-delete');
      const form = overlay.querySelector('#modal-form');

      // Guardar valores originales del formulario para restaurar en caso de cancelar
      const originalValues = {};
      // Almacenar valores originales de inputs, textareas y selects
      Array.from(form.querySelectorAll('input, textarea, select')).forEach(i => {
        originalValues[i.name] = i.value;
      });

      // --- FUNCIÓN: Cerrar modal ---
      function closeModal() {
        // Eliminar el wrapper (que contiene el overlay y todo el modal)
        wrapper.remove();
      }

      // Event listeners para cerrar el modal
      closeBtn && closeBtn.addEventListener('click', closeModal);
      
      // Cerrar modal al hacer clic fuera del contenido (single click)
      overlay.addEventListener('click', (ev) => {
        if (ev.target === overlay) {
          closeModal();
        }
      });

      // --- BOTÓN EDITAR: Activar modo edición ---
      // Habilita inputs/selects y cambia botones visibles
      editBtn && editBtn.addEventListener('click', () => {
        Array.from(form.querySelectorAll('input, textarea')).forEach(i => i.removeAttribute('readonly'));
        Array.from(form.querySelectorAll('select')).forEach(s => s.removeAttribute('disabled'));
        // Mostrar/ocultar botones usando clases de Tailwind
        editBtn.classList.add('hidden');
        saveBtn.classList.remove('hidden');
        saveBtn.classList.add('flex');
        cancelBtn.classList.remove('hidden');
        cancelBtn.classList.add('flex');
      });

      // --- BOTÓN CANCELAR: Restaurar valores originales y cerrar modal ---
      // Revierte cambios no guardados y cierra el modal
      cancelBtn && cancelBtn.addEventListener('click', () => {
        closeModal();
      });

  // --- BOTÓN GUARDAR: Enviar cambios al servidor ---
  // Construye payload y envía PUT request. Ahora, tras guardar siempre recargamos la vista
  // para evitar estados inconsistentes en listados (petición del usuario).
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
          // Añadir campos específicos de tareas
          payload.prioridad = formData.get('prioridad') || '1';
          payload.estado = formData.get('estado') || '0';
        }

        // Elegir endpoint según el tipo de item
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
          // Usar el objeto devuelto por el servidor para actualizar el DOM (server-authoritative)
          try {
            let normalized = {};
            if (type === 'evento') {
              // Normalizar datos de evento desde la respuesta del servidor
              normalized.nombre = data.Nombre || data.nombre || payload.nombre;
              normalized.descripcion = data.Descripcion || data.descripcion || payload.descripcion || '';
              normalized.fecha_evento = data.Fecha_evento || data.fecha_evento || payload.fecha_evento || '';
              normalized.hora_evento = (data.Hora_evento || data.hora_evento || payload.hora_evento || '').toString().slice(0,5);
              normalized.fecha_fin = data.Fecha_fin || data.fecha_fin || payload.fecha_fin || null;
              normalized.hora_fin = (data.Hora_fin || data.hora_fin || payload.hora_fin || '').toString().slice(0,5);
            } else {
              // Normalizar datos de tarea desde la respuesta del servidor
              normalized.nombre = data.Nombre || data.nombre || payload.nombre;
              normalized.descripcion = data.Descripcion || data.descripcion || payload.descripcion || '';
              normalized.fecha_evento = data.Fecha_limite || data.Fecha_evento || data.fecha_evento || payload.fecha_evento || '';
              normalized.hora_evento = '';
              normalized.prioridad = (data.Prioridad || data.prioridad || payload.prioridad || '1').toString();
              normalized.estado = (data.Estado || data.estado || payload.estado || '0').toString();
            }
            const updated = updateItemInDOM(type, id, normalized);
            if (!updated) {
              // Fallback: si no se pudo actualizar el DOM, recargar página para reflejar cambios
              showToast('Guardado. Recargando para actualizar la vista...', 'info');
              closeModal();
              location.reload();
              return;
            }
            showToast('Guardado correctamente', 'success');
            if (type === 'tarea') {
              // Sólo recargar para tareas (solicitud usuario) para refrescar listado.
              closeModal();
              setTimeout(() => { location.reload(); }, 200);
              return; // terminar flujo tras programar recarga
            } else {
              // Evento: mantener actualización en vivo y refrescar calendario si existe
              if (window.calendar) {
                try { window.calendar.refetchEvents(); } catch(e) { console.warn('No se pudo refrescar calendario', e); }
              }
            }
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

      // --- BOTÓN ELIMINAR: Borrar elemento del servidor y DOM ---
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
              // Refrescar eventos del calendario si se editó un evento
              if (type === 'evento' && window.calendar) {
                try { window.calendar.refetchEvents(); } catch(e) { console.warn('Refetch falló', e); }
              }
              // También refrescar por si se eliminó tarea que se muestra en calendario (futuro)
              if (type === 'tarea' && window.calendar) {
                try { window.calendar.refetchEvents(); } catch(e) { console.warn('Refetch falló', e); }
              }
            })
            .catch(err => { console.error(err); alert('Error al eliminar el elemento'); });
      });

      // Si el botón disparador solicitó abrir en modo edición, activar edición inmediatamente
      if (target.getAttribute && target.getAttribute('data-action') === 'edit') {
        editBtn && editBtn.click();
      }

    })
    .catch(err => {
      console.error(err);
      alert('No se pudo cargar la vista del evento');
    });
});

// Animación para aviso ligero en overlay (shake)
const styleShake = document.createElement('style');
styleShake.textContent = `@keyframes shake { 0%{transform:translateY(0);} 25%{transform:translateY(-2px);} 50%{transform:translateY(2px);} 75%{transform:translateY(-2px);} 100%{transform:translateY(0);} }`;
document.head.appendChild(styleShake);
