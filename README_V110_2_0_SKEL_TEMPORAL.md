# V110.2.0 · SKEL temporal

Objetivo de esta puerta: demostrar la continuidad temporal del retargeting V104/V107 → SKEL antes de renderizar la malla anatómica completa.

Flujo: frame semilla validado → escala/betas congeladas → warm-start del frame previo → regularización temporal → 75 poses → animación articular SKEL.

La animación incluida representa los joints anatómicos SKEL. El render de la malla completa se deja para una iteración posterior tras validar estabilidad y RMSE temporal.
