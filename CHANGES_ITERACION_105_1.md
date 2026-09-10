# PhysioSentinel Gait V105.1

Hotfix del visor V105 cuando quedaba indefinidamente en “Cargando atlas…”.

- Three.js/OrbitControls/GLTFLoader vuelven al CDN jsDelivr 0.180 ya validado por V104/V99.
- Carga `skeleton.glb` con GitHub raw + fallback jsDelivr.
- Timeout explícito de 20 s por fuente.
- Diagnóstico de errores JavaScript/promesas en el HUD.
- Mensajes de etapa: motor iniciado, descarga, clasificación de mallas y Atlas OK.
- No modifica la trayectoria V104 ni las métricas clínicas.
