# PhysioSentinel Gait · Iteración 100

## V100 · rig cinemático explícito sobre atlas anatómico real

- Mantiene V99 GPU SAFE: una sola capa anatómica residente, DPR=1, sin antialias, materiales Lambert, máximo 24 FPS y liberación explícita de GPU.
- Sustituye el retargeting dependiente de nombres internos de GLB por una **clasificación espacial de las mallas** dentro del bounding box anatómico.
- Construye grupos cinemáticos para pelvis, tronco, muslos, piernas, pies, brazos y antebrazos.
- Añade pivotes articulares estimados de cadera, rodilla, tobillo, hombro y codo.
- Añade jerarquías: muslo → pierna → pie y tronco → brazo → antebrazo.
- Usa los frames 3D biplanares de PhysioSentinel para calcular cambios segmentarios respecto al primer frame.
- Añade **contador visible de frames**, botón `Paso +1` y diagnóstico de ángulos/segmentos para verificar objetivamente que el reproductor avanza.
- Añade auditoría del número de mallas asignadas a cada segmento y mallas sin asignar.

## Alcance

El atlas es una geometría anatómica genérica real de BodyParts3D/Z-Anatomy/BodyExplorer. El rig V100 es un retargeting rígido y estimado construido por PhysioSentinel; no es skinning continuo, no contiene pesos de vértices y no representa la anatomía interna individual del paciente.
