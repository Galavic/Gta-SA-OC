# Estado actual

Última traducción: `2026-10-14T03:31:06.407545+00:00`.
Imagen actual: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

El análisis inicial está conservado y no necesita repetirse para la misma
imagen. La última pasada estricta dejó 10 funciones fallidas y
147 referencias de dispatch sin destino. El supervisor de compilación
se detuvo para revisión; no hay una compilación nueva jugable en marcha.

Se identificaron cinco archivos PE almacenados dentro del ejecutable. Cuatro
tablas de salto que bloqueaban la pasada pertenecían a esas imágenes, no a
la imagen principal. Sus cabeceras, extents y destinos se comprobaron con los
bytes originales. Sus buffers siguen disponibles como datos; si se invocan,
necesitan carga y reubicación separadas, todavía sin comprobar.

El siguiente trabajo examina los prefijos de llamadas que modifican el
retorno y los bytes que Ghidra interpretó tras esas llamadas. Las herramientas
existentes permiten comparar prefijos originales x86 con Wasm antes de
aceptar contratos. Todavía no se ha aplicado esta corrección a la variante.

## Criterios de aceptación pendientes

- Arranque del ejecutable actual con imports y destinos estrictos.
- Menú original renderizado y operable en el navegador.
- Intro y cinemática originales con audio y sincronización.
- Primera misión original, con sus scripts y condiciones reales.
- CJ animado correctamente y control del jugador.
- Vehículos con comportamiento físico original.
- Entrada, audio y guardado verificados durante juego real.

La demo de recursos y las pruebas con host sin gráficos no satisfacen estos
criterios. El conteo de funciones o una compilación Wasm tampoco los satisface.
