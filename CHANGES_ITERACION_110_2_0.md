# PhysioSentinel Gait · V110.2.0

- Mantiene V104/V107 como fuente cinemática congelada.
- Conserva el runtime SKEL CPU aislado en /tmp y NumPy 2.x.
- Mantiene el ajuste refinado del frame semilla con 15 correspondencias anatómicas.
- Añade propagación temporal desde el frame semilla hasta el final de la secuencia.
- Betas y escala corporal quedan fijas durante toda la marcha.
- Pose, orientación global y traslación se inicializan desde el frame anterior.
- Añade regularización temporal para reducir saltos frame a frame.
- Añade auditoría RMSE por frame, exportación JSON de toda la secuencia y visor 3D animado de joints SKEL.
- La propagación se ejecuta sólo bajo demanda para no penalizar el arranque de Streamlit.
