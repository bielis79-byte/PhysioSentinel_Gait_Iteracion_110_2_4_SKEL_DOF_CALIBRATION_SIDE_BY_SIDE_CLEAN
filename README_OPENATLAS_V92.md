# OpenAtlas V92 · paquete anatómico esperado

PhysioSentinel V92 acepta un ZIP de activo anatómico verificable. Estructura mínima recomendada:

```
OpenAtlas_Package/
  model.glb
  rig_map.json
  ATTRIBUTION.txt
  LICENSE.txt            # recomendado
```

`model.glb` debe contener la geometría anatómica y, para animación real, un armature/skin con pesos de vértice. `rig_map.json` debe mapear los nombres reales de los huesos del armature a los roles semánticos de PhysioSentinel (pelvis, spine, head, left/right upper_arm, forearm, thigh, shin, foot).

V92 exporta `retarget_V92_<paciente>.json` con la cinemática 3D frame a frame. Ese archivo es la interfaz entre la reconstrucción biplanar de PhysioSentinel y el rig del modelo anatómico.

El modelo visible sigue siendo un modelo anatómico genérico conducido por la cinemática de la paciente. No representa su anatomía interna individual.
