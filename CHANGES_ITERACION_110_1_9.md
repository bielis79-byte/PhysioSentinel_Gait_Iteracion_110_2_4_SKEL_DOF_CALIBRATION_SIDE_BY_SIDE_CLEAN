# V110.1.9 · SKEL FRAME 1 REFINEMENT

- Mantiene V104/V107, runtime SKEL CPU aislado y NumPy 2.x.
- Añade Neck -> neck para completar 15/15 correspondencias cuando el landmark está disponible.
- Amplía el ajuste Adam del frame 1 a 120 iteraciones con regularización suave.
- Añade una fase LBFGS de refinamiento de pose + orientación global.
- Betas permanecen neutras y no se procesan todavía los 75 frames.
- Exporta V110_1_9_SKEL_fit_frame1.json para auditar RMSE y correspondencias.
