# PhysioSentinel Gait V110.2.4 · SKEL DOF Calibration & Side-by-Side Validation

Objetivo: identificar empíricamente el efecto real de cada parámetro q del modelo SKEL privado antes de volver a corregir el retargeting anatómico.

Novedades:
- barrido q0…q45 alrededor de la pose neutra mediante diferencias finitas centrales;
- tabla por q con joint más sensible, sensibilidad, eje global dominante, signo y joints afectados;
- exportación CSV y JSON de la calibración DOF;
- mantiene la cinemática V104/V107 congelada y el retargeting jerárquico V110.2.3 como referencia diagnóstica;
- validación sincronizada del mismo frame en tres columnas: XYZ simplificado V104/V107, joints SKEL y skin mesh SKEL;
- error 3D por landmark en el frame sincronizado;
- versionado/exportación corregidos a V110.2.4;
- no se redistribuyen los PKL privados SKEL.

La calibración es diagnóstica. V110.2.4 no presupone que un índice q tenga el significado biomecánico usado en versiones anteriores; esa correspondencia se decidirá a partir del efecto observado.
