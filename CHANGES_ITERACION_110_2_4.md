# Cambios V110.2.4

- Añadida calibración empírica completa q0…q45 del modelo SKEL real.
- Cada q se evalúa en +delta y -delta alrededor de la postura neutra.
- Se cuantifica el desplazamiento articular central por radián y se identifican joints afectados.
- Se registra eje global dominante y signo del joint más sensible como ayuda para detectar ejes/signos mal interpretados.
- Exportación de la calibración en CSV y JSON.
- Nuevo visor Side-by-Side sincronizado por un único selector de frame:
  1. XYZ simplificado V104/V107 no calibrado.
  2. Joints SKEL con líneas de error hacia landmarks objetivo.
  3. Malla corporal SKEL.
- Métricas de error medio, máximo y landmark peor del frame seleccionado.
- Se mantienen NumPy 2.x, Pose2Sim, OpenSim y runtime SKEL CPU aislado.
- Se corrigen las etiquetas internas/exportaciones que arrastraban 110.2.2/110.2.3.
