# V110.2.1 · SKEL MESH WALKER

Esta versión convierte la secuencia temporal SKEL validada en V110.2.0 en una malla corporal animada.

Flujo: V104/V107 XYZ → fit frame semilla → propagación 75 frames → `SKEL(...).skin_verts` → transformación global por frame → Mesh Walker 3D.

El visor no sustituye la cinemática ni repite el fitting; representa el mismo movimiento ya resuelto. La topología corporal procede de `model.skin_f`, conforme al quickstart oficial de SKEL.

El bundle privado `skel_models_v1.1.zip` lo aporta el usuario en ejecución y se extrae sólo a `/tmp`; no se incluye en esta distribución.
