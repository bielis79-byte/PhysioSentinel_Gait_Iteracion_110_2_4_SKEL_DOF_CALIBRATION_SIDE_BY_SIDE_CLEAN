# PhysioSentinel Gait V103

- Reproductor del rig completamente autónomo en JavaScript; −1/+1, scrub y reproducción no dependen de reruns de Streamlit.
- Secuencia XYZ explícita por frame y landmark.
- Diagnóstico frame a frame: delta medio/máximo y coordenadas de cadera, rodilla y tobillo.
- Ghost del frame anterior para hacer visible el cambio.
- Exportación CSV `11_rig_3d_v103/cinematica_rig_3d_frames.csv`.
- Descarga directa del CSV desde la pestaña 11.
- Grabación del rig en MP4/WEBM según soporte del navegador.
- Mantiene GPU SAFE.
- El atlas anatómico móvil sigue deshabilitado deliberadamente hasta validar la cinemática.
