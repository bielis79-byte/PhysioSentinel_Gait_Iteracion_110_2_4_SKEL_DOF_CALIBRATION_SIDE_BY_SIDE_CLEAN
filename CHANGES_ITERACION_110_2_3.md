# PhysioSentinel Gait V110.2.3 · Hierarchical Retargeting

- Sustituye la optimización libre de 46 q por retargeting jerárquico con 16 DOF activos observables/inferibles desde los 15 landmarks V104/V107.
- Los DOF no observables (rotación axial de cadera no determinada, tobillo/subtalar/MTP sin pie, supinación/pronación, muñecas, escápulas y orientación de cabeza) permanecen exactamente neutros.
- Jerarquía de ajuste: eje corporal → miembros inferiores → miembros superiores → micro-refinado conjunto.
- Inicialización directa de flexión de rodilla y codo desde geometría de tres puntos.
- Límites articulares conservadores por parámetro y auditoría de fuga en DOF bloqueados.
- Propagación temporal con la pose previa como referencia, manteniendo escala corporal fija.
- Recupera el vídeo/animación 3D simplificado no calibrado V104/V107 como referencia visual junto a SKEL.
- Mesh Walker se genera únicamente desde la secuencia jerárquica V110.2.3 activa.
- No modifica V104/V107, métricas clínicas, NumPy 2.x, OpenSim ni Pose2Sim.
