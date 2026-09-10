# V110.1.4 · SKEL CPU / NumPy 2

- Elimina `skel` de `requirements.txt` para impedir que su metadata instale `moderngl-window==2.4.6` y fuerce `numpy<2`.
- Mantiene `numpy>=2.1,<2.6`, necesario para Pose2Sim/OpenSim 4.6.
- SKEL se instala sólo cuando se aporta un bundle privado válido, usando `pip install --no-deps` del commit oficial fijado.
- No instala ni usa ModernGL/pyglet para el forward CPU.
- Los modelos `skel_male.pkl` / `skel_female.pkl` no se redistribuyen ni se guardan en Supabase.
- No modifica V104/V107, los 75 frames, los 15 landmarks ni el pipeline clínico.
