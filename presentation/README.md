# Presentación MyPlanner (Standalone)

Este directorio contiene una presentación Reveal.js independiente del proyecto Flask.

## Ver la presentación
- Abre `presentation/index.html` en tu navegador.
- O sirve este directorio:

```powershell
cd C:\Users\pedro\Desktop\Proyecto\Proyecto\proyectoFinal\presentation
python -m http.server 8081
# Abre http://localhost:8081/index.html
```

## Añadir capturas
Coloca imágenes en `presentation/assets/` con estos nombres para que se vean automáticamente:
- `logo.svg` (o `logo.png`)
- `dashboard.png`
- `calendario.png`
- `eventos.png`
- `tareas.png`
- `ajustes.png`

> Nota: Esta presentación usa CDN de Reveal.js, no depende del backend Flask.
