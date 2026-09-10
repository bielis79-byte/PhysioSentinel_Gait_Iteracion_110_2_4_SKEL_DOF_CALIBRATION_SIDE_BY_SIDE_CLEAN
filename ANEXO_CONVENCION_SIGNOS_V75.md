# ANEXO · Convención de signos PhysioSentinel Gait V75

## Principio general
Siempre que una variable sea direccional y la geometría 2D permita determinar el lado anatómico de forma inequívoca, el signo se refiere al **paciente**, no a la derecha/izquierda de la pantalla. El valor 0 representa la referencia neutra/alineada definida por cada variable.

## Plano frontal/posterior
- **Tronco lateral:** + derecha del paciente; − izquierda.
- **COM lateral y COM/BOS firmado:** + derecha del paciente; − izquierda. Las magnitudes absolutas no son direccionales.
- **Pelvis:** + hemipelvis derecha elevada; − hemipelvis izquierda elevada.
- **Hombros:** + hombro derecho elevado; − hombro izquierdo elevado.
- **Hombros−pelvis:** + predominio relativo hacia elevación derecha; − hacia elevación izquierda.
- **Rodilla frontal:** + valgo/desviación medial proyectada; − varo/desviación lateral proyectada. Los P95 absolutos resumen magnitud.
- **Pie:** + toe-out; − toe-in. Se mantiene Heel→BigToe, priorizando apoyo y QC distal robusto.
- **Retropié:** + eversión proyectada; − inversión proyectada. No equivale a pronación/supinación 3D.

## Plano sagital
- **Rodilla:** magnitud de flexión 2D; 0 ≈ extensión geométrica; mayor valor = mayor flexión. No se fuerza hiperextensión negativa sin referencia adicional.
- **Cadera:** magnitud angular 2D hombro-cadera-rodilla. No se fuerza flexión+/extensión− porque la fórmula actual no distingue ambos sentidos con seguridad en todas las geometrías.
- **Tobillo-pie:** ángulo interno rodilla-tobillo-BigToe (0–180°). No se transforma a dorsiflexión+/flexión plantar− sin referencia neutra/calibrada.
- **Hombro sagital:** ángulo interno cadera-hombro-codo; no representa derecha/izquierda.

## Variables no direccionales
ROM, P95 absoluto, amplitud, diferencias absolutas, CV, consistencia, índices 0–100, anchura de base y magnitudes de velocidad no representan lateralidad por su signo. El acoplamiento tronco-pelvis `r` usa + para correlación/en fase y − para correlación opuesta/contrafase. El desfase tronco-pelvis expresa adelanto/retraso relativo, no lateralidad anatómica.

## Orientación de cámara
Las variables que requieren transformar derecha/izquierda de imagen a lateralidad anatómica necesitan declarar correctamente **Frontal** (paciente mirando a cámara) o **Posterior** (paciente de espaldas/alejándose). Si se selecciona **No especificada** o **Mixta/ida-vuelta**, las variables dependientes del espejo de cámara no publican un signo anatómico.

## Alcance
Estas convenciones estandarizan la semántica de las gráficas 2D; no convierten las medidas markerless proyectadas en cinemática 3D ni establecen por sí mismas normalidad, diagnóstico o causalidad clínica.
