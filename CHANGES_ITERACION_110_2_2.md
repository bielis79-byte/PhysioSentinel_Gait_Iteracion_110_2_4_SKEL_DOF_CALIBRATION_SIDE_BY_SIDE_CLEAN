# PhysioSentinel Gait V110.2.2 · SKEL Anatomical Constraints Fix

- Mantiene congelada la fuente cinemática V104/V107.
- Conserva SKEL CPU aislado, NumPy 2.x y compatibilidad OpenSim/Pose2Sim.
- Añade restricciones anatómicas en espacio articular sin asumir el orden interno de los 46 parámetros q.
- Penaliza plegados extremos de rodillas/codos, colapso o cruce izquierda-derecha, desviación de spine1/spine2/spine3 respecto al eje pelvis-cuello y clavículas internas incoherentes.
- Añade límites suaves de pose y continuidad con el frame previo; hard clamp conservador ±2.20 rad.
- Aumenta el ajuste temporal por frame de 16 a 24 iteraciones.
- Añade auditoría anatómica por frame (OK/REVISAR, max |q| y ángulos básicos).
- Usa claves de session_state exclusivas V110.2.2 y elimina la malla previa al recalcular la secuencia.
- La malla copia estrictamente la escala de la secuencia activa y verifica igualdad antes de guardarse.
- El NPZ guarda source_sequence_version y source_sequence_scale para trazabilidad.
