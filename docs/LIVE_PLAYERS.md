# Panel de presencia

El panel se publica en https://gta.galavic.world/jugadores/ y tiene un enlace
desde el launcher. Muestra sesiones anonimas del reproductor: carga del motor,
juego abierto, visibilidad de la pestana y tiempo conectado. El menu del juego
tambien cuenta como juego abierto. Una persona puede abrir varias pestanas;
estas cifras no representan personas unicas ni verifican una mision activa.

Cada conexion recibe un UUID temporal generado por el servidor. La aplicacion
no almacena nombres, direcciones IP, paises ni huellas del navegador para este
panel. Las sesiones se conservan en los adjuntos de WebSocket y desaparecen al
cerrar o caducar; no se genera un historial de jugadores.

## Actualizacion

El reproductor se registra despues de validar su instalacion. El primer informe
de frames del renderer cambia su estado a juego abierto. Un heartbeat cada
25 segundos mantiene la sesion y comunica la visibilidad de la pestana. Los
fallos del motor cierran el registro de presencia. pagehide y pageshow manejan
salida y restauracion de la pagina; las conexiones perdidas se reintentan con
espera creciente. La presencia funciona independientemente de las lecturas del
juego: un fallo de red del panel no detiene el motor.

El servidor transmite cambios a los observadores mediante WebSockets. Los
observadores no aumentan el contador. Las desconexiones normales se retiran al
cierre; sin aviso se excluyen tras 90 segundos sin heartbeat y se cierran mediante
una alarma prevista cada 30 segundos; el planificador puede retrasar su ejecucion. Una pestana congelada por el
navegador puede caducar y volver a registrarse al recuperar la conexion.

Las paginas del reproductor abiertas antes de instalar esta funcion empiezan
a informar cuando se recargan. El panel es publico y sus identificadores son
anonimos; no constituye una lista de cuentas autenticadas.

## Despliegue

`cloudflare/presence.mjs` exporta `PlayerPresence`, conectado al Worker por el
binding `LIVE_PLAYERS`. El empaquetador declara la migracion `presence-v1` con
`new_sqlite_classes`, usando un Durable Object compartido por nombre estable.
Se usa la API de hibernacion de WebSockets y alarmas, sin un temporizador activo
permanente en el objeto. Las peticiones WebSocket del navegador requieren el
mismo origen. Los mensajes estan limitados y validados.

La pagina, estilos y cliente del panel viven en `tools/web/live/`; el tracker
esta en `tools/web/player-presence.mjs`. La integracion del HTML del reproductor
se conserva en `patches/current-vendor.patch`. No requiere recompilar el Wasm.
Los paquetes Pages alternativos deben enlazar la clase del Worker `gta-sa-oc`
ya desplegado mediante `script_name`; Pages no aloja esta clase por si mismo.

Las rutas son `/api/presence` (snapshot), `/api/presence/player` (reproductor)
y `/api/presence/watch` (observador). Los datos no se sirven desde cache. El
panel cambia a reconexion y retira las cifras anteriores si pierde el socket.

Para preparar una release se sigue el flujo de [archivos bajo demanda](DEMAND_FILES.md).
El runtime y los objetos R2 existentes se reutilizan cuando sus identidades
coinciden. Los resultados de pruebas y la version publicada se registran en
[STATUS.md](STATUS.md) y `progress.json`.
