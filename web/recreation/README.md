# Recreación local: El regreso

Primer objetivo escrito para el prototipo Three.js: encontrar la BMX en
Ganton, seguir cuatro marcadores hasta Grove Street, frenar, bajar con F
y llegar a casa a pie. Al terminar se guarda la partida en el navegador.
Se puede pausar, guardar, continuar y reiniciar desde el menú; R reintenta
si la BMX queda destruida.

Es una recreación independiente. No ejecuta los scripts SCM originales ni
reproduce la misión completa, sus cinemáticas, diálogos o persecuciones.
La conducción y las colisiones son aproximaciones del prototipo.

Desde esta carpeta:

```powershell
npm ci
npm run prepare:local
npm start
```

Abre [la partida local](http://localhost:8084). Usa WASD para caminar o
pedalear, ratón para la cámara, F para montar/bajar, Espacio para saltar o
frenar y Esc para pausar. El menú permite guardar y continuar.

Los recursos se leen de `original/` en la raíz del repositorio. Para otra
instalación establece `SA_PATH` en el entorno antes de preparar e iniciar.
La preparación solo escribe archivos derivados locales ignorados por Git
en `public/original-ui/`, `public/original-audio/` y `tools/txd-index.json`.
No compartas estas carpetas: contienen recursos de tu instalación.
El servidor escucha únicamente en la interfaz local.

```powershell
npm test
# Con el servidor iniciado y los recursos locales preparados:
npm run test:local-assets
```

Las pruebas cubren la secuencia, el guardado, las animaciones, la carga de
recursos y el recorrido con colisiones en CPU. No verifican el renderizado
ni una partida interactiva en navegador. Esa comprobación está pendiente.
Three.js y three-mesh-bvh se distribuyen con sus licencias MIT bajo
`public/vendor/`; los recursos de GTA permanecen locales.

## Inicio original en desarrollo

`/cinematic.html` carga los datos de animaci?n de las escenas originales
PROLOG1 y PROLOG3 de la instalaci?n. Es un reproductor experimental,
no una ejecuci?n de la misi?n original. La escena de la polic?a carga sus
11 actores en CPU; falta verificar su reproducci?n en navegador y corregir
una deformaci?n inicial. La escena del aeropuerto todav?a falla por un
canal de animaci?n no finito con influencia visible.

El lector de audio a?n no obtiene pistas compatibles con la duraci?n de
estas escenas. El reproductor identifica expl?citamente la inspecci?n sin
audio. No incluye PROLOG2 ni ejecuta MAIN.SCM. Los bloqueos y la identidad
de la instalaci?n est?n registrados en [STATUS](../../docs/STATUS.md).

Con el servidor iniciado:

```powershell
npm run test:cutscene-assets
```

## Comprobar las voces de la instalaci?n

```powershell
npm run audit:opening-audio
```

El informe distingue duraci?n de audio y c?mara, verifica el CRC de las
p?ginas Ogg y registra el hash del fragmento le?do. Permanece local bajo
`checks/`. No modifica los archivos originales.

`SA_AUDIO_PATH` permite indicar otra **ra?z de instalaci?n** que contenga
`audio/CONFIG/` y `audio/streams/`; se leen tanto las pistas como sus propias
tablas. `SA_PATH` sigue seleccionando modelos, animaciones y dem?s recursos.
Hay que definir estas variables antes de iniciar el servidor. Una fuente de
audio v?lida no implementa por s? sola el guion original de la misi?n.
