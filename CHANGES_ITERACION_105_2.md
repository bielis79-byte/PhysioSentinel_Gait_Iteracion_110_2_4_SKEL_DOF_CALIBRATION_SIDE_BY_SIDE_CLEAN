# PhysioSentinel Gait · Iteración 105.2

Hotfix del visor Rig V104 → Atlas óseo.

- Corrige un error de sintaxis JavaScript introducido por saltos de línea no escapados dentro de cadenas del visor V105.1. Ese error impedía que el módulo 3D comenzara a ejecutarse y dejaba la interfaz indefinidamente en «Cargando atlas… / Preparando…».
- Sustituye los imports estáticos del módulo Three.js por imports dinámicos capturables, de modo que los fallos de CDN/librerías se muestran ahora dentro del panel de diagnóstico.
- Mantiene el cargador de `skeleton.glb` con GitHub Raw + fallback jsDelivr y timeout de 20 s por fuente.
- Mantiene los modos Rig, Huesos y Rig + Huesos, trayectoria V104, GPU SAFE y transformaciones absolutas desde la pose de referencia.
- No modifica métricas clínicas, IC/TO ni resultados biomecánicos.
