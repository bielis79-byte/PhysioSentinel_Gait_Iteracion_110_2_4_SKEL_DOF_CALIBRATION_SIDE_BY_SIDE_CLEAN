# PhysioSentinel Gait · Iteración 110.2.1

## SKEL MESH WALKER
- Mantiene V104/V107 como fuente cinemática congelada.
- Mantiene el fitting temporal SKEL 1→75 de V110.2.0.
- Añade forward de `skin_verts` para cada pose validada.
- Mantiene betas neutras y escala fija durante toda la secuencia.
- Usa la topología oficial `model.skin_f` de SKEL.
- Visor 3D orbitable con malla corporal + joints, Play/Pausa, slider 1–75 y velocidades 0.5× / 1× / 2×.
- Exportación científica NPZ de vértices, caras, joints, frame_ids, escala y betas.
- El PKL privado del usuario no se guarda ni se redistribuye.
- NumPy 2.x, Pose2Sim/OpenSim y runtime SKEL CPU aislado permanecen intactos.
