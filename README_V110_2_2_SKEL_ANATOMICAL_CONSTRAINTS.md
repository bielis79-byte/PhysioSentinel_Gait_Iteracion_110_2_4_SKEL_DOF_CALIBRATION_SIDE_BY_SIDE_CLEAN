# V110.2.2 · SKEL Anatomical Constraints Fix

Objetivo: evitar que una reducción del RMSE de landmarks produzca poses SKEL visualmente deformadas por grados de libertad insuficientemente observados.

Flujo: V104/V107 → frame semilla restringido → propagación temporal restringida → auditoría anatómica → skin_verts con escala verificada → visor 3D.

Esta versión no cambia métricas clínicas ni la reconstrucción V104/V107. Las restricciones son salvaguardas geométricas del retargeting y no constituyen rangos diagnósticos.
