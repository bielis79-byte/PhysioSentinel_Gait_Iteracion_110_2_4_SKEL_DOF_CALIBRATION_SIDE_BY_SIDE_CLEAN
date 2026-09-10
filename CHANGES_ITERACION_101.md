# PhysioSentinel Gait · Iteración 101

## V101 · Rig jerárquico con matrices de reposo

- Sustituye el retargeting directo de V100 por una jerarquía estable: pelvis → muslo → pierna → pie y pelvis/tronco → brazo → antebrazo.
- Cada malla se vincula una sola vez a su segmento conservando su transformación mundial de reposo mediante `Object3D.attach()`.
- Los pivotes se calculan en coordenadas locales del atlas, evitando mezclar coordenadas mundiales y locales.
- La animación usa quaterniones relativos respecto al primer frame válido. La rotación local de cada hijo descuenta la transformación mundial del padre para evitar acumulaciones dobles.
- Las mallas no clasificadas se mantienen fijas en lugar de recibir transformaciones inseguras.
- Mantiene GPU SAFE: una sola capa anatómica residente, DPR 1, sin antialias, Lambert, 24 FPS máximo y liberación explícita de GPU.
- Añade `Mostrar rig` para inspeccionar visualmente la jerarquía.
- Añade `Grabar ciclo`: captura el canvas durante un ciclo y ofrece un archivo descargable. Se usa MP4 si `MediaRecorder` del navegador lo admite; en caso contrario, WEBM.
- Mantiene contador de frames y diagnóstico del rig.
- No modifica HALPE26, V48–V52, métricas clínicas ni Supabase.
