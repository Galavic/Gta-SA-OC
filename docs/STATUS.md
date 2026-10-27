# Estado actual

## Revision del snapshot web para Git (2026-10-27)

Se agrupan los cambios locales del port web: launcher, importacion alojada,
Cloudflare, herramientas reorganizadas, panel asociado y parche completo del
runtime. Se conserva la revision fijada `ad47228c5b0ab2d1453251999bbd86795e178fac`
y su licencia. Las modificaciones locales de la dependencia quedan en el parche.

Validacion de este snapshot: 112 pruebas Python de `tests` y `tools/tests`,
47 pruebas JavaScript del reproductor, Worker e importadores; todas pasan.
La revision del indice con `tools/check_publication.py` tambien pasa.
Estas comprobaciones no verifican gameplay ni resuelven los bloqueos de
la compilacion descritos en las secciones siguientes. No se hace push.
Ejecutable de referencia: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Regresion al entrar en partida (2026-10-24; correccion en preparacion)

El usuario prueba el candidato `1321072f9b3acaca8658d25dfd34715f220e80b881598d6e94eae6a370a079cf`
y se cierra al entrar. Ejecutable fijado:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
El log confirma abort en `01560a22`: el salto `01560bae -> 01560a2a` se
clasifica incorrectamente como interior de instruccion. El PE y una prueba
sin GPU reproducen el rechazo; `01560a2a` es MOV EAX,[ESP+0x1c] y es un destino
valido. Es una regresion del cambio anterior: omitia un bloque tras un salto
y no lo recuperaba al descubrir despues una arista hacia atras.

El decodificador recorre ahora una lista acotada de instrucciones alcanzables,
incluidos esos destinos tardios, y ordena/valida sus intervalos antes de
resolver indices. Conserva los rechazos por solapamiento real, saltos fuera
del rango y presupuestos de ejecucion. Pasan 733 comprobaciones del interprete,
107 de audio y tres de reutilizacion. La regresion sintetica ejecuta cero,
una y tres vueltas, ademas de verificar invalidacion de cache al editar el
bloque omitido. Pasan ademas 131 casos contra Unicorn, con cinco casos nuevos
de control de flujo. Las pruebas acotadas de ambos bloques originales, `005a0035`
y `01560a22`, pasan. No ejecutan gameplay ni prueban estabilidad en navegador.

El perfil nuevo se observa aplicado antes del cierre: escala automatica 1,75,
un submit por fotograma y renombrado activo. Son pantallas previas a la ciudad;
no se atribuye mejora FPS ni calidad visual comprobada. Preparacion Binaryen,
V8 y staging final del motor corregido en curso. Mientras tanto se valida con
V8 y sirve un intermedio sin -O2: Wasm
`7c5008a80038f8e741f1001022137819871746673a4e14260709ee005f638d13`,
260.326.761 bytes. HTTP/source/staging coinciden; es para probar la entrada,
no comparar FPS. La optimizacion sigue en segundo plano. No se publica.
Registros e identidad
de pruebas conservados en `build/entry-crash-20261024/` y `docs/progress.json`.
Pendiente entrar en partida y repetir ruta del crash, Audio, tono y medidas FPS.

## Cierre, audio y resolucion (2026-10-24; candidato servido en local)

Sesion del usuario: Wasm `2d0bac24bc99f8135218adc5b98016927b8964035c21587c21de61865428b7c8`,
ejecutable `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Captura: 17,5 FPS en ciudad (48,2 ms; P95 80,3 ms; GPU 7,8 ms), con pixelacion.
El registro confirma adaptador NVIDIA Ampere. El usuario informa 0,5 FPS al
abrir Audio y sonidos de CJ/botones graves. El cierre termina en la llamada
`005a0035`: el interprete rechaza CMP AX,0x196 (`66 3d 96 01`). Se conserva
el registro completo antes de reiniciar.

Se amplian comparaciones word, TEST AL inmediato, FCOM/FCOMP de memoria y
FNSTSW AX usando flags y pila x87 compartidos. Tras un terminador se omiten
bytes sin entrada observada hasta el siguiente destino de salto conocido.
No se sustituye una instruccion desconocida por un retorno ficticio. La prueba
acotada del bloque original `005a0035` ahora pasa; no ejecuta gameplay.

Dos fallos concretos de audio corregidos: repetir pan/frecuencia sin cambio
marcaba el canal como detenido; reutilizar un canal conservaba la frecuencia
del propietario anterior. Se mantiene el ajuste entre Stop/Play del mismo
propietario. Pasan 716 comprobaciones del interprete, 107 del mezclador y tres
de reutilizacion. Pasan ademas 126 casos pytest contra Unicorn (300 rutinas
integer aleatorias, 76 formas extendidas y 49 comparaciones estrechas); el log
conserva diagnosticos Windows de Unicorn con proceso finalizado correctamente.
El target independiente de audio evita las constantes de
otro juego requeridas por host_tests. La suite DX completa tiene 141.201
comprobaciones y 23 fallos: ABI de host de 64 bits sobre wasm32 (17) y cursor
learned (6); no se declara aprobada ni se ha comparado con un binario anterior.

El HTML deja de forzar escala 1 para recuperar la resolucion automatica y
activa controles existentes de cache de grupos por fotograma, subidas agrupadas
y renombrado de buffers. QPC permanece en 1. Pasan siete pruebas de staging.
La sesion del crash aun tenia escala 1 y renombrado desactivado; no prueba
un fallo del nuevo perfil. No hay ganancia FPS medida.

Compilacion, pruebas dirigidas, Binaryen -O2 y V8 completo aprobados.
Candidato local: Wasm `1321072f9b3acaca8658d25dfd34715f220e80b881598d6e94eae6a370a079cf`
(235.192.022 bytes); JS `7462fd59c3e3a6b381267a6c37f9fee159815acc1fa1f58eacb17b00ade68983`;
data `63b5a7056570aa52e13bd93c067dbe279874e8cbf97ff5c6c2b0cc72df68605d`.
Source, staging y HTTP tienen los mismos hashes. Se verifican MIME Wasm,
COOP/COEP, HTML con el hash nuevo y perfil automatico/QPC=1. La preparacion
conserva 189.522 funciones y maximo 98 locales. El linked archivado conserva
su hash tras compresion NTFS. Se preserva el candidato anterior y su registro.
Recargar con Ctrl+F5 `http://127.0.0.1:8771/gtasa-singleplayer/`.
Pendiente repetir ruta del crash, abrir/cerrar Audio, escuchar el tono y medir
calidad/FPS en navegador; no hay estabilidad o ganancia FPS verificada para
este candidato. Los dialogos ausentes tambien en Windows siguen aplazados.
No se publica.
Evidencia local: `build/crash-audio-20261024/`, `build/render-profile-20261024/`;
identidades de pruebas y bloqueos en `docs/progress.json`.

## Limite de 30 FPS y espera adicional de Idle (2026-10-23)

El usuario informa cinematicas a 60 FPS y juego a 20-30 FPS en PC con el
candidato local `49374508f33b2b704d5756e6265f5b7f82461ead4149797a0a467327f20b3cf9`.
Es un reporte del usuario, sin captura de tiempos ni medicion automatizada.
Se verifica en el ejecutable fijado
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`
que `00619620` inicializa RsGlobal.frameLimit en 30; `00748d81..00748d96`
compara 1000/limite con el tiempo transcurrido cuando corresponde limitar.
Ademas `0053e94a..0053e94d` gira hasta superar 14 ms respecto al marcador de
Idle. No son los hooks historicos de GetTickCount de otra imagen.

`tools/configure_idle_pacing.py` valida SHA y bytes de ambos sitios antes
de configurar dos sustituciones del traductor: limite inicial 60 y comparacion
Idle con cero, que nunca toma el salto unsigned de espera. Conserva el PE,
QPC normal, CTimer::Update, los controles y el trabajo restante del motor.
Permite restaurar ambos cambios; rechaza parches ajenos. La regeneracion,
compilacion y preparacion del candidato local terminan con exit code 0.

La comparacion de fuentes detecta ademas una cabecera x86.h obsoleta junto a
los C generados: el candidato `49374508...` conservaba la rama de retornos
resumables como variable en esas unidades. Corrige la afirmacion anterior
sobre la incorporacion efectiva de esa optimizacion a dicho Wasm: el cambio
existia en la cabecera canonica y el parche completo, pero faltaba refrescar
su copia generada. Esta ronda la sincroniza con la canonica y recompila todas
las unidades afectadas. No se atribuye una ganancia FPS a esa sustitucion.

`tools/audit_idle_pacing.py` ejecuta el prefijo x86 real con Unicorn y relojes
deterministas: cinco cargas de trabajo, 30 fotogramas por caso, conservando
la igualdad entre tiempo real e input del temporizador. El bucle original
introduce esperas adicionales; el candidato solo consume tres lecturas por
fotograma. Seis pruebas del bloque x87 real confirman que a 20 ms el limite
30 bloquea Idle y el limite 60 permite entrar. Son pruebas CPU del control de
flujo, no verifican FPS, fisica ni estabilidad de gameplay en navegador.
Pasan cinco pruebas de configuracion, identidad, idempotencia y restauracion;
quince pruebas Python en total entre configuracion, preparacion y staging.
El binario de pruebas recien compilado pasa 21.600 comprobaciones de arranque,
reloj, eventos, cache y callbacks en ambos modos. Identidad de ese binario CPU:
`f14f175e6e3638538d3a8460bd8fd9966b5869915cba90005f895eb2e3677dab`.
Estas comprobaciones no ejecutan la ciudad ni prueban rendimiento grafico.
El player ya solicita una GPU de alto rendimiento; se anade un registro unico
de vendor/arquitectura/dispositivo/descripcion cuando el navegador lo expone.
La GPU elegida y su impacto en gameplay siguen sin verificar.

V8 acepta el modulo completo: 212.673 funciones antes de -O2 y 189.522 despues;
maximo de locales de 2.929 a 98. Wasm local de 235.190.585 bytes, SHA
`2d0bac24bc99f8135218adc5b98016927b8964035c21587c21de61865428b7c8`.
JS: `fa1ef389ab9453499689dc14cac8272233636ab5b1e707b8a09afd144275820e`;
paquete data sin cambios:
`63b5a7056570aa52e13bd93c067dbe279874e8cbf97ff5c6c2b0cc72df68605d`.
HTTP entrega los mismos bytes que source/staging, con MIME Wasm y COOP/COEP.
El HTML servido mantiene QPC=1 incluso en el enlace antiguo con QPC_SCALE=2,
escala grafica base 1 y preferencia GPU de alto rendimiento. El registro de
GPU pasa tres casos Node y el script inline del player pasa comprobacion de
sintaxis; la seleccion real del navegador queda pendiente.

Para revisar: recargar `http://127.0.0.1:8771/gtasa-singleplayer/` con Ctrl+F5,
medir FPS/tiempos al recorrer la ciudad y comprobar velocidad, controles y
cinematicas. El tope configurado es 60, sin ganancia de FPS verificada en una
partida ni verificacion de fisica a esa cadencia. La copia anterior y los
registros conservan sus identidades. Dos linked archivados se comprimen con
NTFS para recuperar espacio, verificando ambos hashes sin cambios. Todo local.
Evidencia local: `build/idle-pacing-20261023/idle-prefix-audit.json` y
`build/idle-pacing-20261023/status.json`. No se publica nada.

Referencias de correspondencia, contrastadas con el ensamblado local:
[GTA Reversed Idle](https://github.com/gta-reversed/gta-reversed/blob/master/source/app/app_game.cpp)
y [WinMain](https://github.com/gta-reversed/gta-reversed/blob/master/source/app/platform/win/WinMain.cpp).

## Retirada del enlace de reloj acelerado y resolucion base local (2026-10-23)

El usuario informa aproximadamente 20 FPS y sensacion de velocidad x2. El
enlace experimental ofrecido activaba QPC_SCALE=2, que acelera el reloj del
guest; no acredita una optimizacion ni una ganancia de FPS. Se retira del
launcher jugable: el preRun ignora ese parametro en enlaces antiguos y fija
QPC_SCALE=1 incluso ante un valor heredado en ENV. Es necesario recargar la
pagina para reiniciar el runtime que ya estuviera ejecutandose con escala 2.

El bootlog confirma el Wasm local `49374508f33b2b704d5756e6265f5b7f82461ead4149797a0a467327f20b3cf9`
y objetivos de render a 1,75x la resolucion del juego. El nuevo perfil local
usa D3D9_SCALE=1 por defecto, evitando ese incremento de aproximadamente
3,06x en pixeles; la imagen puede verse menos nitida al ampliarla. Se conservan
overrides de escala grafica y cache, pero no del reloj. Se activa el informe
ligero D3D9_STATS para registrar FPS/dibujos/grupos cada 300 presentaciones y
se registran los valores efectivos del perfil al arrancar. No se cambia Wasm.

Pasan diez pruebas Python, incluida ejecucion del preRun real con enlaces
QPC=2/8, parametros repetidos y ENV heredado, y conservacion de otros overrides.
HTTP entrega el HTML corregido incluso al solicitar el enlace antiguo con
QPC_SCALE=2. El navegador de herramientas sigue sin sesiones conectadas:
pendiente confirmar ritmo normal y medir FPS/P95 tras recargar en PC. Los
20 FPS reportados siguen siendo un problema sin mejora verificada. Cambios
solo locales. Evidencia: `build/optimization-20261023/normal-clock-launcher-check.json`.
Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Panel de Deska del port (2026-10-24)

Se agrega `deska/san-andreas-web`, un panel para Deska que abre el launcher
publico, muestra un resumen fechado de hitos verificados y guarda una lista
personal de pruebas. Solo pide `open-url`; no declara hosts ni consulta la red.
Las pruebas se guardan en deska.storage y no son una verificacion oficial.

El manifiesto pasa el validador de deska-panels-examples. En el host de vista
previa carga en temas claro/oscuro y locales en/es sin errores del panel ni del
puente; se comprobaron persistencia, borrado, teclado y `openUrl` simulado, y
los anchos 240, 300, 340 y 400 px sin desbordamiento horizontal.
Pendiente cargarlo en Deska real y revisar la ventana en el escritorio del
usuario. No cambia el ejecutable ni el Wasm publicados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26` y
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Evidencia: `build/deska-panel-20261023/`.

## Optimizacion local para PC y esperas de streaming (2026-10-23)

El usuario informa tirones al recorrer la ciudad y en cinematicas en PC.
Confirma que las voces tampoco funcionan en la instalacion Windows original
y pide posponer ese asunto. La auditoria repetida conserva las identidades
historicas de PROLOG1/PROLOG3: el mismo Ogg de 9.504 bytes y 1,18578125 s,
con relleno posterior. No se sustituye ni publica audio en esta ronda.

Se incorpora del commit de lauta `ff1547048f9924df73f9f99c9d0b7a839f361dc3`
la decision constante del retorno resumable y la preparacion incondicional
con wasm-opt -O2, validando en V8 y aceptando la eliminacion de funciones.
La preparacion registra hashes de entrada/salida y permite elegir el linked
de entrada. Se conserva una copia del runtime anterior. La escala QPC esta
disponible como diagnostico validado entre 1 y 8, desactivada por defecto;
no se incorpora la eliminacion experimental de flags ni contadores por bloque.

Cambios nuevos: pool de hasta 32 checkpoints retirados por hilo propietario,
sin mover checkpoints activos ni cambiar las reglas SEH; eliminacion de
recorridos PCM y mensajes de primer Play fuera de AUDIO_TRACE; aplicacion de
senales host pendientes antes de evaluar una espera, incluso timeout cero.
Este ultimo cambio corrige la observacion tardia de finalizaciones entre los
checkpoints de imports muestreados. El player local activa la cache acotada de
rutas de lectura, conservando overrides RECOMP_ explicitos; no cachea contenidos.

Verificacion CPU: 403 comprobaciones de arranque, 68 de cache de rutas, 20 de
reloj, 8 de despacho SEH vacio, 7 de contadores del interprete y 977 de eventos
pasan. Ambos modos del pool pasan 10.066 comprobaciones cada uno; el ensayo
anidado reduce reservas de 69.032 a 33.032, con 36.000 reutilizaciones. Tiempos
de microbenchmark bajo compilacion concurrente no prueban una ganancia FPS.
Tras corregir las esperas pasan las notificaciones DirectInput/DirectSound y
los grupos de streaming, formatos y vida de PCM. La suite DX completa conserva
23 fallos de ABI/cursor; no se declara verde. Antes del arreglo de esperas el
binario recien compilado tenia 29 fallos, incluidos seis de notificaciones.
Las diez pruebas Python de preparacion y staging pasan.

Compilacion completa y preparacion terminadas con exit code 0. V8 acepta el
modulo completo: 213.007 funciones antes de -O2, 201.224 despues; maximo de
locales de 2.929 a 98. Wasm local de 240.809.792 bytes, frente a los
266.206.438 bytes del baseline conservado. Esto acredita reduccion de tamano,
no una ganancia medida de FPS. Hash del nuevo Wasm local:
`49374508f33b2b704d5756e6265f5b7f82461ead4149797a0a467327f20b3cf9`.
JS, Wasm y data entregados por HTTP son identicos a sus fuentes, con COOP/COEP
y MIME Wasm correctos. El HTML anuncia el mismo hash y conserva overrides.
Las pruebas especificas se repiten con los binarios finales de singleplayer;
la suite DX final confirma los 23 fallos historicos de ABI/cursor y los grupos
de notificaciones/streaming pasan. El parche completo reconstruye identicos
los siete archivos nativos modificados sobre la base local.

Servidor disponible en http://127.0.0.1:8771/gtasa-singleplayer/ . La prueba
de reloj de lauta se activa explicitamente con `?RECOMP_QPC_SCALE=2`;
el arranque normal no escala el reloj. Pendientes comparar FPS/P95 en escenas
de ciudad y cinematicas y comprobar sincronizacion en navegador. No hay una
sesion de navegador conectada a las herramientas; el intento de abrir IAB
tambien devuelve Browser is not available. Ningun cambio de esta ronda se
ha desplegado. Evidencia privada: `build/optimization-20261023/`, incluidos
`staged-candidate.json`, `http-delivery.json` y `source-patch-check.json`.
Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Revision de la prueba de 40 FPS de lauta (2026-10-23)

Revisado el commit remoto `ff1547048f9924df73f9f99c9d0b7a839f361dc3`.
Su informe mide 24,35 FPS con reloj normal, 37,80 con RECOMP_QPC_SCALE=2 y
39,5 con wasm-opt y escala 8, en una escena concreta. El propio autor deja
la escala desactivada por defecto: altera el reloj del juego y puede cambiar
fisica, animacion y trafico. Son mediciones publicadas por el autor, no una
reproduccion local ni una garantia de rendimiento en otros dispositivos.
El informe retira la mejora de velocidad atribuida a wasm-opt; conserva una
reduccion de tamano de 254,2 a 229,7 MB.

El runtime local no contiene RECOMP_QPC_SCALE y el Wasm publicado sigue siendo
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
La actualizacion de descarga no incorpora esta ronda del motor. Esta revision
no modifica ni publica el runtime. Pendientes integrar los cambios compatibles,
compilar y comparar artefactos en navegador con escena y temporizacion normales;
no se ha verificado aqui el resultado de 40 FPS.
Ejecutable del informe y de la publicacion:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Preparacion alojada acelerada y reanudable por bloques (2026-10-24)

La captura del usuario muestra la descarga inicial en 1/417 archivos,
20 MB de 4,7 GB (anim/cuts.img). La ruta anterior descargaba un archivo a la
vez y calculaba SHA-256 en JavaScript tanto en hostedSource como en importGame.
Cada avance de red notificaba al hilo principal y la importacion anterior
persistia el manifiesto solo cada 50 archivos completos.

La nueva ruta alojada, propia del repositorio, usa rangos de 4 MiB y WebCrypto,
con dos archivos y dos rangos por archivo simultaneos (hasta cuatro descargas).
Verifica cada rango antes de escribirlo a su offset real en OPFS. Conserva los
bloques comprobados en un diario, con checkpoint como maximo cada segundo y
al completar cada archivo. Se reutilizan archivos completos del manifiesto
anterior. Un fallo/cancelacion espera las solicitudes hermanas antes de cerrar
sus handles. El sello final solo aparece al terminar y verificar ejecutable y
DLL reales; una DLL local corrupta se vuelve a descargar. Los perfiles siguen
fuera de esta ruta. Los avisos de avance se limitan a 150 ms y muestran MB/s.

Se genera un inventario de 1.586 rangos comprobando de nuevo las identidades
del origen preparado; los objetos R2 y game build `a033b7fd3a69b951` se reutilizan.
El Worker permite Range validado, devuelve 206/Content-Range/Accept-Ranges y
rechaza rangos invalidos con 416 antes de acceder a R2. El lector rechaza una
respuesta 200 antes de almacenar su cuerpo, evitando buffering de archivos
grandes si un servidor ignora Range. La integracion se hace al montar el
launcher y deja disponible la importacion anterior para carpetas/ZIP e
inventarios sin fastRanges; no se modifica la dependencia fijada.

Publicada version `4e246825-35d4-4286-af76-051caf44b917`. Pasan 32 pruebas Node y
8 Python, incluidos corrupcion, interrupcion/reanudacion parcial, reparacion de
DLL, cancelacion, limites de rangos y enlace del inventario a bytes originales.
Verificados por HTTPS cinco recursos cambiados y nueve rangos de archivos
normales y fragmentados con SHA-256 y Content-Range exactos. Muestra HTTP desde
este equipo: 33742848 bytes en 1.048 segundos,
30.69 MiB/s. Es una comprobacion de red con curl,
no una medicion de navegador movil. Microbenchmark Node de 32 MiB: doble hash
JS 1163.9 ms frente a hash nativo 37.0 ms;
el factor 31.4 corresponde solo al hash, no a la carga completa.

La referencia primaria consultada, https://github.com/hellorayhere/gta5-web-port,
documenta rangos, batches y cache acotada para traer recursos bajo demanda.
Este cambio acelera la preparacion completa; todavia descarga 4,7 GiB antes
de arrancar. Carga del motor bajo demanda requeriria cambiar su backend de
archivos y validar lecturas durante juego real. Pendientes velocidad real en
celular, preparacion completa en navegador y gameplay del dominio publico.

Evidencia: `build/cloudflare-release-20261024-fast-import/http-range-verification.json`,
`build/cloudflare-release-20261024-fast-import/preflight-verification.json` y
`build/import-performance-20261024/hash-benchmark.json`.
Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm conservado: `5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.

## Mejoras del launcher publicadas con autorizacion (2026-10-24)

El usuario indica ahora si subelo, autorizando publicar las mejoras que se
habian mantenido solo en local. Publicadas en https://gta.galavic.world/:
favicon, tarjetas de redes de Galavic y lauta con logos originales, cuatro
portadas aleatorias sin repeticion consecutiva, correccion de capas del fondo,
logo centrado en celular y musica en bucle con silencio persistente junto a
Pause backgrounds. La primera imagen tambien se elige aleatoriamente.

Worker version `cc75e7f4-51c3-49a4-b887-cd752e15d55a`.
Se conserva game build `a033b7fd3a69b951` y la descarga automatica del
juego preparado, con los mismos archivos R2. El runtime no cambia:
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

Pasan 6 pruebas Python de staging/servidor y 17 Node de audio de menu,
transporte y Worker. Comprobada la sintaxis de todos los modulos de la release,
el allowlist y la ausencia de credenciales/rutas personales en recursos de
texto. Wrangler dry-run y despliegue completados. Verificados por HTTPS los
33 recursos estaticos con bytes exactos, MIME y COOP/COEP, y HEAD de los dos
objetos de runtime con tamanos originales. Una peticion Range al MP3 devuelve
200 con el archivo completo correcto. Pendiente revision interactiva del
launcher, audio y movil en el dominio publico; no se afirma gameplay nuevo.
No se realiza push de Git ni se reescribe el trabajo pendiente del repositorio.

Evidencia local:
`build/cloudflare-release-20261023-launcher-refresh/preflight-verification.json`
y `build/cloudflare-release-20261023-launcher-refresh/http-verification.json`.
Las notas anteriores de solo local se conservan como historial de cada cambio.

## Portadas aleatorias, solo local (2026-10-23)

Se elige aleatoriamente la primera portada y se barajan las restantes con
Fisher-Yates. Al terminar una ronda se vuelve a barajar la lista completa,
evitando comenzar con la portada visible. Se conservan las cuatro imagenes,
el intervalo de 8 segundos, el fundido, la pausa y las capas del fondo.
La primera imagen aleatoria se muestra tras decodificarla, conservando el
fondo CSS mientras carga; se precarga tambien la siguiente candidata.

node --check pasa para backgrounds.js y el modulo servido por HTTP 200 coincide
con los bytes locales. Pendiente revision visual del usuario. No se ejecuta
subida ni despliegue. Evidencia:
`build/launcher-random-backgrounds-20261023/http-verification.json`.
Runtime y ejecutable conservados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Cuarta portada del launcher, solo local (2026-10-23)

Se agrega el PNG indicado por el usuario como cuarta portada de la rotacion,
conservando las tres anteriores y el comportamiento actual del launcher.
Copia sin modificar: `build/launcher-assets/background-4.png`.
SHA-256: `aaeb5150fa544bc234314afd0789e43dc49f7999cc85ffd06661a8a0913d0c84`.
Staging restaura la imagen y backgrounds.js la incluye en la secuencia.
Verificados por HTTP los bytes exactos de imagen y modulo; node --check pasa.
Pendiente revision visual del usuario. No se realiza subida ni despliegue.
Evidencia: `build/launcher-fourth-background-20261023/http-verification.json`.
Runtime y ejecutable conservados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Musica del launcher en bucle, solo local (2026-10-23)

El usuario aclara que quiere solo audio del enlace YouTube rbcnKcyI7o4 y un
boton de silencio junto a Pause backgrounds. Se prepara un MP3 local solo de
audio (120.581224 segundos, 3.420.269 bytes) y se usa audio.loop, sin iframe ni
cambio de portadas. El archivo queda ignorado en build/launcher-assets y se
restaura mediante staging; no se sube ni se incluye en Git. Origen:
https://www.youtube.com/watch?v=rbcnKcyI7o4
SHA-256: `0e03bbc0f250396cc70b46b00d2b86dbe635b134032c9f9b7028a27959176560`.

Se agrega music.js, con volumen inicial 30%, silencio recordado en localStorage,
inicio al primer gesto o mediante Play music si el navegador bloquea autoplay,
pausa en pestanas ocultas y detencion al salir del launcher. El boton cambia
entre Mute music y Unmute music; los efectos del menu mantienen su audio propio.
El empaquetador queda preparado para una futura publicacion autorizada; no se
ejecuta despliegue ni push.

Verificados por HTTP cinco recursos con bytes exactos y MIME audio/mpeg del
MP3, ffprobe confirma una unica pista de audio y FFmpeg decodifica el archivo
completo sin errores. node --check pasa para music.js y start.js. Pendiente
comprobar reproduccion, bucle y boton de silencio en el navegador del usuario.
Evidencia: `build/launcher-music-20261023/http-verification.json`.
Runtime y ejecutable conservados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Logo centrado en celular, solo local (2026-10-23)

Se centra horizontalmente el logo de GTA en el breakpoint de hasta 800 px,
con align-self:center y object-position:center. La regla de escritorio se
conserva. CSS local servido por HTTP 200 con bytes exactos y reglas moviles
comprobadas. Pendiente revision visual del usuario tras recargar. No se sube
ningun cambio. Evidencia:
`build/launcher-mobile-logo-20261023/http-verification.json`.
Runtime y ejecutable conservados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Tercera portada del launcher, solo local (2026-10-23)

Se agrega el PNG indicado por el usuario como tercera portada de la rotacion,
conservando las dos anteriores, su intervalo de 8 segundos y el aislamiento
del fondo debajo de los controles. Copia local sin modificar:
`build/launcher-assets/background-3.png`, SHA-256 `72ca33fc6ae821ad6ad91e06492e1fa8d7989421307a21a084b66c432ffb10f1`.
Staging restaura la imagen y backgrounds.js la incluye en la secuencia.
Verificados por HTTP los bytes exactos de imagen y modulo servido; node --check
pasa para backgrounds.js. Pendiente revision visual del usuario. No se realiza
subida ni despliegue. Evidencia:
`build/launcher-third-background-20261023/http-verification.json`.
Runtime y ejecutable conservados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Correccion de capas durante el fundido, solo local (2026-10-23)

La captura del usuario muestra que el fondo nuevo tapa logo, menu y ayuda
inferior, mientras siguen visibles los controles con z-index 2. La regresion
procede del z-index 1 de la portada entrante: scene no tenia un contexto de
apilamiento propio y hero y menu-help tenian orden automatico.

Se aisla scene en z-index 0 y se fija hero y menu-help en z-index 1. Los indices
internos del fundido quedan contenidos debajo de los controles. Se conserva
pointer-events:none en el fondo. No cambia la rotacion ni se realiza despliegue.
Servidor local reiniciado; verificado CSS servido por HTTP 200 con bytes exactos
y las reglas corregidas. Pendiente confirmacion visual tras recargar en el
navegador del usuario.
Evidencia: `build/launcher-background-stacking-20261023/http-verification.json`.
Runtime y ejecutable conservados:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Rotacion de portadas del launcher, solo local (2026-10-23)

Se agrega la segunda portada indicada por el usuario a la imagen de fondo
existente. La copia local persistente es `build/launcher-assets/background-2.png`;
se conserva el PNG sin modificar (SHA-256
`357cf3142da95ae4ae2adb532c5827ff09863da4b6b29fbcbe8feae02b4ef2f6`). backgrounds.js mantiene la lista ampliable
de portadas y alterna dos capas con un fundido de opacidad de 1 segundo cada
8 segundos (curva cubic-bezier(.77, 0, .175, 1)). La imagen entrante se precarga
y decodifica antes de mostrarse; la anterior permanece debajo del fundido.

Se agrega pausa/reanudacion. La rotacion se detiene en pestanas ocultas y queda
inicialmente pausada si el usuario prefiere movimiento reducido. Un fallo de
imagen conserva el fondo visible. Staging restaura las portadas adicionales y
el empaquetador las incluira cuando el usuario solicite publicar. No se sube nada.

Verificados por HTTP seis recursos locales con bytes exactos y MIME PNG/JS;
node --check pasa para backgrounds.js y start.js. Evidencia:
`build/launcher-background-rotation-20261023/http-verification.json`.
Pendiente revision visual del fundido y encuadre en el navegador del usuario.
No cambia el runtime ni el ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Redes y logos originales de contribuidores, solo local (2026-10-23)

Se configura Galavic con X @ga_lavic y su GitHub, sin filas de Discord.
El nombre visible machinebreak cambia a lauta; mantiene su identidad GitHub y
avatar existentes, agrega X @LautaTWT, el servidor Discord y el canal WhatsApp
indicados por el usuario. No se muestra usuario de Discord sin configurar.
Las redes ausentes se ocultan por perfil, incluido al alternar entre tarjetas.

Se reemplazan letras y simbolos genericos por SVG originales de X, GitHub,
Discord y WhatsApp, descargados de sus sitios o archivos de marca oficiales.
Se preservan los bytes y colores; solo cambia su tamano de visualizacion.
Fuentes y propiedad en `tools/web/launcher/social-icons/SOURCES.md`.
El staging restaura los cuatro iconos y el empaquetador los incluira cuando
el usuario solicite publicar; no se ejecuta ninguna subida ni despliegue.

Verificados por HTTP siete recursos locales, bytes exactos y MIME image/svg+xml
de los logos; node --check pasa para contributors.js. Pendiente revision visual
e interactiva del usuario. Evidencia:
`build/launcher-contributor-socials-20261023/http-verification.json`.
No cambia el runtime ni el ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Tarjetas sociales de contribuidores, solo local (2026-10-23)

Al pulsar machinebreak o Galavic se abre una tarjeta con su avatar, nombre y
cuatro filas: X, GitHub, grupo de Discord y usuario de Discord. GitHub conserva
los perfiles ya configurados. Las otras redes quedan inactivas hasta recibir
sus enlaces y nombres del usuario; no se deducen cuentas a partir del nombre.
El usuario de Discord se podra copiar con confirmacion y alternativa de texto
si el portapapeles falla. Se reutilizan cierre con Escape, clic exterior,
boton de cierre, limite de tabulacion y restauracion del foco del launcher.

El modulo contributors.js guarda la configuracion de cada perfil; staging y
empaquetado incluyen el modulo. No se ejecuta despliegue, subida ni push.
Verificados por HTTP los cuatro archivos editados, bytes exactos y MIME de
los modulos; node --check pasa para start.js y contributors.js. Pendientes
revision visual/interactiva (inventario de navegadores vacio) y enlaces de X,
invitaciones de Discord y usuarios de Discord para ambos contribuidores.
Evidencia: `build/launcher-contributor-cards-20261023/http-verification.json`.
No cambia el runtime ni el ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

## Favicon del launcher, solo local (2026-10-23)

Se usa el PNG indicado por el usuario como favicon del launcher. Copia local
persistente en `build/launcher-assets/favicon.png`; stage_launcher lo restaura
en el sitio servido y el HTML lo referencia como image/png. Se conserva la
imagen original (810 x 810) sin modificarla. El empaquetado podra incluirla
cuando el usuario solicite publicar; no se ejecuta ningun despliegue ni subida.

Servidor local iniciado en `http://127.0.0.1:8771/`. Verificados referencia HTML,
HTTP 200, MIME image/png y bytes exactos del favicon por HTTP.
SHA-256: `400dc5c4b4f1c47e3142e94961cc214d4a2bf45685001f673ad5f9d62f340a28`.
Evidencia: `build/launcher-favicon-20261023/http-verification.json`.
No cambia el runtime ni la identidad del ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Pendiente revision visual de la pestana del usuario; no hay navegador disponible
para automatizacion. Las siguientes mejoras del launcher quedan solo en local
hasta instruccion expresa del usuario para subirlas.

## Copia preparada alojada y descarga automatica (2026-10-23)

El usuario autoriza subir los archivos del juego para no seleccionar carpetas.
La causa de la diferencia con local esta comprobada en prepare_singleplayer.py:
el servidor usa variants/singleplayer/prepared con DLL auxiliares preparadas y
reubicadas, no los bytes de las DLL instaladas. En particular vorbisFile.dll
procede de vorbisHooked.dll antes de su preparacion. Las correcciones anteriores
de importacion no hacian equivalentes estas dos carpetas.

Se aloja la copia preparada (417 archivos, 5.004.941.035 bytes) en R2, build
`a033b7fd3a69b951`. Los archivos grandes se transfieren en bloques de 64 MiB.
El Worker solo sirve objetos del inventario y del build configurado. El launcher
inicia la descarga al abrir la pagina si la copia no esta lista, conserva los
archivos terminados para reintentos y comprueba hashes de bloques y archivos
antes del sello final. OPFS mantiene los archivos del juego separados de los
perfiles; no se suben partidas, credenciales ni archivos del juego a Git.
En esta configuracion se ocultan los botones de seleccion de carpeta/ZIP.

Publicado Worker `8f22e343-0b9a-423a-8246-62a13ff72f7b`. Verificados por HTTPS
los seis recursos cambiados con bytes exactos, HEAD y tamanos de los 461 objetos
de transferencia con COOP/COEP, descarga y SHA-256 del ejecutable y las cuatro
DLL, y descarga/hash de un bloque completo de 64 MiB. Evidencia local:
`build/cloudflare-release-20261023-hosted-game/http-verification.json` y
`build/cloudflare-release-20261023-hosted-game/chunk-verification.json`.
Pasan 39 pruebas Node y 7 Python (incluyen descarga por bloques, corrupcion,
fallos HTTP, reanudacion, aislamiento y empaquetado/subida sinteticos).

Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm publico conservado:
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Pendiente: primera preparacion completa y siguiente arranque en navegador del
dominio publico. La herramienta de navegador devuelve inventario vacio, por lo
que no se afirma verificacion interactiva ni gameplay en este despliegue.
Se conserva debajo la evidencia de las etapas anteriores y sus identidades.

## DLL automaticas durante la importacion de carpeta (2026-10-23)

A peticion del usuario, la importacion de carpeta prepara las DLL requeridas
sin una seleccion adicional: normaliza sus nombres antes de copiar a OPFS,
comprueba que estan en la carpeta antes de copiar archivos grandes y valida
los hashes guardados antes de escribir el sello de importacion completada.
La reimportacion vuelve a copiar una DLL corrupta aunque su tamano y fecha
coincidan con el manifiesto anterior. La misma logica sirve para ZIP.
Si la carpeta carece de una DLL o contiene otra version, informa el nombre;
no puede obtener del disco un archivo que no fue seleccionado.

Pasan 20 pruebas Node: importacion automatica con mayusculas, ausencia previa
a copia, rechazo de DLL incompatible sin sello y reparacion en reimportacion,
ademas de transporte y recuperacion selectiva. Publicado en el Worker
`8eaa36fc-b735-4a68-a4e2-966a6e5b800b`; verificados por HTTPS core.js, app.js
y games.json con bytes exactos, MIME y aislamiento. Evidencia local:
`build/cloudflare-release-20261023-auto-dll-import/http-verification.json`.
Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm publico conservado:
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Pendiente verificar importacion real y arranque en navegador; no se afirma gameplay.

## Recuperacion de DLL en el dominio publico (2026-10-23)

La captura del usuario muestra `Missing eax.dll` tras importar y pulsar jugar
en gta.galavic.world. El launcher solo validaba sello y carpetas; el player
publico rechazaba las DLL ausentes sin ofrecer una recuperacion selectiva.
Ahora el launcher comprueba los hashes reales de las cuatro DLL auxiliares.
El boton `Complete DLLs` abre el player, donde `Select missing DLLs` permite
seleccionar archivos locales compatibles sin repetir la importacion del juego.
Se validan antes de escribir, se comprueba la copia y se normalizan nombres
con mayusculas para OPFS. Los archivos permanecen en el navegador; los perfiles
no se modifican. No se publican DLL ni se habilita /install en el servidor.

Publicado en el Worker, version `74b671b5-2fe8-4298-b981-cf78b03c9db3`.
Verificados por HTTPS seis recursos con bytes exactos, MIME y COOP/COEP.
Pasan 30 pruebas Node y 6 Python, incluyendo espera de seleccion, rechazo,
reintento y continuacion tras una reparacion sintetica. Evidencia local:
`build/cloudflare-release-20261023-dll-recovery-v2/http-verification.json`.
Ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm publico conservado:
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Pendiente: seleccion de DLL compatibles y siguiente arranque real en el
navegador del usuario. Estas pruebas no verifican gameplay.

## Dominio gta.galavic.world activo en Cloudflare (2026-10-23)

El usuario anadio los nameservers gracie.ns.cloudflare.com y
yahir.ns.cloudflare.com en Namecheap. La delegacion propago y la zona
galavic.world (cfec2730fb45705cb99e6e5af8e8f0f0) figura active desde
2026-10-23T20:23:35Z. El apex conserva el A de Vercel, los MX de
registrar-servers.com y el SPF; solo se movieron los nameservers. El origen
Vercel del apex responde 402 con x-vercel-error DEPLOYMENT_DISABLED tambien
de forma directa (216.198.79.1), por lo que esa incidencia es anterior a la
migracion y ajena a este cambio. www.galavic.world sigue sin registro, igual
que antes.

gta.galavic.world se sirve desde el Worker gta-sa-oc mediante custom domain,
no desde el hostname de Pages. HTTPS responde 200 con certificado Let's
Encrypt de la zona (expira 2027-01-21) y HTML con COOP/COEP. Los dos objetos
del runtime responden 200 con application/wasm y application/octet-stream,
266206438 y 35073821 bytes, cache inmutable y las mismas cabeceras de
aislamiento; /install y un build de runtime desconocido responden 404. El
endpoint Pages gta-galavic.pages.dev sigue respondiendo 200.

Se publica el Worker version b21fe8f6-1302-400e-a203-819591463bba, que
conserva la redireccion 301 de HTTP a HTTPS y retira el credito "Ported by /
San Andreas Community" del launcher (HTML y CSS). El endpoint Pages
gta-galavic.pages.dev se redespliega como 2e4a07f7 con los mismos assets y
worker; ambos siguen sirviendo el runtime desde el mismo bucket. Los assets y
el runtime R2 son los mismos de c94da1d7. tools/tests/worker.test.mjs cubre
redirect, cabeceras, runtime, 404 y 405; 6/6 tests pasan. Tambien se actualizan
fixtures y aserciones obsoletas de player_boot y test_serve_variant: pasan 16/16
tests JS de tools y 12/12 tests Python de tools.

Pendiente: el custom domain homonimo del proyecto Pages queda pending
("CNAME record not set") porque el Worker ocupa el hostname; no sirve trafico
y conviene retirarlo desde el panel. No se verifica gameplay ni importacion en
el dominio nuevo: OPFS es por origen, asi que hace falta importar de nuevo la
carpeta del juego en gta.galavic.world. La resolucion nativa 1080p sigue sin
verificarse.

## Cambio de DNS a Cloudflare solicitado; creacion de zona bloqueada (2026-10-23)

Superado por la seccion superior; se conserva como evidencia del bloqueo inicial.

El usuario solicita gestionar galavic.world en Cloudflare DNS. Confirma que solo
usa la web apex en Vercel y deja su migracion de contenido para otra tarea.
Se consulta la cuenta conectada: no existe una zona galavic.world. El POST de
creacion de zona full recibe HTTP 403: falta el permiso de cuenta zone.create.
La sesion OAuth actual permite el despliegue pero no esta operacion. No hay
credenciales de Namecheap ni navegador habilitado para crear la zona por UI.

Falta que el usuario anada galavic.world en Cloudflare, plan Free. Despues se
pueden leer los nameservers asignados, crear el CNAME gta al Pages existente y
completar en Namecheap el cambio a Custom DNS. Aun no hay nameservers Cloudflare
asignados, no se ha creado la zona ni cambiado DNS, apex o correo. La web sigue
publicada en gta-galavic.pages.dev y gta.galavic.world sigue pendiente de DNS/TLS.

## Dominio gta.galavic.world preparado (2026-10-23)

El usuario solicita el subdominio de galavic.world, registrado y servido por
DNS de Namecheap. La zona no esta incorporada a Cloudflare; el apex tiene su
sitio existente y MX de Namecheap. Se elige Pages con funcion avanzada + R2 para
conectar solo el subdominio mediante CNAME, conservando el resto del DNS.

Proyecto gta-galavic, https://gta-galavic.pages.dev/ , despliegue 4dda85ca.
El hostname gta.galavic.world ya esta registrado en Pages; el estado inicial de
Cloudflare es initializing/verificacion pending. Falta guardar en Namecheap un
CNAME con host gta y destino gta-galavic.pages.dev, TTL Automatic. No hay acceso
a Namecheap ni superficies de navegador habilitadas en esta sesion para guardarlo.
No se han cambiado los nameservers, registros apex ni correo.

El nuevo endpoint Pages, launcher, reproductor y ambos endpoints R2 responden
200 con COOP/COEP; MIME application/wasm correcto. Se conserva el mismo bucket y
Wasm publico `5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Pendiente: DNS CNAME, emision TLS y comprobacion HTTPS en gta.galavic.world.
No se verifica gameplay ni se resuelve la incidencia de resolucion con este cambio.

## Publicacion en Cloudflare Workers y R2 (2026-10-23)

Web publicada: https://gta-sa-oc.enrimilioano09.workers.dev/ . Worker gta-sa-oc, version
c94da1d7-cb1a-4d44-ad5d-83455ef2fb1f. Bucket privado gta-sa-oc-runtime;
el Worker solo permite GET/HEAD de los dos objetos del runtime de esta version.
El usuario autorizo publicar el proyecto y dejo sin efecto las restricciones
anteriores que impedian alojar artefactos generados. Los binarios siguen fuera de Git.

20 archivos estaticos del launcher/reproductor y 2 objetos R2 verificados desde
el dominio publico, con SHA-256, MIME e aislamiento COOP/COEP. Wasm (266206438 bytes)
y data (35073821 bytes) se sirven como streams bajo el mismo dominio. La preparacion
publica elimina prefijos personales de cadenas del compilador sin cambiar longitud
ni instrucciones. V8 completo valida ese Wasm. Las rutas /install y los objetos
R2 no permitidos responden 404. Se incluyen medios seleccionados del launcher,
fuente CSS y efectos de sus botones; no se sube la instalacion del juego, sus DLL,
archivos de mundo/modelos, pruebas locales ni volcados o registros privados.

Wasm local de origen:
`4530b7f65c519561952cd2e70044719650f32d99633d9d4c8a143f29e2af5e74`.
Wasm publico con cadenas de rutas saneadas:
`5889d8ddf6efc047b12791dad6cc1f526447d35f5d67f5865a37e195601fe036`.
Se conserva la logica del juego y la incidencia de resoluciones sigue pendiente.
No se verifica gameplay ni importacion real en el dominio publico. Cada usuario
necesita importar su carpeta compatible completa con las DLL esperadas; la reparacion
automatica desde el servidor local se sustituye por validacion local. OPFS esta
separado por dominio: la importacion de localhost no se transfiere a esta web.

Fuente del despliegue: cloudflare/worker.mjs y tools/prepare_cloudflare.py.
Instrucciones en cloudflare/README.md. Evidencia de despliegue privada bajo build/.

## Resolucion: el usuario sigue sin ver 1080p (2026-10-23)

El usuario indica que no observa cambios y 1080p no aparece tras la compilacion
`35a69f19cc7f7964408df5a4356a1c61495e1c742f358ed4bcc562e6e4f7ab97`.
La correccion del presupuesto de memoria NO esta verificada como solucion completa.
Se mantiene pendiente el menu real y el cambio de resolucion nativa.

Se sirven recursos con query de identidad SHA para diferenciar compilaciones,
y el log local indica Player build con SHA completo. GetAvailableVidMem registra
hasta cuatro resultados (presupuesto, punteros y validez); la enumeracion D3D9
registra de forma acotada formatos, conteos y dimensiones. No imprime por frame.
Se prepara una URL de diagnostico con PERF_WATCH generico que lee, sin modificar,
los campos auditados de VRAM y el puntero a la lista de modos. Los logs siguen
ocultos por defecto. Falta que el usuario inicie esta compilacion y abra el menu;
no se dispone de acceso interactivo al navegador para hacerlo desde esta sesion.

Wasm de diagnostico servido: `4530b7f65c519561952cd2e70044719650f32d99633d9d4c8a143f29e2af5e74`.
Compilacion web, V8 y entrega JS/Wasm/data por HTTP verificadas. No se ejecutan
suites de pruebas ni se aplica estirado. La evidencia no verifica modos del menu.

## Resoluciones nativas ocultas por presupuesto de VRAM (2026-10-23)

El usuario muestra que el menu original ofrece solo 640x480 a 16/32 bits.
Se auditaron los bytes del PE original
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`:
GetVideoMemInfo en 007455e0 obtiene la memoria mediante DirectDraw7;
GetVideoModeList en 00745af0 conserva la excepcion 640x480 y descarta los demas
modos cuando VRAM libre menos el framebuffer no supera 45 MiB (00745bf6).
La implementacion DirectDraw devolvia solo 24 MiB libres y 32 MiB totales.
La tabla D3D9 ya contiene 1280x720 y 1920x1080; no faltaban esas entradas.

Se unifican GetCaps y GetAvailableVidMem en un presupuesto virtual de compatibilidad
de 256 MiB totales / 224 MiB libres, coherente con el adaptador D3D9 modelado.
No es una medicion de memoria fisica ni una reserva adicional de GPU. Se mantiene
el filtrado original y el cambio de modo original de GTA mediante Reset; no se
modifican la proyeccion, el aspect fit, la camara ni los recursos del juego.
El intento anterior de estirar se retiro antes de compilar o servirlo.
Referencia de apoyo: https://github.com/gta-reversed/gta-reversed/blob/master/source/app/platform/win/VideoMode.cpp

Compilacion web y validacion completa V8 pasan. JS/Wasm/data coinciden entre
salida, sitio y HTTP; cero imports invoke_. No se ejecutan suites de pruebas.
Wasm nuevo: `35a69f19cc7f7964408df5a4356a1c61495e1c742f358ed4bcc562e6e4f7ab97`.
Pendiente: el usuario recarga, elige una resolucion panoramica con izquierda/derecha
y aplica con Enter. Aun no se verifica el menu ni el cambio de modo en navegador.
Esta compilacion no acredita gameplay adicional ni rendimiento.

## Logs ocultos al entrar al juego (2026-10-23)

El reproductor servido comienza con todo el panel de logs oculto. El boton
Show logs y F8 permiten abrirlo y volver a ocultarlo. Los avisos no quitan el
atributo hidden; el registro sigue disponible. Se actualiza solo HTML mediante
stage_player(), sin ejecutar pruebas ni recompilar, por peticion del usuario.
Verificacion interactiva pendiente. Wasm conservado:
`610f22f845bb15950ce369a39b92de908f191e9897860b1b8460444f48242f40`.

## Launcher en ingles (2026-10-23)

Textos, accesibilidad, ayuda de guardado, biblioteca, estados y errores del launcher
pasan a ingles. Se elimina la capa que convertia mensajes originales del runtime
al espanol, conservando el seguimiento de estado y progreso y los controles.
El mensaje de timeout y el estado de indisponibilidad del runtime tambien se
traducen; el cambio se incluye en el parche completo.

Verificado: sintaxis JavaScript, cuatro pruebas del transporte, HTML/start/app
servidos identicos a los archivos locales. Verificacion visual pendiente.
Sin cambio nativo; Wasm conservado:
`610f22f845bb15950ce369a39b92de908f191e9897860b1b8460444f48242f40`.

## Tamano de texto del launcher (2026-10-23)

Los textos de estado, credito, ayuda, contribuidores, biblioteca y progreso usan
la misma variable CSS que los botones principales: 18-23 px segun el viewport,
19 px en pantallas estrechas. Se mantiene la fuente local de San Andreas.
Los avatares pasan a 48 px y las pantallas estrechas distribuyen los bloques en
flujo vertical con desplazamiento para evitar superposiciones al ampliar textos.
Se conserva el fondo, el logo y el comportamiento del launcher.

Verificado: CSS servido por HTTP identico a la fuente, sin tamanos de texto de
11-14 px; comprobacion visual de esta revision en navegador pendiente. Cambio
solo de presentacion, sin recompilacion ni nueva verificacion de gameplay.
Wasm conservado: `610f22f845bb15950ce369a39b92de908f191e9897860b1b8460444f48242f40`.

## Organizacion del repositorio (2026-10-23)

Se movieron 70 scripts Python y el preparador PowerShell de la raiz a tools/.
Se actualizaron sus rutas de proyecto, llamadas entre scripts, imports de pruebas
y comandos documentados. BROWSER_STATUS.md y PORT_STATUS.md estan en docs/archive/;
el README anterior tambien se conserva alli. La raiz presenta el acceso al proyecto,
la configuracion y las dependencias. No se eliminan auditorias ni datos de evidencia.

La limpieza se publica sobre el commit remoto ff15470 y conserva su parche completo
y el gitlink del runtime. No cambia el ejecutable ni establece nuevo gameplay. Pasan 92 pruebas en el
arbol de publicacion y 100 en la copia local; todos los scripts Python parsean.
Los ajustes locales pendientes del launcher y runtime se mantienen separados.

## Contribuidores en el launcher (2026-10-23)

La esquina inferior derecha muestra machinebreak y Galavic con sus avatares y
perfiles enlazados, ademas del enlace al listado del repositorio. Lista consultada
en https://api.github.com/repos/Galavic/Gta-SA-OC/contributors?per_page=100 en esta
fecha; el contenido HTML es una instantanea, no una consulta durante cada arranque.
Se conserva la fuente local del menu, el fondo y el logo existentes. Los avatares
publicos de GitHub usan CORS anonimo; no se publican recursos originales del juego.
HTML/CSS servidos coinciden con las fuentes y ambos avatares responden 200 con
Access-Control-Allow-Origin: *. Verificacion visual en navegador pendiente.
Sin cambios al ejecutable Wasm servido
`610f22f845bb15950ce369a39b92de908f191e9897860b1b8460444f48242f40`.

## Pantalla completa y Escape mantenido (2026-10-23)

El reproductor solicita pantalla completa y Pointer Lock desde el clic explicito
en el canvas; tambien ofrece un boton de pantalla completa. En pantalla completa
solicita Keyboard Lock exclusivamente para Escape. No intercepta el Escape corto:
sigue llegando a SDL y al menu original. La salida con Escape mantenido queda a
cargo del navegador (Chrome documenta unos dos segundos), sin recaptura automatica.
Salir de pantalla completa libera el puntero; perder foco libera teclado y puntero.
Los rechazos de permisos y la ausencia de Keyboard Lock se notifican en los logs;
en esos casos el navegador conserva su comportamiento de Escape corto.

Referencia: https://developer.chrome.com/blog/better-full-screen-mode y
https://developer.chrome.com/articles/keyboard-lock . Esta capacidad depende del
soporte y permiso del navegador y de pantalla completa iniciada por la pagina.

Verificado: cuatro pruebas Node con eventos/APIs simulados, seis pruebas Python
del servidor, HTML local identico al servido por HTTP con aislamiento COOP/COEP.
No hay recompilacion nativa: se conserva Wasm
`610f22f845bb15950ce369a39b92de908f191e9897860b1b8460444f48242f40`
y el PE original `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Pendiente: prueba real del permiso, Esc corto en menus y Esc mantenido en el
navegador del usuario. Las pruebas simuladas no verifican esos gestos del navegador.
No se retoma optimizacion.

## Limites del cursor y clics coherentes con Pointer Lock (2026-10-23)

La captura del usuario muestra que el cursor original ya aparece en Language,
pero se detiene antes de Back. La integracion relativa limitaba sus coordenadas
al modo inicial de 640x480; el log muestra CreateDevice/Reset a 800x600. La ruta
Direct3D puede ajustar el cliente invitado sin pasar por el callback de modo
DirectDraw que actualizaba esos limites.

Se consulta el rectangulo del cliente invitado bajo el baton al integrar el
movimiento. Ese tamano positivo gobierna los limites; el modo anterior queda
como respaldo si no hay ventana valida. Los deltas DirectInput permanecen sin
limitar. Ademas, botones y rueda decodifican si el evento ocurrio con Pointer
Lock y usan la misma posicion virtual al entregarse: no vuelven a mapear la
posicion absoluta fija del navegador ni generan deltas adicionales. Las rutas
sin bloqueo conservan su mapeo existente.

Compilacion web, V8 completo, comprobaciones de fuentes y parche inverso pasan.
JS/Wasm/data coinciden entre salida, sitio y HTTP. Wasm servido: `610f22f845bb15950ce369a39b92de908f191e9897860b1b8460444f48242f40`.
No se ejecuta la suite host_tests, cuyo bloqueo anterior en esta variante por
macros ajenas permanece documentado. Queda pendiente comprobar en navegador
que se alcanza Back y los cuatro bordes, que los clics no saltan y que la camara
sigue libre. La captura confirma el cursor visible de la revision anterior;
no se midio directamente el hash del binario cargado en esa pesta?a.
Evidencia privada: build/cursor-bounds-20261023.

## Cursor original del menu con Pointer Lock (2026-10-23)

El usuario informa que desaparece el cursor del juego al bloquear el raton.
La ruta relativa agregada anteriormente enviaba DirectInput pero omitia
WM_MOUSEMOVE. El menu original consume las posiciones de ese mensaje para
actualizar y mostrar su sprite de cursor. Se confirma en el ejecutable local
que el caso en 00748323 escribe las dos coordenadas (evidencia privada con su
identidad original a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26).

La ruta relativa devuelve ahora si el movimiento se entrego; el host publica
WM_MOUSEMOVE con la posicion absoluta limitada, ademas de conservar los deltas
sin limitar para DirectInput. Ambas entregas se hacen bajo el baton del scheduler.
Si un mod consume el evento, no se publica el mensaje. No se agrega un cursor
superpuesto del navegador ni se cambia la logica original de visibilidad del
menu. Se extiende la regresion de movimiento relativo para comprobar entrega.

Compilacion web, validacion V8 completa, limites de fuentes y revision del
parche completo pasan. JS/Wasm/data coinciden entre salida, sitio y HTTP;
no hay imports invoke_. Wasm servido: `c2642c996ba595e58b403193f404ffee960d94a33e9fea40cb21cc978b566567`.
La suite host_tests no se ejecuto en este cambio: el intento anterior en esta
variante sigue bloqueado por macros de otro juego, documentado en la evidencia
de pointer-lock-20261022. Sigue pendiente verificar visualmente el cursor del
menu/pause, su clic y la camara en navegador. La compilacion no prueba esa
interaccion. Evidencia privada: build/menu-cursor-20261023.

## Sonidos originales de menu para el launcher (2026-10-23)

Banco frontend 60 de la copia local: pares 4/5 para resaltar y 6/7 para confirmar,
segun AEFrontendAudioEntity.cpp de gta-reversed. El exportador existente admite
salida explicita y --menu-only, preservando el modo previo. WAV estereo privados
bajo el sitio ignorado; ningun sonido se incorpora a Git.

Hover y foco de teclado usan resalte; clic confirma. Web Audio se desbloquea en
la primera interaccion. Se excluyen botones deshabilitados y movimientos entre
hijos; el clic interno reenviado por Jugar no duplica la confirmacion. Antes de
navegar se espera el efecto, con un maximo de 350 ms para no bloquear el inicio
si el audio no responde. No hay musica ni cambios al sonido del motor.

Pasan 4 pruebas Node de eventos/audio simulado y 6 pruebas Python del servidor.
Se verifican HTTP, MIME/sintaxis JS, muestras no silenciosas y WAV estereo de
16 bits a 44,1 kHz: resalte 0,1424 s, confirmar 0,1602 s. Escucha y operacion en
navegador pendientes. Antes del primer clic/tecla el navegador puede bloquear
el sonido de hover.
Fuente:
https://raw.githubusercontent.com/gta-reversed/gta-reversed/master/source/game_sa/Audio/Entities/AEFrontendAudioEntity.cpp

## Tarjetas oscuras segun la referencia (2026-10-23)

Se aplica el acabado gris oscuro con marco y relieve de la referencia del usuario
a los paneles de progreso y biblioteca, almacenamiento, tarjeta de juego, avisos
y controles de ayuda. Se mantienen los botones claros y la fuente local comun.
Los indicadores de importacion usan barras claras sobre recuadros oscuros.
El cambio es solo CSS; la hoja servida coincide por HTTP con la fuente del
proyecto. La revision visual en navegador sigue pendiente. No cambia el motor.

## Una misma fuente para todos los textos del launcher (2026-10-23)

El usuario pide extender la letra de los botones a toda la pantalla. Se genera
una fuente CSS local a partir de los glifos del subfont de menu en fonts.txd y
sus avances de fonts.dat. Las siluetas se construyen por franjas del canal alfa,
con umbral 96, mediante FontTools; los glifos latinos descompuestos conservan
el mismo mapeo usado por el renderizador anterior. La fuente resultante queda
en el sitio ignorado original-menu/menu.ttf, sin publicar recursos del juego.

Se aplica Local SA Menu por herencia a titulos, avisos, controles, botones y
biblioteca. Se elimina el renderizador canvas por etiqueta: el navegador ajusta
ahora los parrafos y mensajes dinamicos de forma normal, conservando el texto
HTML accesible y los observadores existentes. Se mantienen los colores de
texto/botones. FontTools se declara en tools/web/launcher/requirements.txt.

Se comprueban la familia, cobertura de caracteres habituales y coincidencia
HTTP de la fuente. Tras reiniciar el servidor con respaldo de logs, se confirma
Content-Type font/ttf; las seis pruebas Python pasan con asercion de ese MIME.
Identidad de la fuente generada en esta comprobacion: `de807ae588d1146e250fac589b73181a8c2c829a483143817eb9c510a586cf89`.
La apariencia en navegador sigue pendiente de revision del usuario; no se toca
el motor ni su compilacion.

## Botones segun la referencia del usuario (2026-10-23)

Se aplica a las acciones del launcher el acabado de la referencia: gris claro,
relieve con borde doble, esquinas pequenas, sombra inferior y texto negro
centrado. Las opciones principales conservan los glifos originales de San Andreas,
recoloreados en negro, sin el contorno negro del menu previo. La seleccion se
indica con un borde exterior y el estado pulsado baja tres pixeles. Se conservan
logo, fondo y funciones. Los botones de biblioteca comparten el mismo acabado.
Sintaxis JS y 6 pruebas del servidor pasan; CSS/JS coinciden por HTTP. Revision
visual en navegador pendiente; no se cambia el motor ni sus archivos.

## Correccion de MIME para modulos JavaScript (2026-10-23)

La siguiente captura del usuario muestra Failed to fetch dynamically imported
module para repair-import.mjs. La comprobacion HTTP encontro respuesta 200 con
Content-Type text/plain, heredado de las asociaciones MIME de Windows. Es una
regresion introducida al agregar el modulo de reparacion: verificar bytes y
sintaxis no detecto que el navegador rechazaria ese tipo. font-layout.mjs tenia
el mismo problema, lo que tambien impedia cargar el renderizador de letras.

Handler declara ahora application/javascript para .mjs y .js, y application/wasm
para .wasm, independientemente del registro del sistema. Se respalda el log y
se reinicia solo el servidor de esta tarea. Las seis pruebas Python pasan,
incluida una peticion HTTP de modulo que comprueba Content-Type. Las respuestas
HEAD del servidor real confirman los cuatro recursos (reparacion, mapeo de fuente,
renderizador y Wasm) con los tipos correctos. La siguiente carga del navegador
y el arranque del juego siguen pendientes; no se afirma verificacion interactiva.

## Reparacion de DLL auxiliares antes del arranque (2026-10-23)

La captura del usuario y el log local muestran que el motor no puede leer
`eax.dll` junto al ejecutable en OPFS. La configuracion actual exige cuatro DLL
auxiliares; el servidor tiene las cuatro y entrega los hashes configurados.
La validacion previa solo comprobaba ejecutable, sello y carpetas, por lo que
una importacion anterior podia pasar sin estas nuevas DLL.

Se agrega un inventario generado desde modules.aux (solo nombre, tamano, hash e
identidad del ejecutable) y una reparacion local previa a WebGPU/Wasm. Comprueba
los archivos reales de OPFS; si faltan o no coinciden, descarga solo esa DLL del
servidor local, valida SHA-256 antes de escribir y vuelve a leerla para comprobar
la copia. Las importaciones grandes y los perfiles no se tocan. Los fallos de
red/escritura se muestran antes de iniciar el motor. No se modifica el Wasm.

Pasan 6 pruebas Python y 16 Node, incluidos casos de archivo ausente, correcto,
corrupto, descarga incorrecta y fallo de escritura. Se comprueban por HTTP las
cuatro DLL y el orden/sintaxis del script servido. Queda pendiente verificar la
reparacion y el siguiente arranque en el navegador del usuario. Identidad Wasm
servida en esta comprobacion: `d5da9162b55b676be96256ba082d1d00dbc43747752f8addc85a2b414137f7cf`.

## Fondo elegido por el usuario (2026-10-23)

Se reemplaza el fondo local por el nuevo PNG indicado por el usuario, conservando
su contenido sin modificar, a pantalla completa con cover. El staging restaura
la imagen desde build/launcher-assets/background.png; el archivo queda ignorado,
sin publicar la imagen ni la ruta personal de origen. Se conserva el logo elegido
y la tipografia original. 120130e14ad09aa7c75746046179ff33b9c68325993f617997483b44ee04d7ef-256 servido: `120130e14ad09aa7c75746046179ff33b9c68325993f617997483b44ee04d7ef`.
La copia HTTP coincide con el archivo elegido; revision visual en navegador
pendiente. No se modifica el juego.

## Logo PNG elegido por el usuario (2026-10-23)

Se incorpora como imagen del encabezado el PNG especificado por el usuario en
PNGmart. Se descarga sin modificar al cache privado build/launcher-assets y el
staging lo copia al sitio local. Dimensiones: 1965x1814; SHA-256
`e3c54f3082f1e2461bb74b80d521c68a53cdaf07f6ec4ed0a748504fa83d507c`.
Se mantiene la foto de fondo, la fuente original y las funciones del launcher.
La imagen no se incorpora a Git. tools/prepare_launcher_logo.py reproduce la
descarga comprobando firma y hash. HTTP entrega la imagen exacta y el HTML la
referencia; 5 pruebas del servidor pasan. Revision visual en navegador pendiente.

## Fuente original de San Andreas para el launcher (2026-10-23)

A peticion del usuario se retira la fuente de sustitucion UnifrakturCook. El
launcher decodifica fonts.txd y lee los avances proporcionales de data/fonts.dat
de la copia local preparada. Las opciones se dibujan con los glifos originales
del subfont de menu (font2, estilo 2); los titulos de biblioteca usan estilo 0.
Se reutiliza el mapeo de glifos existente, con texto accesible separado y repintado
al cambiar la etiqueta o el tama?o. Se conserva la foto de fondo sin cambios.

El exportador y renderizador son codigo publicable; las imagenes de fuente y
sus medidas quedan solo en el sitio ignorado original-menu. No se publican
assets del juego. Si no estan disponibles, queda texto HTML normal como respaldo.
Los recursos se verifican identicos por HTTP, la sintaxis Node pasa y las 15
pruebas previas pasan. Se inspecciono el atlas y su canal alfa localmente; queda
pendiente la comprobacion visual en navegador. No cambia la compilacion Wasm.

## Launcher con menu clasico y fondo completo (2026-10-23)

Se conserva intacta la foto local background.png con su logotipo integrado;
ocupa toda la ventana con cover, sin filtros ni capas que la oscurezcan.
Se retiran titulo duplicado, SVG superpuesto, ticker de colores y panel de
controles. Menu en blanco/gris, sombra negra, tipografia gotica y seleccion
simple; biblioteca con panel oscuro recto. Se conservan importaciones, partidas,
estados de error, reintento y navegacion por teclado.

Fuente UnifrakturCook original embebida en CSS, SIL OFL 1.1; licencia completa
en tools/web/launcher/FONT-LICENSE.txt. Origen: google/fonts,
ofl/unifrakturcook/UnifrakturCook-Bold.ttf. No necesita conexion externa.
La imagen sigue local y no se publica. Recursos de pantalla identicos por HTTP;
15 pruebas pasan. Revision visual del navegador pendiente (sin navegador en
la herramienta). El juego y su Wasm no cambian. Se inicia el servidor con WMI
oculto para mantenerlo disponible despues de cerrar el proceso de terminal.

## Continuacion del launcher de DeepSeek (2026-10-23)

Por indicacion del usuario se detiene el trabajo de optimizacion y se continua
con el launcher. Se encontro la pantalla y start.js solo en la carpeta generada
del sitio: se conservaron en tools/web/launcher y se agrego stage_launcher para
restaurarlos al iniciar el servidor, junto a app/core/worker del runtime.
Se conserva el fondo local existente; ninguna imagen ni asset del juego se
incorpora al repositorio. El SVG incluido proporciona una alternativa visual.

La consulta de estado tiene ahora un limite de 15 segundos. Los fallos del
worker rechazan las solicitudes pendientes y el error se muestra en la biblioteca
con Volver a comprobar, sin exigir importar otra vez. Ese limite no afecta a las
importaciones, que pueden durar varios minutos. Se conserva el timeout que dejo
DeepSeek para las consultas opcionales de espacio/persistencia. No se afirma una
causa de bloqueo confirmada en navegador. El servidor estaba apagado y se inicio
de nuevo, respaldando los logs previos antes del arranque.

Verificacion: 5 pruebas Python del servidor/staging y 10 pruebas Node (6 del
importador y 4 del transporte), sintaxis de cuatro modulos y coincidencia HTTP
de la pantalla y scripts. La herramienta de UI no devuelve navegadores: quedan
pendientes la revision visual y el estado real del OPFS del usuario. Durante este
trabajo no se recompilo ni cambio el Wasm, que conserva la identidad
`d5da9162b55b676be96256ba082d1d00dbc43747752f8addc85a2b414137f7cf`.

## Captura del raton en el navegador (2026-10-22)

Implementada la solicitud de Pointer Lock al hacer clic en el canvas una vez
inicializado el runtime. Escape o perder el foco libera el raton; la captura
solo se solicita de nuevo con otro clic. El navegador oculta el cursor.
El estado se publica mediante un atomico de la capa de plataforma; los eventos
SDL relativos se encolan y se entregan a DirectInput bajo el baton del scheduler.
Sus deltas se conservan aunque la posicion absoluta alcance el borde, con
acumulacion fraccionaria y sin correccion hacia un cursor absoluto fijo.
Se conserva el control de logs por boton/F8.

Compilacion web y validacion completa V8 pasan; JS/Wasm/data coinciden entre
origen, sitio y HTTP. Wasm servido: `d5da9162b55b676be96256ba082d1d00dbc43747752f8addc85a2b414137f7cf`.
Pasan cuatro pruebas del servidor, sintaxis JS y simulacion DOM de captura,
liberacion, foco, errores de permiso y proteccion antes de inicializar el runtime.
La suite host_tests no compila en esta configuracion por referencias antiguas
RECOMP_GLOBAL_SIMULATION_TURN_ADDR/COMMAND_FRAME_ADDR y hooks de raton de otro
juego; la nueva regresion relativa queda sin ejecutar. No se afirma validacion
de la camara en navegador: queda pendiente comprobar giro continuo y Escape en
la partida. La meta de 60 FPS sigue pendiente. Evidencia privada separada de las
mediciones historicas en build/pointer-lock-20261022.

## Control de logs del reproductor local (2026-10-22)

El reproductor servido incorpora un boton para ocultar el panel completo y el
atajo F8 para alternarlo. La captura de logs sigue activa; los avisos posteriores
no vuelven a mostrar un panel ocultado por el usuario. Al mostrarlo se expande y
el foco regresa al juego. Se verificaron HTTP local, sintaxis JavaScript, control
con click/F8, repeticion de tecla y persistencia ante avisos con DOM simulado;
las cuatro pruebas del servidor pasan. Interaccion visual en navegador pendiente.
Solo cambia HTML; conserva Wasm
`f0fc5978a330d36846879f7d8996409662cab43210c43e1a9678ed036a44a49f`.
La captura relativa del raton y la meta de 60 FPS siguen pendientes.

## Corrección de retiro de texturas WebGPU; 60 FPS aún pendientes (2026-10-22)

La ejecución diagnóstica sirviendo
`044083ea544b8a014dfa2d706d8d42968c0a220a757610883b7b282c9ec98be0` registró limitador de
menú=0, replay=0, frameLimit=30 y beat count=0 en una fase ligera de frontend
/carga. No verifica el estado de esas condiciones durante gameplay. Tras una
ventana de unos 2.700 frames del backend aparecieron errores de asignación
CreateCommittedResource/CreateTexture y después objetos/comandos inválidos.
No se trata esa cifra de frames ni el ritmo del menú como evidencia de 60 FPS.

El dispositivo WebGPU genérico soltaba referencias de texturas propias sin
solicitar su destrucción explícita. El SDK instalado elimina la entrada JS al
liberar el handle; su TextureDestroy es una llamada separada a destroy(). Se
corrigió esa ruta: la textura se destruye cuando ya no quedan encoders abiertos
que puedan necesitar enviarla, conservando el handle hasta entonces. Según
[la especificación](https://www.w3.org/TR/webgpu/#texture-destruction), el agente
puede recuperar esa memoria cuando terminan los usos previamente enviados.
Los recursos importados siguen siendo externos y los drawables del canvas
solo sueltan su referencia, para permitir la presentación del navegador.

Con PERF_STATS se informan cada 1.000 destrucciones las creaciones,
destrucciones y diferencia de las texturas propias rastreadas. No incluye
las importadas ni las del canvas, y no mide VRAM física. La relación entre
esta ruta y el agotamiento observado es una hipótesis de corrección que aún
requiere reproducir la sesión en navegador; no se declara resuelto el OOM.

Build, compilación completa V8 y entrega idéntica por HTTP pasan. Wasm servido:
`f0fc5978a330d36846879f7d8996409662cab43210c43e1a9678ed036a44a49f`, 266204169 bytes. Ejecutable original:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Faltan la validación GPU, el recorrido menú/carga/partida durante más tiempo
que la sesión fallida y comprobar que las texturas pendientes quedan acotadas.
El objetivo de un mínimo de 60 FPS en gameplay sigue sin verificar. Evidencia
privada: `build/texture-retirement-20261022/`, incluido `baseline-oom.log`.

## Menos entregas GPU; medición pendiente del límite interno (2026-10-22)

La captura posterior del usuario con las opciones nuevas muestra 22,5 NEW FPS,
mediana 39,8 ms, P95 55,3 ms y finalización GPU 6,4 ms. La cámara difiere de la
captura anterior: no prueba una regresión ni ganancia controlada. Una ventana
con 638 dibujos registra 3,64 submits, 7,57 grupos nuevos, 56,4 versiones de
buffers y 2,6 barreras por fotograma, con 8,22 ms de encoding y 3,32 ms de
espera en Present. Otra ventana registra 701.984 comprobaciones de resumption
SEH/s y 12.706 consultas de profundidad/s. Las opciones están actuando, pero
el objetivo de 60 FPS continúa sin alcanzar/verificar. El Wasm servido en esa
prueba era `483ed423995b0794caf7800c1ff98ee3b17144f77ba11000179317098b5239eb`; no se midió
el hash cargado en navegador ni equivalencia de píxeles.

El [bucle de referencia](https://github.com/gta-reversed/gta-reversed/blob/master/source/app/platform/win/WinMain.cpp)
condiciona el frame también a replay/beat info, además del ajuste del menú.
La lectura del PE original verifica las ramas en `00748d62`–`00748d96` y
`IsBeatInfoPresent` en `005071d0`, que consulta el dato en ECX+8+A0 tras
GetBeatInfo. Es una hipótesis pendiente de observación en la partida, no una
causa establecida de los FPS actuales. No se modifica el reloj, la simulación
ni el ejecutable para saltar esa condición.

Se añadió `PERF_WATCH` genérico, opcional y de solo lectura: hasta ocho campos
hexadecimal:ancho, con ancho 1/2/4; las peticiones inválidas desactivan la lista.
Se lee desde el titular del baton al emitir el informe, no desde el sampler.
Pasan 21 comprobaciones nuevas, las 68 de rutas y 403 de arranque. Build,
V8 completo y entrega idéntica por HTTP pasan. Wasm diagnóstico servido:
`044083ea544b8a014dfa2d706d8d42968c0a220a757610883b7b282c9ec98be0`, 266202717 bytes. Identidad original:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Falta leer el estado de menú/replay/frameLimit/beat info en gameplay con el
flag configurado. Evidencia privada: `build/frame-gate-watch-20261022/`.

## Objetivo solicitado de 60 FPS: versiones de buffers y caché persistente (2026-10-22)

El objetivo solicitado es un mínimo de 60 FPS durante gameplay; todavía no
está verificado. Se mantiene la evidencia anterior de 29 NEW FPS aportada por
el usuario, con escena distinta al baseline. El registro sin sampler muestra
ventanas de mundo con 487 dibujos/32,2 FPS y 668 dibujos/23,1 FPS; ventanas
ligeras de 50–52 dibujos no prueban 60 FPS en gameplay. Había unas 30–45
entregas WebGPU por fotograma en ventanas de mundo.

Se compiló `RECOMP_D3D9_RENAME_BUFFERS=1`, desactivado por defecto. Cuando
un buffer ya usado por el encoder se modifica, la ruta experimental conserva
una copia completa e inmutable en un offset distinto del ring, evitando cerrar
el pase por esa modificación. Se preservan las actualizaciones parciales y los
offsets de vértices/índices. Acepta buffers de hasta 256 KiB y hasta 4 MiB de
copias por encoder; fuera de ese presupuesto conserva la barrera anterior.
Después de queueSubmit restaura el respaldo persistente en orden de cola,
antes de reutilizarlo. Los contadores nuevos distinguen versiones temporales
y barreras restantes; no constituyen todavía evidencia de mejora de FPS.

Otra opción, `RECOMP_D3D9_PERSIST_GROUP_CACHE=1`, mantiene bindings entre
Present, con límite de 4.096 e invalidación antes de retirar vistas de texturas.
También se evita consultar el TLS de callbacks en las dos comprobaciones SEH
cuando la lista de registros está vacía. La ruta con registros activos se
conserva. `D3D9_STATS=0` ahora desactiva el informe; antes su mera presencia
seguía activándolo.

La prueba aislada SEH pasa 8 comprobaciones, incluidos registros/ESP intactos,
sin consultas de profundidad en despachos vacíos y adopción de un registro
creado después. Un intento amplio con la configuración resumable produjo
cuatro fallos de aserción en delay-load y después desbordamiento de stack;
no se declara aprobada la suite completa. Se añadió `--empty-dispatch` para
la comprobación específica, y memoria Emscripten suficiente para ese binario.

Build, compilación V8 completa, cero imports invoke, entrega idéntica por HTTP
y límites de fuente pasan. Wasm servido: `483ed423995b0794caf7800c1ff98ee3b17144f77ba11000179317098b5239eb`,
266199893 bytes. Original: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
No se ha medido el hash cargado en navegador ni probado gameplay del candidato.
Faltan comparar la misma escena, entregas/grupos/tiempos y comprobar imagen
con las opciones nuevas. Evidencia privada: `build/buffer-renaming-20261022/`.

## Caché experimental de rutas de lectura (2026-10-22)

La nueva captura con diagnóstico muestra CJ en BMX y 18,5 NEW FPS. En ocho
ventanas finales seleccionadas, `004dc2b0` acumula 772/4554 muestras
(17.0 %). Los bytes originales y su IAT `008580a0` verifican que
esa rutina llama a CreateFileA. Las muestras incluyen esperas y trabajo del
shim, no tiempo CPU exclusivo. `004eeead` incluye Sleep(1) de un trabajador;
no se trata su espera como coste exclusivo de simulación. La parada desconocida
anterior no se ha reproducido en el registro diagnóstico capturado.

Se preparó `RECOMP_READ_PATH_CACHE=1`, desactivado por defecto: recuerda hasta
1.024 resoluciones positivas de rutas de lectura normalizadas. Cada apertura
sigue creando un descriptor independiente y leyendo los datos bajo demanda.
No se almacenan contenidos, metadatos, escrituras ni respuestas negativas.
Las invalidaciones existentes por mutaciones, cambio de raíz o de overlays
vacían también esta caché. Los cambios externos de capas requieren la misma
invalidación explícita del resolver. `perf-files` mide ahora el adaptador
CreateFile completo, incluidas resolución y apertura del host; la medición
previa de ReadFile no incluía ese coste.

Pasan 68 comprobaciones específicas y las 403 de arranque existentes. Cubren
posiciones independientes, normalización, borrado/recreación, cambio de raíz,
escrituras e invalidación de overlays. Build, compilación completa V8 y entrega
idéntica JS/Wasm/paquete por HTTP pasan. Wasm servido:
`55838ff08ef441052dd60f2dcc1f677549273b9d567969128941639d983756ab`, 266198190 bytes.
Ejecutable original: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
La prueba posterior del usuario con el flag activo muestra CJ en BMX, 29 NEW FPS, mediana 37,4 ms, P95 54,1 ms y finalización GPU 4,7 ms; informa que se siente algo más fluido. La cámara/escena difiere del baseline de 18,5 FPS, por lo que no verifica una ganancia controlada. Los contadores confirman una ventana con 28 aperturas/s, 28 aciertos/s, cero fallos de caché y 0,66 ms/s en CreateFile. Otras ventanas con nombres nuevos siguen teniendo fallos y mayor coste. El perfilador y los logs continúan activos; falta comparar sin diagnóstico. No se midió el hash cargado dentro del navegador. El registro posterior se conserva como `candidate-browser.log`. Evidencia
privada: `build/read-path-cache-20261022/` conserva perfil, baseline, pruebas,
build, preparación y entrega; los artefactos previos mantienen su identidad.

## Lecturas bajo demanda y subidas WebGPU agrupadas (2026-10-22)

Se integraron seis archivos con cambios locales posteriores de DeepSeek:
tiempos de preparación de función fija, trabajo de encoding y espera en
Present, más diez callers del sampler. Esos cambios todavía no estaban
en el Wasm servido. Se conserva su trabajo y se desactivan relojes y
atómicos de diagnóstico cuando PERF_STATS no está activo.

El host monta los archivos del juego en OPFS y ReadFile solicita rangos:
no precarga los 5 GB de instalación en RAM. El paquete del runtime mide
35.073.821 bytes. Se midieron ahora llamadas/bytes/tiempo de lectura de
ReadFile e instrucciones del intérprete. Aperturas, seeks y lecturas de
codecs nativos quedan fuera de esa medición. Las llamadas interpretadas
anidadas consumen el presupuesto externo una sola vez; las funciones
traducidas no consumen instrucciones de ese contador.

El usuario dejó la escena quieta con PERF_STATS, D3D9_STATS, LOG=0 y la
caché de grupos experimental activa. Se servía
`d50efdfa774d17b788241cdbf754bd7f2c6272c01f59541505eba95e9dd9cced`,
266.181.302 bytes; el hash cargado en el navegador no se midió. Identidad
original: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

En las ventanas de gameplay seleccionadas, las lecturas muestran 0–24,45 ms
por segundo y el intérprete unos pocos miles de instrucciones por segundo.
Una ventana de 751 dibujos/fotograma registra 12,68 ms de encoding,
1,45 ms en Present y 2,73 ms de preparación de función fija. Los intervalos
pueden solaparse y no se suman. La captura del usuario muestra 21 NEW FPS,
mediana 50,2 ms y GPU 6,0 ms. Estas observaciones justifican medir primero
el trabajo del renderer; no descartan todo posible coste de streaming ni
constituyen una comparación de FPS con otra escena.

Se preparó `RECOMP_D3D9_BATCH_UPLOADS=1`, desactivado por defecto. Las
asignaciones de los dibujos mantienen sus offsets distintos, se copian a
staging y se sube cada prefijo usado antes de su entrega GPU original.
Se conservan las barreras de entrega. `ring_uploads/frame` cuenta las
llamadas de subida reales por separado de las asignaciones lógicas. La
sesión del usuario confirma la activación: una ventana de 909 dibujos
muestra 955,7 asignaciones y 140,4 subidas por fotograma (85,3 % menos
llamadas respecto a subir cada asignación), pero 14,74 ms de encoding.
Otra de 1.062 dibujos registra 1.102 asignaciones y 121,2 subidas, también
14,74 ms de encoding. El usuario informa que no hay defectos gráficos;
no se midió equivalencia de píxeles ni una ganancia controlada de FPS.
La opción continúa desactivada por defecto.

Se reabre una hipótesis de pacing con evidencia distinta a los hooks de
GetTickCount rechazados históricamente. Los bytes originales verifican
QueryPerformanceCounter en la IAT `008580c8` y una condición de dibujo
en `00748d81` que compara tiempo transcurrido contra `1000 / [00c1704c]`,
precedida por el flag `00ba6794`. Se pidió comprobar Frame Limiter en el
menú original. La captura posterior del usuario confirma «Limitar cuadros p. segundo: NO», efectos visuales bajos y antialiasing desactivado. El menú muestra 44 NEW FPS; eso no mide gameplay. El ajuste visible ya está desactivado, por lo que no justifica atribuir los pocos FPS a ese limitador. Falta medir de nuevo la misma escena con CJ; no se leyó directamente el flag en memoria.
La captura siguiente muestra CJ en BMX en otra calle: NEW 22,5 FPS, mediana 41,4 ms, P95 60,8 ms y finalización GPU 6,0 ms. No es una comparación controlada con la cámara anterior. Después, el registro termina en `recomp_unknown_call` y abort; LOG=0 omitió el destino desconocido. Se conserva el registro privado como `limiter-off-browser.log`. Falta repetir con LOG=1 y sampler para recuperar la dirección y atribuir el coste; las frecuencias elevadas de dispatch/SEH no prueban por sí solas su tiempo CPU. No se escaló el reloj ni se parcheó el ejecutable. El resultado histórico
de la hipótesis anterior se conserva por separado.

El Wasm del experimento servido es `1922c93bebee518a72e8d771a85bb56c19f954ff556f4752416f4f25ec8d4735`,
266,183,103 bytes. Build, V8 completo, cero imports invoke y hashes de
JS/Wasm/paquete entre salida/sitio/HTTP pasan. El intérprete pasa 446
comprobaciones y su contabilidad 7; la suite de función fija pasa 180 y las
pruebas Python relevantes 13. Cinco expectativas gráficas antiguas se
actualizaron para rechazar vertex blending y una operación inválida, en
vez de iluminación y multiply-add ya implementados. El código de dibujo
no se cambió para satisfacer esas expectativas.

El usuario resolvió un fallo de validación de la importación volviendo a
importar. El jugador conserva ahora el motivo original del error en el
mensaje; no se atribuye ese incidente al renderer ni a falta de FPS.
No se demuestra una ganancia estable de FPS, una misión completa ni 120 FPS.

Evidencia privada: `build/performance-followup-20261022/` contiene build,
pruebas y entrega de los contadores. `build/batch-uploads-20261022/` conserva
`baseline.log`, `baseline-delivery.json`, `build.log`, `browser-prepare.log`,
`delivery.json` y `result.json`. Los resultados históricos siguen separados
por identidad de ejecutable y artefacto.

## Partida con BMX confirmada por el usuario; perfil de rendimiento (2026-10-22)

El usuario confirma que la compilación corregida funciona y aporta una
captura de CJ en la BMX con el objetivo inicial visible. Se servía el Wasm
`0b9293973f72e4495289b71df6e3ea918a635f0892890d5827c3b76d77319b59`;
no se midió el hash cargado dentro del navegador. Ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Esto verifica la escena mostrada y el informe de funcionamiento del usuario,
no la misión completa, una conversión 1:1 ni estabilidad prolongada.

La captura indica NEW 18,0 FPS, DSP 98,5, mediana 53,5 ms, P95 82,2 ms,
GPU 7,1 ms y 82 % de repeticiones. DSP incluye imágenes repetidas: no son
98,5 fotogramas nuevos del juego. El indicador GPU es tiempo hasta la
finalización, no un timestamp aislado del hardware; la diferencia con el
intervalo de imagen nueva sugiere investigar CPU y sincronización.

Se pidió una pasada con PROFILE, PROFILE_INTERVAL_MS=2000, D3D9_STATS,
PERF_STATS y LOG=0. El registro muestra, en ventanas distintas:

| Dibujos por fotograma | FPS reportados | Grupos nuevos/fotograma | Entregas GPU/fotograma |
| --- | --- | --- | --- |
| 681 | 14,5 | 351,12 | 79,74 |
| 970 | 13,4 | 414,63 | 103,05 |
| 136 | 21,4 | 63,98 | 25,15 |

No son una comparación A/B: cambian la cámara/carga de escena y el
perfilador también añade coste. El sampler atribuye shims y esperas al
caller publicado; sus muestras no equivalen a tiempo CPU exclusivo.

El backend vaciaba los grupos en cada submit. Se compiló una opción
experimental, `RECOMP_D3D9_FRAME_GROUP_CACHE=1`, para conservarlos entre
entregas del mismo fotograma. Present y retirada de texturas invalidan la
caché; se invalida antes de liberar vistas cuyos handles podrían reutilizarse.
El límite de 4.096 entradas acota la retención incluso sin Present.
**Sigue desactivada por defecto** mientras se compara la imagen y el coste
con el comportamiento anterior. No se cambia la resolución ni la simulación.

El Wasm experimental servido es
`709d5924c68ee2222fdc668b1882c272379288f12a9fbc02381f60c65555af9e`,
266.178.214 bytes. Build, compilación completa V8, identidad JS/Wasm/paquete
entre salida/sitio/HTTP y cero imports invoke pasan. El registro confirma
que la opción se activó. Falta una comparación de partida con la misma
escena, cámara y opciones, y confirmación visual. No hay una ganancia de
FPS verificada ni una meta de 60 FPS alcanzada.

Para la comparación externa, [Grand-V](https://github.com/SebasKitten/Grand-V)
declara WebAssembly memory64, workers compartidos y WebGPU; esa descripción
no ofrece un benchmark equivalente a este equipo y escena. Esas tecnologías
no explican por sí solas una diferencia de FPS.

Evidencia privada: `build/performance-20261022/baseline.log`,
`baseline-delivery.json`, `build.log`, `browser-prepare.log`,
`delivery.json` y `result.json`. El progreso de carga/menu con pocos dibujos
no se usa como rendimiento de gameplay.

## TEST de byte e INC en memoria al continuar la carga (2026-10-22)

La siguiente captura y el registro local muestran un alto estricto en
`01560a22`: el intérprete no admitía `TEST byte ptr [EDX+EDI],0x80` en
`01560a3b` (`f6 04 3a 80`). El Wasm servido era
`4004a5657d3ad14f19911fe66736de1710ce2146fb611b63477b837fceaea250`;
el hash cargado dentro del navegador no se midió. Ejecutable verificado:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
La captura no demuestra que la versión reconciliada haya llegado a gameplay.

Se admite ahora F6 /0 con operandos de un byte, incluidos registros altos
y memoria SIB, sin escribir el operando. La prueba acotada de la rutina
original reveló después `INC dword ptr [ESP+0x10]` en `01560a7d`;
se añadieron FF /0 y /1 sobre el camino existente de INC/DEC. Las pruebas
con acarreo inicial 0 y 1 detectaron que ese camino perdía CF cuando no
había flags pendientes: ahora conserva el indicador de entrada.

Pasan **446 comprobaciones unitarias, 76 casos concretos contra Unicorn y
la decodificación acotada completa de `01560a22`**. No se ejecutó la suite
aleatoria de Unicorn en esta pasada. Las pruebas cubren flags, registros
altos, memoria vecina, acceso al último byte del arena y acarreo conservado.
El resto de operaciones de grupo 3 byte sigue rechazado. La decodificación
del original no ejecuta su lógica ni verifica sus llamadas.

El rebuild incremental terminó con código 0, conservando los datos de
traducción reconciliados. El nuevo Wasm es
`0b9293973f72e4495289b71df6e3ea918a635f0892890d5827c3b76d77319b59`,
266.177.413 bytes, 212.978 funciones definidas, máximo 2.929 locales y
cero imports `invoke_*`. Pasa la compilación completa con V8. Los hashes
de JS, Wasm y paquete coinciden entre salida, sitio y HTTP; se comprobaron
COOP, COEP, `no-store`, MIME Wasm y STRICT_UNKNOWN por defecto. Entrega
verificada en `2026-10-23T01:05:46Z` (22 de octubre local).

El registro anterior también contiene `GPU completion timed out` antes
del alto estricto. No se modificó el presentador para ocultarlo; su causa
y su repetición tras esta corrección siguen pendientes de comprobar.
Falta una nueva ejecución en navegador del Wasm corregido. No se afirma
que pase la carga ni que ejecute la misión.

Evidencia privada: `build/byte-test-20261022/browser-failure.log`,
`unit.log`, `decode.log`, `unicorn.log`, `build-verified.log`,
`browser-prepare.log`, `delivery.json` y `result.json`. El cambio queda en
el parche completo del runtime; los recursos y traducciones generadas
permanecen privados.

## Reconciliación de entradas locales tras GitHub (2026-10-22)

El nuevo informe del usuario se detiene en `01564df9`, por `CMP word ptr
[ESI+4],DI` en `01564dfe` (`66 39 7e 04`), con STRICT_UNKNOWN activo.
GitHub y el checkout principal coinciden en `d948a51`: no había otro commit
pendiente de descargar. Sin embargo, la variante privada conservaba 11
entradas explícitas y 13 contratos de sitios de llamada. La documentación
publicada ya registraba ocho entradas observadas adicionales para esta misma
imagen, ausentes de esa configuración. Las compilaciones anteriores se
hicieron con el runtime nuevo y esos datos locales antiguos; las extensiones
del intérprete no reconstruían las entradas de código faltantes.

Se ejecutó `tools/audit_allbytes_call_thunks.py` sobre el ejecutable verificado:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
La auditoría de bytes prueba 7.645 formas completas de llamada/RET4 (3.853
fijas y 3.792 con checksum), 7.640 ausentes de los contratos locales.
Tras unirlos con los anteriores quedan 7.653 sitios auditados y 8.134
entradas explícitas: continuaciones/destinos verificados, las ocho entradas
históricas documentadas y los tres destinos de los altos locales recientes.
Los nuevos puntos también se comprobaron contra las secciones ejecutables
y las regiones de datos declaradas de la imagen original.

El aplicador ahora admite que el último elemento y `]` compartan línea,
ignora corchetes en comentarios, verifica la identidad del ejecutable antes
de modificar entradas y conserva los primeros respaldos. Pasan seis pruebas
de esta reconciliación. `config/singleplayer-entry-points.json` publica solo
once direcciones escritas a mano con identidad y referencias de evidencia;
los listados y el informe completo de la auditoría siguen siendo privados.
README.md documenta cómo reconstruir los contratos y aplicar esas entradas.

La primera regeneración se interrumpió al escribir los archivos de salida:
el disco estaba lleno. Se conservó un registro antiguo de 2.628.592.044 bytes
en gzip (47.959.724 bytes), verificando por SHA-256 la descompresión completa,
y se retiraron 3.882.705.776 bytes de duplicados Wasm tras comprobar sus
copias idénticas conservadas. No se retiraron recursos originales ni partidas.
El empaquetador web copiaba también los probes y los Wasm linked/browser/
stripped del directorio de salida. Ahora copia solo el módulo referenciado
por el jugador, su paquete y sus scripts auxiliares; pasan tres pruebas de
esa selección. El parche completo recoge este ajuste del empaquetado.

La regeneración estricta terminó: el informe principal registra 59.809
funciones examinadas, 59.127 aceptadas y 168.081 entradas; cero fallos,
formas sin modelar, huecos de tablas o tablas sin decodificar. Los cuatro
informes auxiliares también registran cero en esos controles. Se comprobó
la presencia de las once direcciones documentadas en la tabla de despacho
real, incluido `01564df9`, cuyo bloque contiene la comparación de 16 bits.
Estos recuentos describen la traducción, no la ejecución del juego.

La interrupción de la sesión detuvo la compilación en el paso 177; se
reanudó sin regenerar ni repetir los objetos terminados y concluyó con
código 0. El módulo preparado conserva sus 212.978 funciones definidas,
máximo 2.929 locales y ninguna función por encima del límite comprobado.
Pasa la compilación completa de V8 y conserva cero imports `invoke_*`.

Wasm nuevo servido: `4004a5657d3ad14f19911fe66736de1710ce2146fb611b63477b837fceaea250`,
266.177.461 bytes. Los hashes de JS, Wasm y paquete coinciden entre la
salida de compilación, el sitio y la respuesta HTTP. El servidor local
entrega COOP `same-origin`, COEP `require-corp`, `no-store` y MIME Wasm
correcto; el HTML mantiene STRICT_UNKNOWN por defecto. La entrega se
verificó en `2026-10-23T00:56:16Z` (22 de octubre local). No se midió el
hash del módulo de la captura anterior: solo se conoce que entonces se
servía `d73a8a0586e64f3f63ea1b89188493799820a558fea83bdf06f8f9be82f032d8`.

Para conservar margen de disco se archivaron también salidas antiguas de
compilación y diagnóstico, verificando la descompresión de cada una por
SHA-256 antes de retirar sus copias sin comprimir. Las rutas y sus
identidades están en los manifiestos privados; los originales del juego
y las partidas no se modificaron.

Queda pendiente una nueva prueba en navegador de este artefacto reconciliado.
No se afirma que haya superado la carga, que ejecute la misión, ni que sea
idéntico bit a bit al artefacto histórico que abrió el juego. La evidencia
histórica sigue separada por identidad. Evidencia privada:
`build/sync-inputs-20261022/result.json`, `allbytes.json`,
`observed-entries.json`, `browser-failure.log`, `pipeline.log`,
`pipeline-retry.log`, `pipeline-resume.log`, `browser-prepare.log`,
`delivery.json`, `log-compression.json`, `site-linked-compression.json`,
`archived-diagnostics/manifest.json` y `duplicate-cleanup.json`.

## Lectura absoluta de byte tras la primera corrección de carga (2026-10-22)

El siguiente registro recibido del navegador se detiene en `0156c146`, por
`MOV AL,[009654bf]` en `0156c15d` (opcode A0). Esta vez STRICT_UNKNOWN sí
está activo y detiene el proceso antes de omitir la rutina. El Wasm servido
al recibirlo era `73bc1112a5c61917b9e6d26e4749ee33f4fe8bbb1b70b2bdaaff828f7d8ca76c`;
la identidad cargada dentro del navegador no se midió. Ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
La traza se conserva en `build/byte-shift-20261022/browser-moffs-failure.log`.

Se admiten ahora las lecturas y escrituras absolutas de AL (A0/A2) usando
los accesos de un byte existentes. Las pruebas verifican los otros bits de
EAX, los bytes vecinos, los flags sin cambios y el último byte del arena.
Pasan **420 comprobaciones del intérprete y 65 casos contra Unicorn**.
El análisis acotado sobre la imagen original acepta `0156c146` completo;
no es una prueba de ejecución del juego.

El enlace web y la compilación completa de V8 pasan. Nuevo Wasm servido:
`d73a8a0586e64f3f63ea1b89188493799820a558fea83bdf06f8f9be82f032d8`.
JS/Wasm/data responden HTTP 200 y sus hashes coinciden con los construidos.
El parche completo recoge también este ajuste, sin aplicar parches parciales
ni cambiar el pin del runtime. Resultado y hashes privados en
`build/byte-shift-20261022/moffs-result.json`; pruebas en `unit-moffs.log`,
`unicorn-moffs.log` y `decode-moffs.log` en ese directorio. Sigue pendiente
confirmar la continuación de la carga con este último artefacto en navegador.

## Bloqueo de carga en operaciones de byte del intérprete (2026-10-22)

La nueva captura y el registro del usuario llegan al arte de carga, pero el
proceso invitado termina con `0xc0000005`; el presentador conserva la imagen.
El primer rechazo es la rutina `0156f890`: el decodificador no admite
`SHR DL,5` en `0156f98b` (`c0 ea 05`). La URL observada no activa el modo
estricto y el runtime devuelve cero. A continuación intenta continuar en
`0d68f7e5`, devuelve cero otra vez y llama a `00000206`. La salida del juego
precede a los contadores de audio sin datos: esos contadores no demuestran
que siga avanzando la carga. Ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm servido al recibir el informe:
`f58b1d6197f2afe4a45bf92403a7fbb92dc14fe43b84c7fef58732ceb7b154ed`;
no se midió el hash del Wasm cargado dentro del navegador.

El intérprete ahora decodifica SHL/SHR/SAR de byte con inmediato, uno implícito
y CL. Reutiliza los helpers de flags de 8 bits y las lecturas/escrituras de un
solo byte, incluidos AH..BH y el límite del arena. El siguiente análisis de
la rutina original detectó `AND DL,1` en `0156f990`; también se admiten las
operaciones inmediatas de byte del grupo 1 que ya tenían semántica de byte
implementada. ADC/SBB y los prefijos no soportados siguen rechazados.
No se editó el ejecutable ni el código generado y no fue necesaria otra
regeneración: solo cambiaron el intérprete y su enlace con el juego.

Verificación: **415 comprobaciones, cero fallos**, **62 casos contra Unicorn**
y **4 pruebas del servidor** pasan. Cubren preservación de bits superiores,
registros byte altos, vecinos de memoria, flags, contadores de desplazamiento
cero/enmascarados y rechazo de ADC/SBB. El decodificador acotado del probe
sobre el ejecutable verificado acepta ahora `0156f890` completo; ese ensayo
no ejecuta la rutina original ni verifica gameplay.

La compilación web y la validación completa de V8 terminan con salida 0.
Wasm actualizado:
`73bc1112a5c61917b9e6d26e4749ee33f4fe8bbb1b70b2bdaaff828f7d8ca76c`.
Los tres archivos JS/Wasm/data servidos responden HTTP 200 y coinciden por
SHA-256 con los construidos; siguen sin existir importaciones `invoke_*`.
La preparación local del jugador activa STRICT_UNKNOWN incluso en la URL
sin parámetros. Las opciones RECOMP_ explícitas conservan su prioridad.
Esto evita omitir otra rutina pendiente y perder su estado antes de informar
el primer error. El servidor estaba detenido durante la comprobación final;
se inició de nuevo y las cabeceras de aislamiento y ausencia de caché se
comprobaron por HTTP.

El parche completo del runtime está actualizado y conserva sus cambios
anteriores. Evidencia privada: `build/byte-shift-20261022/result.json`,
`browser-failure.log`, `unit-final.log`, `unicorn-final.log`,
`decode-final.log`, `server-tests.log`, `web-build.log` y
`browser-prepare.log`. La continuación de carga en el navegador con este
Wasm está pendiente de confirmación del usuario; no se atribuye a estas
pruebas CPU una partida, prólogo o misión completados.

## Recompilación web local de la actualización de GitHub (2026-10-22)

Se regeneró y recompiló la variante `gtasa-singleplayer` con los cambios de
`d948a513896ca9403711eea59c69c4dde7f25262` y el parche completo del runtime
verificado en la sincronización anterior. Ejecutable original:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
La traducción estricta de la imagen principal y las cuatro DLL terminó sin
fallos, instrucciones no modeladas, huecos de tabla ni tablas sin decodificar.
Se usó Release con optimización normal del código generado; el modo diagnóstico
permanece desactivado. Tras una interrupción controlada para aumentar el
paralelismo de cuatro a seis procesos, se reutilizaron los objetos terminados
y la compilación finalizó con salida 0.

El módulo completo pasó la compilación de V8. Tiene
196,562 funciones definidas y un máximo de
2,929 locales por función; no requirió
coalescencia adicional de locales. El artefacto servido tiene
232 433 735 bytes y SHA-256:
`f58b1d6197f2afe4a45bf92403a7fbb92dc14fe43b84c7fef58732ceb7b154ed`.
La inspección de sus importaciones confirma cero `invoke_*` entre
332 importaciones; el Wasm local anterior tenía
25 de esos puentes.
Estos datos identifican esta compilación y no establecen su rendimiento.

Se preparó de nuevo el HTML y se inició el servidor de loopback en
`http://127.0.0.1:8771/gtasa-singleplayer/?RECOMP_STRICT_UNKNOWN=1`.
El HTML responde HTTP 200 con las cabeceras COOP/COEP y sin caché; JavaScript,
Wasm y paquete de recursos responden HTTP 200 y coinciden por SHA-256 con los
archivos recién construidos. El Wasm se entrega como `application/wasm`.
Los recursos originales y las partidas no se modificaron.

El usuario informa que esta versión supera la carga y permite jugar en web.
Se conserva la evidencia histórica de gameplay con sus identidades originales.
No se repitió una prueba interactiva en esta sesión: el control nativo informa
que su canal no está disponible y el inventario de navegadores está vacío.
Tampoco se midieron FPS de este artefacto. Sigue documentada la ausencia en el
remoto del commit fijado para el runtime; se compiló el árbol del parche
completo comprobado sobre la base local disponible, sin cambiar el pin.

Evidencia privada: `build/rebuild-20261022/result.json`, `pipeline.log`,
`compile.log`, `browser-prepare.log` y registro del servidor en ese directorio.
Los artefactos ejecutables y los recursos permanecen excluidos de Git.

## Sincronización local con GitHub (2026-10-22)

Se descargaron e integraron por avance directo los siete commits desde
`e903029` hasta `d948a513896ca9403711eea59c69c4dde7f25262`.
El runtime local coincidía exactamente con el parche completo anterior y se
respaldó antes de retirarlo y aplicar una sola vez el parche completo nuevo.
La comparación de árboles Git del resultado da
`da8fbe192f6868fd49541f4abd231737e22a9d43` tanto para la aplicación aislada
del parche como para los archivos locales actualizados. No se recompiló ni
se ejecutó el juego durante esta sincronización; las mediciones históricas
conservan su alcance y sus identidades originales.

Bloqueo de reproducción pendiente: el nuevo gitlink y
`patches/recomp-kit-base.txt` señalan
`ad47228c5b0ab2d1453251999bbd86795e178fac`, que el remoto original rechaza
como revisión inexistente. Se conserva disponible localmente la base
`eb32cc42623e0e9e868b9d27423a57d5a5cba56b`; el parche entrante se aplica
íntegro sobre ella y el árbol resultante está verificado. No se modificó
el pin publicado ni se reconstruyó artificialmente el commit ausente.
Evidencia privada: `build/github-sync-20261022/result.json` y respaldo del
parche anterior en ese mismo directorio.

## Rendimiento: no hay limitador que retirar; el techo lo pone la simulación (2026-10-22)

Esta sección **corrige la siguiente**, que daba por hecho que el limitador de frames del
juego giraba sobre `GetTickCount`. Esa hipótesis queda refutada. La sección anterior se
conserva como evidencia de lo que se midió entonces y de lo que se creía.

Medido en el navegador con el wasm `sha256 40a0ac86…` (266.527.795 bytes), servido en
`http://127.0.0.1:8771/gtasa-singleplayer/`. El build **sigue sin ser bit-reproducible**,
así que el hash identifica un artefacto y no un estado del código.

### El juego no importa `GetTickCount`

La sustitución de `native_frame_clock()` (`vendor/recomp-kit/runtime/kernel32.cpp`) está
colgada de `k_GetTickCount`: compara la dirección de retorno de cada llamada con los cinco
ganchos `RECOMP_HOOK_FRAME_CLOCK_*`. Tres hechos:

- El código traducido no contiene ninguna llamada a `GetTickCount`; la cadena no aparece
  en `build/recomp/gen`.
- El reloj del juego es `QueryPerformanceCounter` a través de la ranura IAT `0x008580c8`
  (`FUN_00561a80`: lee el contador y resta la base de `0x00b7cb38`).
- Un diagnóstico que histogramaba la dirección de retorno de cada `GetTickCount`
  (`RECOMP_TICK_CALLERS`) no registró ni una sola llamada en dos ejecuciones de gameplay.

Para este ejecutable esa ruta es **inalcanzable**, no solo «sin configurar». Se retiró el
diagnóstico y se corrigieron los comentarios que afirmaban lo contrario.

### Las direcciones que nombraba ese comentario eran falsas

`kernel32.cpp` afirmaba que `0049cfc0` y `0049cfe0` eran las dos esperas del bucle de
dibujo. No lo son:

| Dirección | Qué es en realidad |
|---|---|
| `0049cfe0` | `FUN_0049cfe0`, 72 instrucciones: test de caja envolvente sobre la lista de entidades de `0x00a9ad70`, con dos argumentos, llamado desde `chunk_021.c:3524` y `:3557` |
| `0049cfc0` | no es entrada de función: cae dentro de `FUN_0049cec0` |

Cablear esas direcciones no habría dado un error: habría cambiado el ritmo del juego en
silencio.

### No hay techo artificial: el coste es la simulación

| Escena (misma sesión) | *draws*/frame | fps |
|---|---|---|
| callejón, 4 informes | 430 / 489 / 690 / 888 | 24,3 / 24,2 / 24,4 / 24,3 |
| callejón | 584 | 20,1 |
| otras ejecuciones | 743 / 757 / 788 | 24,3 / 23,4 / 23,1 |
| escenas más cargadas | 859 / 917 / 1020 | 21,4 / 19,4 / 19,3 |

Dos hechos descartan un limitador:

- fps se queda en 24,2–24,4 entre 430 y 888 *draws*. Si mandara el coste por *draw*, 430
  tendría que ir muy por encima de 888.
- El muestreador del batón (`RECOMP_PROFILE=1&RECOMP_PROFILE_INTERVAL_MS=2000`) da
  **1–4 muestras inactivas de 130–131 por ventana (≈1–3 %)** y reparte el resto entre
  muchas funciones (`FUN_007fa320`, `FUN_0070fa70`, `FUN_00561a80`,
  `sub_007f99b0.blk_007f99b0`), sin ninguna dominante.

Un limitador que duerme aparecería como inactividad; uno que gira, como una sola función
caliente. No aparece ninguna de las dos: son ~41 ms de trabajo de simulación
independiente del número de *draws*, con el dibujado sumándose encima cuando la escena
pesa. **No hay nada que «desbloquear»: llegar a 60 fps exige que el trabajo del invitado
sea ~2,5× más rápido.** No se ha conseguido y no se reclama.

### Trabajo por frame del camino WebGPU (nuevo, medido)

El informe `d3d9 webgpu:` publica ahora, junto a los *draws*, el trabajo de host que el
invitado no ve (`host/gpu/webgpu/d3d9_webgpu.cpp`):

| Medida | 917 *draws* | 1020 *draws* |
|---|---|---|
| `writes/frame` | 956,8 | 1061,3 |
| `new groups/frame` | 423,7 | 434,0 |
| `new pipelines/frame` | 0,00 | 0,01 |
| `submits/frame` | 83,7 | 85,9 |

Es decir: ~1 escritura de uniformes por *draw* (`wgpuQueueWriteBuffer`), ~0,46 bind groups
creados por *draw* y ~84 `wgpuQueueSubmit` por frame, con las *pipelines* ya cacheadas.
Los recuentos están medidos; **su coste en ms no**, así que son un candidato a reducir, no
una mejora demostrada.

## Rendimiento: el invitado no duerme, y el limitador de frames del juego gira sobre el reloj (2026-10-22)

Medido en el navegador con el wasm `sha256 6276422a…` (266.527.447 bytes), servido en
`http://127.0.0.1:8771/gtasa-singleplayer/`, en el mismo callejón de Los Santos. El
build **sigue sin ser bit-reproducible**, así que el hash identifica un artefacto y no
un estado del código.

| Medida | Ronda anterior (`087ca85c…`) | Esta ronda (`6276422a…`) |
|---|---|---|
| `STAT d3d9` media, ~750 *draws* | 22,87 fps (6 informes) | **23,4–24,4 fps** (5–8 informes por ejecución) |
| `STAT d3d9` media, 859 *draws* | — | 21,4 fps (1 informe) |
| `invoke_*` en las importaciones | 26 | **0** (de 331 importaciones totales) |

La mejora en fps a igual número de *draws* es modesta y en parte cae dentro del ruido de
±1 fps; lo que sí es un cambio estructural es la desaparición de los 26 `invoke_*`.

**El recuento de *draws* no es constante dentro de una misma sesión**: derivó entre 743 y
1000 en el mismo callejón. Como el coste por frame crece con los *draws*, dos ejecuciones
solo son comparables al mismo recuento. La cifra de 21,4 fps corresponde a 859 *draws*, no
a un empeoramiento.

### Lo que se corrigió en el build

`-fwasm-exceptions` + `-sSUPPORT_LONGJMP=wasm` **globalmente** para los objetivos web
(`vendor/recomp-kit/CMakeLists.txt`, dentro de `if(EMSCRIPTEN)`). Con el `setjmp`/`longjmp`
en JavaScript, cualquier llamada indirecta de una unidad que pueda lanzar se compila como
una importación `invoke_*`: un viaje wasm → JS → wasm que copia los argumentos y
reconstruye el marco. El código traducido despacha **todas** las llamadas por puntero
(`recomp_call` → `recomp_base_ptrs[i](c)`), así que ese envoltorio estaba en decenas de
miles de llamadas por frame. Con `-fwasm-exceptions` el mismo despacho es un
`call_indirect` normal.

Los cinco bloques `-fno-exceptions` que la ronda anterior había puesto en `runtime/`,
`dx/`, `host/`, `host/gpu/` y `mods/` se retiraron: eran un rodeo que dejaba 26
`invoke_*` en su sitio, porque el SJLJ de Emscripten los emite igual. El recuento de
funciones pasó de 213.144 a 213.145; V8 compila el módulo completo sin errores.

También se sacó del camino caliente la instrumentación que corría incondicionalmente en
cada *dispatch* (`runtime/imports.cpp`): el histograma por página y el contador por
*trampolín* ahora están tras `import_stats_on()`, que solo es cierto con
`RECOMP_WATCHDOG_TLS`/`RECOMP_WATCHDOG_CS`, y `log_level()` se lee una vez en un
`static const int verbose` en lugar de en cada llamada. Con ~50.000 *dispatches* por
frame eso eran tres accesos a memoria compartida y una llamada por importación.

### La medición que faltaba: el invitado no duerme

El perfilador del propio runtime (`RECOMP_PROFILE=1&RECOMP_PROFILE_INTERVAL_MS=2000`)
muestrea a 1 kHz **el hilo que tiene el batón** y cuenta como `idle` las muestras en las
que no está dentro de una función traducida. En ~45 ventanas de 2 s durante gameplay:

| `idle` | ventanas |
|---|---|
| 0,0–1,5 % | 24 |
| 1,6–3,9 % | 15 |
| 4,6–6,9 % | 6 |

**El invitado está ejecutando código traducido el 93–100 % del tiempo.** Esto descarta
la hipótesis con la que arrancó la ronda —que el limitador de frames del juego (30 fps
por defecto) estuviera durmiendo al invitado y que por tanto hubiera 2× de margen—. No
hay tal margen: el CPU ya está ocupado.

### Dónde va ese tiempo: el limitador gira sobre el reloj

El mismo muestreador atribuye el tiempo a funciones del invitado, y dos se llevan casi
todo en el callejón:

| Función | Muestras | Qué es |
|---|---|---|
| `FUN_00561a80` | 20–30 % | 8 instrucciones: lee un puntero importado y resta la base de tiempo. Es la forma de `CTimer::GetTimeInMilliseconds`. |
| `FUN_00748710.blk_00748da0` | 25–45 % | Bucle con `Sleep(0x64)` y lecturas del reloj. |

Los contadores del runtime lo confirman: a ~24 fps el invitado lee el reloj
**0,94–1,32 millones de veces por segundo**, es decir **~40.000–55.000 lecturas por
frame**, y despacha 1,1–1,5 millones de importaciones por segundo (~47.000–64.000 por
frame, coherente con ~50 importaciones por *draw*).

El propio código del kit ya lo tenía escrito: *«this game's frame limiter spins on
GetTickCount»* (`runtime/kernel32.cpp:1715`) y *«the frame limiter's GetTickCount spin is
left alone»* (`:2054`). GTA San Andreas **no duerme** para limitar los frames: gira
llamando a `GetTickCount` hasta que vence su plazo.

### El siguiente paso concreto, y por qué no se aplicó aquí

El kit ya sabe sustituir ese giro: `native_frame_clock()` (`runtime/kernel32.cpp:1665`)
retira los dos plazos del bucle de dibujo y deja que el kit marque el ritmo con
`mods_display_fps()`. Pero esa sustitución **solo se compila si el variante define**
`RECOMP_HOOK_FRAME_CLOCK_BEGIN`, `_WAIT`, `_WAIT_CLAMP`, `_CLAMP_DEADLINE` y
`_WAIT_DEADLINE`, y `variants/singleplayer/game.toml` **no tiene sección `[hooks]`**. En
este build esa ruta es código muerto y el limitador del juego gira sin tocar.

Cablearla exige auditar las cinco direcciones. El comentario de `kernel32.cpp:1660`
identifica `0049cfc0` (inicio del plazo; selecciona el segundo plazo cuando el estado de
juego 2 tiene *flags* de frame rate) y `0049cfe0` (el límite por defecto de 60, o 24/20/14
Hz), y avisa de que ninguno de los dos plazos mueve la simulación. Faltan por confirmar
las dos esperas y las dos direcciones de plazo. **No se cablearon a ojo**: una dirección
equivocada no da un error, cambia el ritmo del juego en silencio.

### Lo que se intentó y no se quedó

- **`-sGROWABLE_ARRAYBUFFERS=2`.** El enlazador lo recomienda por `-pthread` +
  `ALLOW_MEMORY_GROWTH`, y atacaría justo la lentitud del código no-wasm. Rompe el
  backend WebGPU: `Uncaught TypeError: Failed to execute 'setBindGroup' on
  GPURenderPassEncoder: The provided ArrayBuffer value must not be resizable`. Revertido.
- **Cachear el reloj de milisegundos del invitado** a partir de las lecturas monotónicas
  que el planificador ya hace (`host_publish_millis`, ~1 M de lecturas/s servidas sin
  llamar al *host*). Medido **neutro** (23,96 fps frente a 23,84) y revertido: en wasm
  `os_monotonic_ns()` no es el viaje a JS que sugería el contador `clock`, así que el
  ahorro no compensaba tocar el camino de tiempo.
- **Escalar el reloj del invitado 2×** para separar «sin CPU» de «esperando a su
  limitador». El juego se cuelga en el menú (su lógica de fundido depende de tiempo
  real), así que la prueba no sirve. Revertida junto con el caché.
- **`-fno-exceptions` solo** y **`SUPPORT_LONGJMP=wasm` solo** siguen descartados por lo
  medido la ronda pasada (quedan los 26 `invoke_*` / el enlace falla en `liblua.a`).

### Corrección a la ronda anterior

La sección siguiente afirma que 60 fps están fuera de alcance «con aritmética», porque
solo el código traducido ya consume ~19 ms de los 16,7 ms de presupuesto. Esa cifra sigue
siendo coherente, pero la conclusión **no está establecida**: el desglose salía de un
perfil que atribuía el tiempo por muestras de los *workers*, que se leían como 97 % en
`__pthread_cond_timedwait`. El muestreador del batón, que mide al hilo que realmente
ejecuta, muestra 0–7 % de reposo. Y la parte dominante del «código traducido» es un bucle
de espera sobre el reloj (`CTimer::GetTimeInMilliseconds`), no trabajo de simulación: es
justo la parte que el kit ya sabe sustituir. **60 fps no están demostrados ni descartados;
falta cablear la sustitución auditada del limitador y volver a medir.**

### Qué se verificó en el navegador

- El juego arranca desde el menú original y llega a gameplay: `draws > 100` confirmado
  antes de medir (711–1000 *draws*), tras descartar tres intentos en los que una pulsación
  consumida durante el fundido dejaba la página en el menú a ~300 fps sobre 10 *draws*.
- `invoke_*` = 0 en el wasm servido; V8 compila el módulo completo.
- El audio corre (mensajes `dsound` con `first play on channel …`), sin *underruns*.
- El invitado lee el reloj y despacha importaciones a los ritmos citados, sin abortos ni
  avisos de validación de WebGPU.

### Qué sigue sin verificarse

Misiones, vehículos, audio **escuchado**, guardado y carga, estabilidad más allá de
~35 minutos y cobertura de la ciudad entera. Las cifras de arriba son **una escena
estática** y el número de *draws* derivó entre 743 y 1000 dentro de la misma sesión, así
que las comparaciones entre ejecuciones solo son válidas al mismo recuento. `CAP 60` en el
overlay es el límite configurado del kit, no una medida.

## Rendimiento: de 17,8 a 22,9 FPS medidos, y la aritmética que descarta los 60 FPS (2026-10-22)

Medido en el navegador con el wasm `sha256 087ca85c…` (266.416.245 bytes), servido
en `http://127.0.0.1:8771/gtasa-singleplayer/`, en el mismo callejón de Los Santos
de la ronda anterior: CJ, la valla, la BMX y el HUD de objetivo, con ~750–760
*draws* por frame. El build **sigue sin ser bit-reproducible**, así que el hash
identifica un artefacto y no un estado del código.

| Medida | Ronda anterior (`67e599f6…`) | Esta ronda (`087ca85c…`) |
|---|---|---|
| `STAT d3d9` media | 17,1–17,8 fps | **22,87 fps** (6 informes) |
| `FRAME` | 39,4–56,3 ms | **43,7 ms** |
| `draws/frame` | 751–787 | 750–760 |
| `GPU` | 3,5–4,2 ms | 3,5–4,2 ms |

La GPU sigue sin ser el cuello: 3,5–4,2 ms de un frame de 43,7 ms. Todo lo ganado
en esta ronda está en el hilo del invitado.

### La progresión, medida paso a paso

Cada fila es un build distinto medido con el mismo protocolo (asentar 340 s,
leer los últimos informes `STAT`). El ruido entre ejecuciones del mismo fuente es
de ±1 fps, así que las filas separadas por menos que eso no prueban nada por sí
solas; se conservan porque el conjunto sí es monótono.

| fps | Cambio |
|---|---|
| 17,8–18,1 | Punto de partida de la ronda (`-fno-exceptions` en `runtime`, `dx`, `gpu_backend`, `host`) |
| **20,1** | Diagnóstico `ARGC_UNKNOWN` con marca `argc_warned` por *trampolín* + reloj de `sched_wait_locked` solo con `perf_stats::on()` |
| 20,6 | `-fno-exceptions` también en `mods` y `host_common` (con `-fexceptions` por fichero en `interp.cpp`, `overlay.cpp`, `indexed_frame.cpp`) |
| 19,5 | Muestreo 1-de-16 del reloj del *checkpoint* de importaciones — dentro del ruido, se queda por ser gratis |
| **21,1** | Descripción del *trampolín* perezosa: `imports_describe` deja de construir la cadena en cada *dispatch* |
| **22,4** | Arena estable de descripciones (`desc_arena()`), así el *dispatch* guarda un puntero en vez de copiar |
| **22,9** | `SCHED_SLICE_SECONDS` de 0,001 a 0,004 |

Total: **17,8 → 22,9 fps (+29 %)** en la misma escena estática.

### La causa real del `printf_core` que llevaba dos rondas en el perfil

El perfil tenía un 1,74 % en `printf_core` sin dueño aparente. Estaba en
`dx/d3d9.cpp:579`: el shim instala `g_return_observer` de forma **incondicional**,
y ese observador llama a `describe()` en **cada dispatch** de importación. No era
un `printf` de depuración olvidado: era la descripción de la función construyendo
una `std::string` por llamada para un observador que casi siempre la ignora.

La corrección no es quitar el observador —lo usan los modos de diagnóstico—, sino
que `Tramp` guarde un `desc_c` que apunte a una arena que nunca se mueve
(`desc_arena()`, un `std::deque<std::string>`; `deque` no invalida las referencias
de los elementos ya insertados). El *dispatch* pasa entonces un puntero y no
copia ni formatea nada. `printf_core` desaparece del perfil.

### Lo que se intentó y no se quedó

- **`SUPPORT_LONGJMP=wasm`.** Era la vía para eliminar los ~25 `invoke_*` que
  quedan en las importaciones. El enlace falla con
  `undefined symbol: emscripten_longjmp` en `liblua.a` y en los *chunks* de
  `recomp_gen`: habría que recompilar **todos** los objetos en ese modo, no solo
  el runtime, y además el `setjmp`/`longjmp` de Emscripten es load-bearing para el
  SEH del invitado. Descartado por invasivo para los ~2 fps estimados.
- **`-fno-exceptions` solo.** No basta: Emscripten emite los `invoke_*` en los
  sitios de llamada indirecta por su `setjmp`/`longjmp` en JS, con independencia
  de cómo se compilen las excepciones de C++. Quedan 25–26 en la sección de
  importaciones, y su traza es `recomp_run` ← `invoke_vii` ← `run_entry`, es decir
  el SJLJ de Emscripten y no una excepción de C++.
- **Poda de *flags* en el traductor.** Eliminaría ~1,54 M accesos a
  `c->eflags_`, pero 341 de 19.207 funciones tienen *flags* vivas a la entrada y
  188 de 69.866 sitios de llamada las tienen vivas después: el riesgo de
  incorrección no compensa ~1,5 fps.

### Por qué 60 FPS no están al alcance, con aritmética

A 22,9 fps el frame dura 43,7 ms y el hilo del invitado los reparte así:

| Parte | % del frame | ms por frame |
|---|---|---|
| Código traducido del invitado | 43,6 % | **~19,0** |
| Runtime + shims | 22,8 % | ~10,0 |
| Frontera JS | 22,2 % | ~9,7 |
| Espera del *scheduler* | 11,4 % | ~5,0 |

El presupuesto de 60 fps es **16,7 ms por frame**, menos que los ~19 ms que ya
consume **solo** el código traducido del invitado. Aun con un runtime de coste
cero el techo sería ~50 fps, y eso sin contar GPU, presentación ni el
`scheduler`. La vía realista es llegar a ~25–30 fps recortando la frontera JS y
el runtime, no a 60.

### Qué se verificó en el navegador

- `move_verify.py final1 40`: con `w` pulsada 40 s, **68 de 68** capturas
  distintas entre sí, `problems: []`, a 19,4 fps de media con 757–774 *draws*.
  El mundo responde a la entrada y no reproduce una cinemática.
- `shot_final.png`: CJ, la valla, las palmeras, el semáforo, los edificios, el
  radar y el HUD, sin avisos de validación de WebGPU y sin abortos.
- El audio corre: 2.147 mensajes `dsound` con búferes reproduciéndose
  (`first play on channel …`), sin *underruns*.
- `presenter: FAULT: target pool stalled for 250ms` aparece **una sola vez**, en
  el arranque; muestreado a 0 s y 40 s el contador sigue en 1, así que no recurre.

### Qué sigue sin verificarse

Misiones, vehículos, audio **escuchado** (los búferes se reproducen; nadie ha
confirmado que suenen), guardado y carga, estabilidad más allá de ~35 minutos y
cobertura de la ciudad entera. Las cifras de arriba son **una escena estática**:
al caminar por la misma calle la media baja a 19,4 fps, y con la ciudad a la vista
y ~850–970 *draws* por frame baja a 15–17 fps. `CAP 60` en el overlay es el
límite configurado del kit, no una medida.

## Rendimiento: de 0,4–0,6 FPS a 17–24,5 FPS en gameplay (2026-10-22)

Medido en el navegador con el wasm `sha256 67e599f6…` (266.404.198 bytes), servido
en `http://127.0.0.1:8771/gtasa-singleplayer/`, en el mismo callejón de Los Santos
con CJ y la BMX. El build **no es bit-reproducible**: el mismo fuente produjo
`c2bd157f…` (266.404.081 bytes) en la ronda anterior y `67e599f6…` ahora, así que
un hash identifica un artefacto, no un estado del código.

| Medida | Antes (`target7d`, `32630437…`) | Ahora (`67e599f6…`) |
|---|---|---|
| `NEW FPS` del overlay | 0,4–0,6 | **17,0–24,5** |
| `FRAME` | 1828,5 ms | **39,4–56,3 ms** |
| `P95` | 2281,5 ms | 51,7–73,4 ms |
| `GPU` | 3,9 ms | 3,5–4,2 ms |
| `STAT d3d9` | 11,8–14,5 fps | media **17,1–17,8 fps** |
| `seh_frames` | 200–260 M/s | **0/s** |
| `chain_visits` | 8–28 M/s | **0/s** |
| `live_frames_max` | 845 | **1** |

La GPU nunca fue el cuello: 3,5–4,2 ms de un frame de 39–51 ms. El coste estaba
en el hilo del invitado, y el perfil de CPU lo repartía entre `__pthread_cond_timedwait`,
`recomp_seh_resume_frame`, `ChainWalk::visit` y el código traducido por debajo del 2 %.

### Causa raíz 1: un epílogo SEH que nunca retiraba su frame

Los contadores del propio runtime, no una hipótesis, la señalaron. La tabla por
dirección nombró un solo sitio: `0x0048130e` (`fn_00481300`) instalaba frames y no
liberaba ninguno (`enters_total=850`, `live=845`, y la lista solo crecía). Como
cada dispatch recorre la lista entera dos veces —una en el escaneo de reanudación
y otra en la pasada de frontera—, un único retiro perdido se convierte en un coste
que crece con la lista y no baja nunca.

Eran dos defectos independientes:

1. `tools/recomp/translate.py` calculaba `fn.seh_restores` en `prepare()` y **nunca
   lo consultaba**: la regla que emite `recomp_seh_frame_leave` para
   `MOV FS:[0], reg` estaba condicionada a `fn.seh_sites`, que está vacío para el
   bloque de epílogo `body_004835cc` porque su prólogo vive en otro bloque
   recuperado. Por eso `0x004835ef` (`MOV dword ptr FS:[0x0],ECX`) no emitía nada.
2. El retiro en `runtime/seh.cpp` usaba `registration < ESP`, y en esta forma de
   epílogo MSVC la ESP **sigue por debajo** de la registration: el epílogo carga la
   cabeza de la cadena desde `[ESP+0x1fc]` en ECX y solo saca parte del frame. Aun
   emitiendo el `leave`, no habría retirado nada.

Correcciones: la regla del traductor consulta `seh_restores`, con
`seh_unproven_establishment` para no retirar en cuerpos cuyo establecimiento no se
pudo probar; las emisiones de `recomp_seh_frame_leave` pasan de 6 a 563. En el
runtime la liveness se decide por **pertenencia a la cadena SEH** —la misma prueba
que ya aplicaba el escaneo de reanudación—, con una poda acotada
(`prune_unlinked_frames`, una pasada cada 1024 reanudaciones y solo por encima de
32 frames) como red de seguridad, y `recomp_callback_depth()` se saca del bucle de
escaneo.

### Causa raíz 2: el *staging* de D3D9 se asignaba y liberaba en cada *draw*

Con el SEH arreglado el perfil cambió de dueño: `vector<unsigned char>::__insert_with_size`
14,4 % dentro de `host_d9_buffer_upload` y `heap_alloc` 9,5 % bajo `stage_lock`.
`stage_lock` pedía un bloque del tamaño completo del recurso en el primer *lock* y
`stage_unlock` lo copiaba y lo liberaba en el último, así que un juego que bloquea
un búfer dinámico una vez por *draw* pagaba asignación, dos copias y liberación
por *draw*. Además `gpu_after_unlock` marcaba **todo** el búfer como sucio, de modo
que cada *draw* resubía el búfer entero aunque el juego hubiera bloqueado un
subrango.

Correcciones en `dx/d3d9.cpp` y `dx/com.h`: el bloque de *staging* sobrevive al
*lock* (`stage_bytes`) solo para búferes de vértices e índices, que son los que se
reescriben cada *draw*; una textura lo libera al desbloquear para no retener una
segunda imagen durante toda la sesión. El *Unlock* sube únicamente el rango
bloqueado, ensanchado hacia fuera hasta un múltiplo de 4 porque el offset de
escritura del backend debe estar alineado (ensanchar es seguro; estrechar no).
`__insert_with_size` baja de 4514 ms a 354 ms por ventana de 30 s.

### El rango de subida es correcto también con geometría en movimiento

Una captura estática no distingue un rango de subida correcto de uno que pierde
bytes: los triángulos obsoletos solo aparecen cuando la geometría se reescribe en
cada frame. Por eso la última comprobación mantiene `w` pulsada 40 s y captura la
vista cada 0,5 s: los **72 fotogramas de 72** son distintos entre sí, así que el
mundo se mueve con la entrada y no reproduce una cinemática, y `mv1_after_move.png`
muestra a CJ fuera del callejón con el cartel de la calle, palmeras, edificios, un
coche aparcado, el radar y el HUD, sin triángulos perdidos ni costuras. El registro
de la página no contiene ningún aviso de WebGPU ni abortos.

Con la ciudad a la vista el coste sube y la cifra baja: **12,0–12,8 fps con
1154–1249 *draws* por frame** frente a 17,8 fps con ~760 en el callejón. Es la
medida honesta del recorrido, y sigue siendo una sola calle, no la ciudad entera.

### Dos intentos medidos y descartados

Ninguno de los dos se quedó. Ambos están aquí para que no se repitan, y el segundo
además advierte de cómo una comparación mal hecha casi deja pasar una conclusión
falsa:

- Implementar `os_monotonic_ns` con `emscripten_get_now()` en vez de
  `clock_gettime`. La medida directa es del perfil, no del fps: `_emscripten_get_now`
  pasó del 9,6 % al **28,7 %** del hilo del invitado. Revertido.
- Leer el reloj del *checkpoint* una vez cada 16 llamadas. Se descartó primero con
  una comparación que resultó **inválida**: los dos lados se habían medido en
  fases distintas de la carga (frames 8101–9601 frente a 11101–12601), así que la
  caída atribuida al cambio era la escena, no el código. Re-medido con el protocolo
  estable (asentar 340 s y leer los últimos informes `STAT`) da **19,1 fps frente a
  18,6–19,6** del build sin el cambio: está dentro del ruido. Se descarta por no
  aportar nada medible a cambio de añadir latencia al *scheduler*.

La lección vale para el resto del documento: las cifras de fps solo son comparables
entre ejecuciones que llegan al mismo punto de la escena, y por eso el protocolo
asienta 340 s y descarta los informes de la fase de carga.

### Qué sigue sin verificarse

Misiones, vehículos, audio escuchado, guardado y carga, estabilidad más allá de
~35 minutos y cobertura de la ciudad entera. La cifra de 17,8 fps es **una escena
estática** (el callejón); en movimiento por la misma calle baja a 12,0–12,8 fps. El
límite `CAP 60` del overlay es el límite de frames de la configuración del kit, no
una medida.

Evidencia local de esta ronda: `ship_overlay.png` (overlay recortado, `NEW 18.5
FPS`, `FRAME 56.3 ms`, `GPU 3.8 ms`), `final_overlay.png` (`NEW 17.0 FPS`, `FRAME
51.0 ms`), `refocus_ov.png` (`NEW 24.5 FPS`, `FRAME 39.4 ms`), `ship_scene.png`,
`final_scene.png` y `cur2_scene.png` (la escena completa), `mv1_move_*.png` y
`mv1_after_move.png` (la secuencia con `w` pulsada), y las líneas `perf:` de
`RECOMP_PERF_STATS=1` con `live_frames_max=1`, `seh_frames=0/s`, `frames live=0
enters_total=1550`. Sin avisos de WebGPU ni abortos en el registro de la página.

### Dónde está ahora el coste

Tras los dos arreglos el hilo del invitado ya no tiene un dueño único, y por eso
esta ronda se detiene: no queda ninguna corrección grande que pueda validar sin
arriesgar el *scheduler*. El perfil reparte el tiempo entre
`__pthread_cond_timedwait` 13,6 %, los *trampolines* `invoke_*` de Emscripten con
`get`/`getWasmTableEntry`/`wasm-to-js` ~9 %, lecturas de reloj ~9 %, código
traducido del juego ~11 %, *staging* de D3D9 3,9 %, `imports_dispatch` 2,1 % y
`printf_core` 1,2 %. Desactivar la captura de excepciones C++ quitaría los
`invoke_*` (wasm→JS→wasm), pero `interp.cpp` depende de `throw`/`catch` para las
faltas de memoria del invitado y la ganancia estimada es de ~2 fps: no se hizo.

## Gameplay controlable verificado en el navegador: CJ camina por Los Santos (2026-10-21)

La ejecución `target7d`, con el wasm `sha256 32630437…` (266.386.779 bytes),
**no registra ni un solo rechazo de función fija** en todo el recorrido
(`mirror-target7d.log`): la síntesis cubre ya todas las combinaciones de estado
que GTA SA usa para dibujar el mundo y los personajes. `evid_gameplay_clean_1122.png`
muestra el callejón con CJ, la valla, el objetivo y 350 $ sin ninguna línea
`fixed-function draw refused`, y `evid_move_noc_refusals.png` a CJ moviéndose
con la cámara siguiéndolo.

La ejecución `target7b` fue la primera en llegar a **gameplay sin pausar con el
personaje del jugador** y en responder al teclado. `evid_gameplay_cj_935.png`
muestra a CJ de espaldas en el callejón de Los Santos con la cámara tras él, la
valla, los árboles, los edificios y el objetivo «Follow the 'CJ' icon on the
radar to get back to the hood.» con 350 $. Manteniendo `w` pulsada sobre esa
misma página durante 240 s (`evid_move_street_002.png`, `probe7b_hold_002.png`)
CJ **camina hasta la calle**: se ven casas, césped, la acera, la valla y tres
peatones más. `evid_move_forward_009.png` muestra el siguiente tramo, con
palmeras y la barandilla metálica en primer plano. Cada captura de la secuencia
es distinta de la anterior, así que el mundo se mueve con la entrada y no es una
cinemática.

Estado del arte en este punto:

- Iluminación de función fija sintetizada (difusa, ambiente global, material).
- Declaraciones de vértices descritas directamente, sin exigir *stream* cero,
  que era lo que descartaba 131.072 *draws* por ejecución.
- Transformaciones de coordenadas de textura y *texgen* de espacio de cámara.
- Caso mixto: *vertex shader* del juego con etapas de píxel fijas, que es lo que
  usan los modelos con *skinning*.
- Operaciones de etapa de textura completadas (ADDSIGNED, ADDSIGNED2X,
  ADDSMOOTH, los cuatro *blend*, PREMODULATE, MODULATEALPHA_ADDCOLOR,
  MODULATECOLOR_ADDALPHA, MULTIPLYADD, LERP y **DOTPRODUCT3**). Con
  `DOTPRODUCT3` el callejón se dibuja entero (`target7c_play_651.png`): muros de
  ladrillo, calzada, palmeras y árboles, cielo de atardecer.

Lo que **no** está verificado: misiones, vehículos, audio audible, guardado,
estabilidad más allá de ~35 minutos y rendimiento utilizable. La medición es de
**0,3–0,5 FPS** con tiempos de frame de 2,0–3,8 s, así que el juego es
técnicamente interactivo pero no jugable en tiempo real. Esa cifra pertenece a la
ejecución `target7d` (`32630437…`); el rendimiento medido después en `c2bd157f…` es
de 17–24,5 FPS, según la sección de rendimiento al principio de este documento.
Tampoco se ha medido
cuánto de la ciudad se dibuja sin errores: `target7d` no encontró ningún rechazo
nuevo en 2316 s, pero eso cubre el callejón y la calle contigua, no la ciudad
entera.

Evidencia: `browser-target7b.log`, `mirror-target7b.log`, `move-probe7b.log`,
`evid_gameplay_cj_935.png`, `evid_gameplay_cj_1697.png` (frame en reposo),
`evid_move_before.png`, `evid_move_street_002.png`, `evid_move_forward_009.png`.
Wasm `sha256 c21bac75…` para la ejecución 7b; el build con las operaciones de
textura es `build-web-texops.log`.

## Los personajes con *skinning* se dibujan: CJ aparece en pantalla (2026-10-21)

Tras la iluminación, el rechazo que quedaba era otro: la declaración de vértices
del juego pone **la posición en el *stream* 1**, y `d9_declaration_fvf` la
rechazaba porque exigía *stream* cero. Ese mismo rechazo se disparaba 131.072
veces en una ejecución, así que era todo el mundo con textura, no un caso raro.

Correcciones aplicadas en esta ronda:

- `dx/d3d9_ffp.cpp`: `d9_declaration_format` describe la declaración
  directamente en vez de reconstruir un código FVF. Sólo le interesa qué
  atributos existen —posición, normal opcional, los dos colores y cuántos juegos
  de UV—, porque el renderizador ya enlaza atributos a entradas del shader por
  *usage*. Así el orden de los elementos, sus desplazamientos y el número de
  *stream* dejan de importar. El *vertex blending* se rechaza por su nombre
  (`BLENDWEIGHT`/`BLENDINDICES`) en lugar de como elemento desconocido.
- `dx/d3d9_ffp.cpp`: **transformaciones de coordenadas de textura**
  (`D3DTSS_TEXTURETRANSFORMFLAGS`) con matriz por etapa en `c34..c65`, y
  **texgen** de posición y normal en espacio de cámara
  (`D3DTSS_TCI_CAMERASPACEPOSITION`/`CAMERASPACENORMAL`), componiendo la matriz
  de vista con la de la etapa. El renderizador ya dividía por `w` para
  `D3DTTFF_PROJECTED`, así que el divisor se escribe en esa vía.
- `dx/d3d9_ffp.cpp`: el bucle de declaración miraba sólo hasta
  `at + 8 < size`, de modo que nunca veía el elemento terminador del final y
  rechazaba con «has no terminator». Corregido a `at + 8 <= size`.

Evidencia (wasm `sha256 86de7cc6…`): `evid_cj_skinned_143.png` muestra a **CJ y
tres personajes más con *skinning*** en la cinemática de introducción, con ropa,
piel y vaqueros texturizados; `evid_crowd_skinned_748.png` y
`target7a_play_1353.png` muestran la escena de la comisaría con una multitud de
policías y peatones y el logotipo de la emisora. Es la primera vez que el
personaje del jugador se dibuja en el navegador.

Sigue **sin verificarse gameplay controlable**: las capturas son de la
cinemática, ningún frame muestra a CJ respondiendo a una tecla de movimiento, y
el rendimiento es de 0,5 FPS con tiempos de frame de 1,6–2,5 s.

## La iluminación de función fija deja de rechazarse y el mundo se dibuja iluminado (2026-10-21)

El rechazo de los *draws* de función fija era lo que dejaba el mundo vacío. Con
el wasm de `0x006338e0` (`sha256 4a052d68…`) la ejecución estricta llegaba a
gameplay sin pausar, con HUD y el objetivo «Follow the 'CJ' icon on the radar to
get back to the hood.» y 350 $, pero **sin geometría de mundo**: el espejo del
log mostraba exactamente tres rechazos distintos de `d3d9_ffp_prepare`, y el
primero de ellos, «fixed-function lighting is not implemented», descartaba
todos los *draws* del terreno y de los edificios.

Correcciones aplicadas en esta ronda:

- `dx/d3d9_ffp.cpp`: **iluminación difusa de función fija** sintetizada en el
  *vertex shader* (`vertex_program`). Suma por vértice
  `emissive + ambient * D3DRS_AMBIENT + Σ light.diffuse * material.diffuse *
  max(0, N·L)`, con la normal rotada al espacio de mundo por `c8..c11` y
  normalizada. Direccionales usan `-direction`; puntuales y *spot* calculan el
  vector luz→vértice con una `MAD` y `NRM` sobre la posición de mundo, sin
  atenuación ni cono. El alfa nunca se ilumina: se escribe aparte, del material
  o del vértice con `D3DRS_COLORVERTEX`.
- `dx/d3d9_ffp.cpp`: la síntesis se partió en `vertex_program` y
  `pixel_stages`, y `d9_ffp_prepare` acepta `vertex_supplied`/`pixel_supplied`
  para sintetizar sólo la mitad que falta. Es el caso que GTA SA usa con sus
  modelos con *skinning*: *vertex shader* propio y etapas de píxel fijas.
- `dx/d3d9_pipeline.h`, `dx/d3d9.cpp`: `D9_FFP_VCONST` (34 constantes) en vez
  de las 7 anteriores, para que el intercambio y la restauración de constantes
  cubran material y luces; `D3DLIGHT9` se lee con sus desplazamientos reales
  (posición +52, dirección +64, rango +76, caída +80, atenuación +84) y
  `GetMaterial` escribe `Power` como un único `float` en +64, no como un vector
  de cuatro que desbordaría la estructura del invitado.
- Los rechazos restantes ahora llevan el estado culpable y un contador
  (`refused (N so far)`) que se emite en potencias de dos, para distinguir un
  rechazo cosmético de miles de *draws* perdidos.

Evidencia de la ejecución `target6y` (wasm `sha256 6aca1de8…`, 266.370.477
bytes) con el mirror adjunto: `mirror-target6y.log` ya no contiene
«fixed-function lighting is not implemented», y los frames
`evid_cutscene_lit_317.png`, `evid_world_lit_680.png` y `evid_hud_lit_1246.png`
muestran cielo con degradado, horizonte, terreno, edificios, un vehículo
aparcado y el HUD de la primera misión con 350 $ a 0,5–1 FPS. La
`D3DRS_AMBIENT` global y el material se ven como sombreado, no como color plano.

Sigue **sin verificarse gameplay controlable**: ningún frame muestra a CJ
caminando ni una respuesta a una tecla de movimiento, el *vertex blending* de
función fija sigue rechazándose (por eso los personajes con *skinning* no se
dibujan), quedan dos rechazos por explorar (declaración con *stream* distinto de
cero y etapas de textura con transformación/*texgen*) y el rendimiento es de
0,5–1 FPS en carga y cinemática.

Evidencia de construcción: `build-web-ffplit.log` y `build-web-mixed.log`
(EXIT=0), `prepare-wasm-ffplit.log` y `prepare-wasm-diag.log` (212.853
funciones, V8 compila el módulo completo).

No se afirma jugabilidad, conversión completa, equivalencia 1:1 ni porcentaje.
`browser_gameplay_verified` sigue en `false`.

## El mundo 3D se renderiza; el juego se pausaba solo al perder el foco (2026-10-21)

Con el wasm de `0x005245bd` (`sha256 9b20ee85…`, 266.361.215 bytes) el juego
dibuja **geometría 3D real**. En `target6h_load_106.png`,
`target6h_load_137.png` y `target6h_load_223.png` se ve una calle de Los Santos
con edificios, postes, calzada y cerros, a 2,5–9,5 FPS. En
`target6k_resume2.png` el fondo del menú de pausa muestra la misma escena viva a
22 FPS, y en `target6k_no.png` el mapa completo de Los Santos se dibuja con su
leyenda de controles. El HUD de la primera misión también sale: salud y
chaleco, icono de arma, dinero y los avisos «Press RETURN to jump on the bike»
y «Use UP, DOWN, LEFT and RIGHT to move Carl.» con 210 $.

Durante mucho tiempo cada frame de mundo aparecía con el menú de pausa abierto.
La causa no era de renderizado: **GTA SA se pausa solo cuando su ventana pierde
la activación**. Al abrir otra ventana de Chrome por delante de la del juego, el
invitado abría el menú de pausa y se quedaba ahí. La solución es
`Emulation.setFocusEmulationEnabled` por CDP, que mantiene el documento con
foco para el invitado con independencia del gestor de ventanas; con eso la
cinemática de introducción corre sin pausarse (`target6u_030.png`).

También se identificó que el clic de ratón queda encolado mientras el invitado
transmite y se reproduce después, ya en gameplay, donde el juego lo lee como
Start: por eso la navegación del menú usa sólo Enter, dos pulsaciones
verificadas contra un recorte de la banda de opciones.

La ejecución estricta sigue **sin llegar al gameplay controlable**. Con el wasm
`9b20ee85…` el invitado abortó a los ~565 s en `0x00684ce6` (epílogo SEH
`mov fs:[0],ecx`, que el intérprete no decodificaba por el prefijo de segmento
FS) y, ya con ese arreglo, a los ~730 s en `0x006338e0`, donde el intérprete se
detenía en `0f 95 c0` (`SETNZ AL`).

Correcciones aplicadas en esta ronda:

- `0x00684ce6` y `0x006338e0` añadidos a `entry_points` en
  `variants/singleplayer/game.toml`.
- `runtime/interp.cpp`: prefijo de segmento FS (`fs:[disp]` suma `fs_base`, que
  es como el invitado alcanza su TEB y el array TLS) y `SETcc r/m8`
  (`0x0f 0x90..0x9f`).
- `dx/d3d9_pipeline.h` y `dx/d3d9.cpp`: estado de material (`D3DMATERIAL9`) y de
  hasta ocho luces (`D3DLIGHT9`) con `SetMaterial`/`GetMaterial`/`SetLight`/
  `GetLight`/`LightEnable`, que eran `D9_STUB`. La síntesis de shaders todavía
  rechaza la iluminación de función fija y el *vertex blending*.

Evidencia: `build-web-5245bd.log` (59.166/59.839 funciones, 168.221 puntos de
entrada), `prepare-wasm-5245bd.log` (212.850 funciones, V8 compila el módulo
completo), `browser-target6h.log`, `browser-target6v.log`,
`browser-target6w.log`, `mirror-target6w.log` y las capturas citadas.

No se afirma jugabilidad, conversión completa, equivalencia 1:1 ni porcentaje.
`browser_gameplay_verified` sigue en `false`: hay mundo 3D, HUD y cinemática,
pero ningún frame muestra gameplay sin pausar con el personaje y todavía no se
observó movimiento controlable.

## Primera misión llega al HUD; el mundo 3D sigue sin renderizar (2026-10-21)

Una ejecución estricta de 16 minutos (`RECOMP_STRICT_UNKNOWN=1`) sobre el build
con `0x006c1a04` llegó por primera vez al estado de juego de la primera misión.
En `target6c_load_262.png` se ven las barras de salud y chaleco, el icono de
arma y el contador de dinero; en `target6c_load_554.png` aparece el aviso
«Press RETURN to jump on the bike.» con 350 $. El HUD y el texto los dibuja el
juego; **no** hay geometría 3D, moto ni personaje: el fondo es el color de
cielo/limpieza. No se observó movimiento controlable ni progreso de misión.

La ejecución **no terminó limpia**. A los ~565 s el invitado llamó a
`0x005245bd` (bytes `8a 47 36 24 07 3c 02`, o sea `mov al,[edi+0x36];
and al,7; cmp al,2; jne ...`), que es código real pero no era punto de entrada.
El intérprete tampoco decodificaba `0x24` (`AND AL, imm8`). La captura de 950 s
está congelada en ese instante (AGE ~385 s), así que el HUD es real pero el
frame final no está vivo.

Correcciones aplicadas para el siguiente build:

- `0x005245bd` añadido a `entry_points` en `variants/singleplayer/game.toml`.
- Formas AL,imm8 (`0x04/0x0c/0x24/0x2c/0x34/0x3c`) añadidas a
  `runtime/interp.cpp`.
- FFP D3D9: se aceptan niebla de tabla y por vértice y suma especular; siguen
  rechazadas la iluminación de función fija y el *vertex blending*.
- WebGPU: el pipeline de `LINE_STRIP` indexado fijaba
  `stripIndexFormat=Undefined`, lo que invalidaba cada `DrawIndexed` del HUD;
  ahora la clave y el descriptor usan el formato de índice del draw.

Evidencia: `translate-6c1a04.log` (168.197 puntos de entrada, 0 fallos),
`build-web-6c1a04.log`, `prepare-wasm-6c1a04.log` (212.830 funciones,
266.371.165 bytes, sha256 `354bd942…`), `browser-target6c.log`,
`target6c_load_262.png`, `target6c_load_554.png` y `target6c_load_950.png`.
La regeneración y el nuevo build estaban en curso al escribir esto.

No se afirma jugabilidad, conversión completa, equivalencia 1:1 ni porcentaje.
`browser_gameplay_verified` sigue en `false`: hay HUD, pero no mundo ni
personaje renderizados ni juego controlable.

## Alto en la pantalla de carga en blanco (abierto) (2026-10-16)

Tras los títulos, la carga inmediatamente anterior al menú queda en blanco.
El usuario lo verifica en navegador: pantalla blanca con barra vacía, AGE
~9-10 s, 0 FPS y ~1169 fotogramas descartados. El bootlog del servidor
(16:12, 122 líneas) termina tras la inicialización del SoundManager y el
inicio de la música de menú en bucle (buffers 384/385, 28000 Hz, 554176
bytes); el sink de audio está sano (`0 starved`) y el huésped se bloquea sin
`strict-stop` ni mensaje de error. Sospechosos sin confirmar: la import
`wsprintfA` sin implementar registra "unknown stdcall argument count: not
adjusting ESP, the guest stack will drift" (deriva potencial de pila si es
realmente stdcall) y las líneas de `LoadLibrary` de `wmvcore.dll` y
`quicktime.qts` sin shim poco antes del alto.

Para nombrar la última llamada culpable hace falta la traza completa
(`?RECOMP_LOG=2`). El transporte del bootlog se optimizó en
`tools/serve_variant.py`: el escritor anterior (XHR síncrono cada 1500
líneas, ~66 bloqueos/segundo con nivel 2) se sustituyó por un escritor
asíncrono encadenado (lotes de 4096 líneas con cabecera `#B` auditable,
reinyección al frente de la cola si un lote falla, y vaciado síncrono en
`pagehide`); el espejado a la consola de DevTools ya no ocurre en la página.
Verificado el servidor en `http://127.0.0.1:8771` (HTTP 200, `drain`
asíncrono en la página servida). La ejecución del usuario con `RECOMP_LOG=2`
sobre este transporte sigue pendiente; el estado de la pantalla blanca, del
menú y de la carga no está verificado.

## Sombreado plano verificado en navegador y suite nativa clasificada (2026-10-16)

El usuario verifica en navegador con el build del 16/10 15:50: la secuencia
de copyright y la de CJ se dibujan con su sonido; las pantallas de título
dibujan la barra de progreso y esta se rellena sobre el arte (el sombreado
plano de función fija llega al rasterizador); después aparece el alto
documentado en la sección anterior. No se verifica mundo, prólogo ni
primera misión.

Suite nativa completa (`tools/test.py --native --jobs 4`, juego stub por
defecto): 24/26 suites pasan. `d3d9_ffp_tests` pasa con 168 comprobaciones y
0 fallos, incluidos los casos nuevos de sombreado plano: la puerta FFP
acepta FLAT (rs[9]==1) en el mismo par de shaders, la traducción WebGPU
declara ambos colores `@interpolate(flat)`, PHONG (3) sigue rechazado y el
rasterizador CPU pinta el triángulo en el color del vértice provocador.
`runtime_tests`, `interp_tests`, `gdi_tests`, `host_boundary_check` y el
resto de la suite pasan.

Corrección de la propia prueba: `flat_shading_cases()` ponía los render
states en un pipeline local en vez del pipeline vivo del dispositivo, así
que la puerta FFP veía `D3DRS_LIGHTING` (rs[137]) activado y rechazaba los
dos dibujos; ahora opera sobre `d9_pipeline(dev->id)` como el resto de los
casos.

Corrección de prueba obsoleta en `dx_tests`: `test_directdraw_create_ex_fallback`
codificaba el contrato antiguo de `DirectDrawCreateEx` (rechazo
`DDERR_UNSUPPORTED`) y fallaba contra la fábrica v7 real pendiente de
confirmar. Actualizado al contrato nuevo: la fábrica entrega el objeto v7
(DirectDrawCreate devuelve `DD_OK`), se conservan los rechazos (IID v4,
agregación y argumentos nulos) y el balance de referencias cierra a cero;
`dx_tests` pasa completa ("all dx tests passed").

Clasificación de los 2 fallos restantes contra la línea base
HEAD `eb32cc4` del kit (suite nativa reconstruida en un worktree limpio del
repositorio del kit): `host_tests` falla exactamente igual (2
comprobaciones de `host_resource("controls")` con rutas de layout de
repositorio/paquete) y `gpu_vulkan_tests` falla exactamente igual
(`gpu_contract_tests.cpp:193`, el ancho del drawable tras
`resize`+`acquire` no se actualiza en el backend Vulkan). Son fallas
existentes de plataforma/backend, no del trabajo pendiente: no se tocan su
subtree ni su contrato en este hito.

Nota sobre Windows: `tools/format.py` requiere `clang-format` accesible;
instalado (`clang-format==23.1.1` en el venv) y pasando con
`.venv\Scripts` en el `PATH` (378 fuentes de primera mano formateadas).

## Punto de entrada recuperado en el cargador de ajustes (2026-10-16)


Con el shim del filter graph, el arranque avanzó más allá de los estados de
cine hasta un nuevo alto estricto del usuario: `call to unknown target
005c1723` y el descarte del tramo
`["005c16f0", "data", "005c1820"]` en `blocks_withdrawn`. Todavía no hay
verificación de pantalla, menú, carga ni partida tras ese avance. Evidencia
verificada sobre el ejecutable: el literal de vtable en `0085a974` nombra
`005c16f0`
como puntero de función (ningún literal apunta a `005c1723`), el prólogo es
`81 EC 88 01 00 00 / 55 56`, el cuerpo termina en `ret 4` en `005c18ed`
(siguiente prólogo en `005c18f0`) y la reentrada del bucle en `005c1710`
(`jl 005c1710` en `005c18dd`) queda dentro del cuerpo. La causa del retiro es
la misma de `005347d0`: el descodificador arrancó la rutina en `005c1723` y la
reentrada interna del bucle la dejó fuera. Añadido `0x005c16f0` a
`entry_points` en `variants/singleplayer/game.toml`.

Regeneración con `tools/build.py --game-dir variants/singleplayer --target web
--diagnostic-all --regenerate`: salida 0, y `005c16f0` aparece una única vez en
`translate-report.json`, como `recovered_blocks`; no queda en
`blocks_withdrawn`. Wasm servido:
`d2f27b1bdb629f3e9a60f7a92b735d4fc136334f73a808a0eb0485017f90b430`
JS `4087d7786db7e7236794a54cfa738d600fcf2973033c87ef270e56aabe238837`,
paquete `d328113ff9feb4b2aa809fd5c4ab35c99a4122107c48a2db6ebc225540002fc9`.
`tools/check_publication.py` pasa. Falta la verificación del usuario en
navegador; no se afirma menú, carga ni partida jugable.

## Shim del filter graph de DirectShow para la secuencia de cine (2026-10-16)

La traza estricta de 48 462 256 líneas del usuario mostró el arranque nuevo
detenido en los estados 2/4 de WinMain (`00748b17`): la cola esperaba
supuestamente el fin de la película, pero el aviso `WM_USER+13` (`0x40d`) nunca
llegaba, porque `CoCreateInstance(CLSID_FilterGraph {e436ebb3…})` respondía
`0x80040154` y el juego había cargado sin player. Causa única verificada sobre
la imagen original y el IDL QuartzTypeLib real: el reproductor de cine usa el
ABI de DirectShow con offsets exactos — `IGraphBuilder::RenderFile` = +0x34,
`IMediaControl::Run` = +0x1c y `::Stop` = +0x24, `IMediaEventEx::GetEvent` =
+0x20, `::FreeEventParams` = +0x30 y `::SetNotifyWindow` = +0x34, y
`IVideoWindow::put_WindowStyle` = +0x24 y `::put_Owner` = +0x74 (interfaces
duales con IDispatch en 0x0c..0x18). Sólo {56a868b4} (IVideoWindow) faltaba
registrado además del CLSID.

Implementación en `dx/dshow.cpp`, sin tocar código generado: `CoCreateInstance`
del FilterGraph crea un graph autónomo (sin stream multimedia; `graph_this`
usa su propio registro de estado), `RenderFile` guarda la ruta pedida
(`movies\Logo.mpg`, `movies\GTAtitles.mpg/GTAtitlesGER.mpg` están en el
paquete) y completa siempre; `Run` encola `EC_COMPLETE` y lo anuncia por
`SetNotifyWindow` con un mensaje real vía la bomba del host, que reactiva el
manejador huésped `0x745fb0` y permite avanzar 2→3→4→5. La tabla nueva
`IVideoWindow` es un no-op documentado en el orden dual del SDK. Los graphs de
stream (música) no cambian: su `SetNotifyWindow` sigue sin producir mensajes y
su `Run` sigue decodificando. El destructor borra el estado propio del graph
autónomo; la referencia es nula.

Alcance declarado: NO se decodifica ni muestra vídeo ni audio de las películas;
la secuencia de apertura completa de inmediato (equivale a saltarla). No se
afirma reproducción de vídeo. El dibujado fijo con sombreado plano (pantalla
de carga posterior) sigue rechazado.

Compilación web: salida 0, servida en el sitio del variant con wasm
`5f32873e41c55a55d369b8c1720187276c35c6bca12446bdadb824bab7221cfa` (250 221 505
bytes), JS `8670bab2adc3390cca314460c61ce490172e9bbe152bfb65acbd6ee751e9ba6f` y
paquete `51564b0c3665e04e5553f8e015e3f2b8c321d388a023d7f5217a15a726dbfbd0`.
El bootlog anterior (`bootlog.txt`, 2 929 324 465 bytes, y `bootlog.seq`) se
rotó para la traza siguiente. Pendiente la verificación en navegador del
usuario: el arranque debe pasar los estados de cine; ninguna prueba local
acredita menú, carga o partida jugable.

## Desbordamiento de pila durante la carga original (2026-10-15)

Las capturas posteriores del usuario muestran el arte original de carga y
una superficie blanca, con NEW a 0 FPS mientras el presentador sigue activo.
El diagnóstico posterior registra `Maximum call stack size exceeded`.
Esto verifica el bloqueo de carga; todavía no verifica mundo, prólogo ni
primera misión. Ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm servido antes del diagnóstico:
`4dea1d033cc086d069d2c529b1cee0f22411373a2b11b045cedf62ba9037d529`;
Wasm servido con el muestreo:
`3ddac5763b7619025282f8b4092119864248f8acd7026b991231eba40b8c9e70`.
No se midió la identidad del Wasm cargado por el navegador.

El muestreo opcional ahora puede informar durante la ejecución mediante
`RECOMP_PROFILE=1&RECOMP_PROFILE_INTERVAL_MS=5000`. Solo lee el índice atómico
publicado por el planificador. Las cadenas profundas se capturan en el hilo
propietario. Una muestra repetida después de abortar puede ser un índice
obsoleto: no demuestra que siga ejecutándose ni un bloqueo en
LeaveCriticalSection, donde apareció una de las trazas de desbordamiento.

Las cadenas profundas sí identificaron un ciclo real:
`0069f800 → 004012bb → 0069f806 → 0069f800`, dentro de la conversión de
cadenas original. El traductor emitía cada JMP entre cuerpos recuperados como
una llamada nativa. La prueba CPU del ejecutable original conserva el texto
de 255 caracteres, ESP y ESI, pero con muestreo alcanza profundidades de
128, 256 y 512 antes de terminar. Identidad del probe previo:
`3f939375f874a19d6509d3d54494d210342e2c5d532710569a62e5776eab41ca`.
La corrección devuelve el destino EIP al despachador cuando están activas
las pilas reanudables. Conserva el salto original, los registros y la pila
invitada; no omite código ni amplía la pila del navegador. La configuración
local `legacy_address_intrinsics = false` que dejó DeepSeek se conserva.

La primera regeneración pasó la auditoría principal, pero falló al aplicar
por error a una DLL la auditoría de cuerpos retirados del ejecutable.
La auditoría se limita ahora a la imagen principal; la prueba de módulo
auxiliar cubre ese aislamiento sin relajar sus comprobaciones. Pasan 181
pruebas del traductor. La regeneración posterior pasa con cero fallos,
no modelados, huecos de tabla y tablas sin decodificar en la imagen principal
y las cuatro DLL. La compilación web completa y las pruebas posteriores
siguen en curso; sus resultados se añadirán al terminar.

Evidencia privada: `build/white-browser-depth-evidence.log`,
`build/tail-before-identity.json`, `build/tail-before-string-1.log`,
`build/tail-translator-tests.log`, `build/tail-web-regenerate.log` y
`build/tail-web-regenerate-fixed.log`. La suite DX conserva sus 27 fallos
históricos de cursor, disposición y DirectDraw, ajenos a esta corrección.
El sombreado plano de función fija sigue sin implementarse. La continuación
de la pantalla blanca en WebGPU, el prólogo, las voces y la primera misión
requieren verificación en navegador.

## Método virtual de límite de mundo ausente al iniciar partida (2026-10-15)

El informe del usuario detiene la carga nueva partida en `call to unknown
target 005347d0`. Es el método virtual de recorte de límites invocado desde
`0053303b` (`CALL [EDX+0x4]`, retorno `0053303e`): no tiene referencia estática
y solo lo nombra su hueco de tabla en `00866e7c`. El intérprete falla en
`005347eb` (x87 `FCOMP`), el método devuelve 0 y la caída posterior llama a
`c4e8600e` desde `00405cfe` (`CALL [EDX+0x8]`, retorno `00405d01`) y termina en
`memory access out of bounds`. Es un fallo en cadena, no dos huecos.

La causa no era la falta de candidato: el escaneo de punteros de datos sí
recupera el cuerpo (158 instrucciones, `005347d0..00534ac8`), pero una rama
desde su propio bloque de tabla de saltos (`00534acc`) hacia la continuación
`00534aa7` retiraba el tramo completo como cuerpo especulativo, porque no hay
prefijo terminado antes de ese destino. Un barrido de los cuerpos recuperados
y luego retirados reunió 33 candidatos; 8 conservan prólogo, terminador y
cuerpo verificados (los tres despachadores SEH `00474900`, `00478000`,
`00479da0` y `005cc290`, `005347d0`, `006419f0`, `00690220`, `006cb7c0`).
Los 8 se añaden como puntos de entrada explícitos de la variante con su
evidencia; el resto del barrido fueron inicios desalineados o fragmentos.

Traducción repetida: 50 679/51 963 funciones, 154 020 puntos de entrada
(+103 341 alternativos), sin fallos, sin no modelados y sin huecos de tabla.
Los ocho aparecen como `entry`/`config` en `build/recomp/gen/symbols.json` y en
la tabla de despacho `table.c`; las ramas internas de `005347d0` quedan como
continuaciones de su cuerpo. Los recuentos y la tabla no verifican una partida
jugable: la compilación web se inició después y la carga en navegador sigue
sin verificarse. Ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm servido al recibir el informe:
`61036d3839b212996dd5ed68205dad2905feaa088600f1155a315c84af0bdf72`;
no se midió el Wasm cargado en el navegador.

La compilación web siguiente terminó con salida 0 reutilizando esa traducción,
y la página del jugador se volvió a preparar. Wasm servido ahora:
`4dea1d033cc086d069d2c529b1cee0f22411373a2b11b045cedf62ba9037d529`
(253 836 912 bytes, JavaScript `f0a868da…`, paquete `f81f48d3…`). La carga en
navegador sigue sin verificarse y ninguna medición establece una partida
jugable.

## Extensiones de signo y movimientos de 16 bits al cargar partida (2026-10-15)

El informe posterior del usuario detiene la carga en `005c16f0`, retorno
`004a4b4e`. El primer rechazo es MOVSX EAX,AL en `005c17da`. Los registros
ampliados conservan ese primer bloqueo y añaden una aserción posterior de
mutex, contadores de audio sin datos y mensajes Failed to fetch repetidos.
No son evidencia de una partida jugable. Ejecutable:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm servido al recibir el informe:
`15e46e850bb21060057fa9cc8ef95b2fed6a269c243dcbef8d501645b1043164`;
no se midió el Wasm cargado en el navegador.

Se añadieron MOVSX/MOVZX de byte/word a registros de 32 bits y MOV de 16 bits
entre registros/memoria. La rutina original también usa MOV word en `005c1899`.
Las lecturas/escrituras comprueban exactamente los dos bytes accedidos;
los registros conservan sus 16 bits superiores al mover word y la memoria
adyacente no se modifica. Estas operaciones conservan los flags. Otros opcodes
con prefijo 0x66 siguen rechazados: no se interpretan como operaciones de 32 bits.
STRICT_UNKNOWN permanece activo y no se editan archivos originales/generados.

La prueba autónoma pasa **381 comprobaciones, 0 fallos**. Incluye extensión
negativa/positiva, registros byte altos, acceso word en el límite del arena,
vecinos de memoria, preservación de flags y rechazo de prefijos no soportados.
**35 casos contra Unicorn pasan**, salida 0. Sobre el ejecutable verificado,
la rutina completa desde `005c16f0` pasa el diagnóstico de decodificación sin
ejecutar instrucciones. No se presenta esa cobertura como ejecución de la
carga real. Evidencia privada: `build/narrow-result.json`,
`build/narrow-unit.log`, `build/narrow-decode.log`, `build/narrow-unicorn.log`.

El envío opcional de telemetría a /log no capturaba el rechazo asíncrono de
fetch: el try/catch solo cubría errores síncronos. Se añade el manejador de
rechazo. Además, la página conserva el primer error fatal en pantalla y guarda
los errores posteriores en el registro. Pasan 4 pruebas del servidor y 6 del
bootstrap, incluida la secuencia aborto → mutex → rechazo de red. No se afirma
que esto repare todas las peticiones de red ni la aserción de mutex. En la
comprobación posterior el servidor local estaba detenido y se inició de nuevo;
la página estricta responde HTTP 200 con la telemetría actualizada.

Compilación web terminada con salida 0. Nuevo Wasm servido:
`5ad508d814f7e05a0918dae876c12833793deccf6871635176831cc542f8fcb5`.
Probe CPU:
`6e158eb71e26bf436fabc7b500d52c32ac49d2610766bab8514cf27f3f931541`.
Quedan pendientes la continuación al iniciar partida en WebGPU, el prólogo,
primera misión y audio audible original. Los fallos históricos de la suite DX
y las interfaces opcionales pendientes se conservan en las secciones anteriores.

## Menú original verificado; bloqueo al iniciar partida (2026-10-15)

Las capturas del usuario muestran el menú original con Start Game, Options y
Quit Game. El registro inicializa SoundManager, arranca el dispositivo de audio
y envía PCM no nulo. Eso verifica envío al mezclador, no que se hayan escuchado
las voces o la música. Se actualiza original_menu_verified a true; no se
verifican jugabilidad, prólogo ni primera misión. El ejecutable sigue siendo
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
El Wasm servido antes del informe era
`45ff03479294726106c94f080659787065e8677d274dee1b5884767be3984848`;
no se midió el módulo que el navegador había cargado.

Al elegir jugar, el usuario informa de un abort estricto en `015633bd`. Sus
bytes originales coinciden con el comienzo informado. El decodificador acotado
rechazaba XCHG [ESP],EDX en `0156346e`; la misma rutina también contiene shifts
y multiplicación firmada de un operando. Se añadieron XCHG de 32 bits,
SHL/SHR/SAR e IMUL con resultado EDX:EAX, sin cambiar archivos originales,
fuentes generadas ni desactivar STRICT_UNKNOWN. Los shifts y la multiplicación
usan las funciones de flags del CPU traducido. XCHG conserva los flags y lee
ambos operandos antes de escribir, incluyendo operandos que forman la dirección.

La prueba autónoma del intérprete pasa **362 comprobaciones, 0 fallos**:
intercambio en pila y con direcciones que usan el registro intercambiado,
redirección de retorno, flags de shifts con cuenta cero/enmascarada, producto
firmado y overflow, además de los casos anteriores. Al habilitarla se corrigió
su seam de logging y fixtures anteriores que codificaban BH donde comentaban
BL, y direcciones DATA con orden de bytes incorrecto. Se implementó MOV inmediato
a registro byte, presente en una rama que el decodificador valida antes de
cualquier ejecución, aunque la prueba no la tome.

**23 casos contra Unicorn pasan**, comparando registros, memoria y flags finales
definidos. Unicorn en Windows emitió un diagnóstico SEH de acceso durante mem_map;
pytest completó igualmente con salida 0 y 23 passed. No se oculta ese diagnóstico.
El nuevo modo `game_boot_probe <exe> --decode <dirección>` usa el mismo
decodificador sin ejecutar instrucciones. Sobre la imagen verificada, toda la
rutina desde `015633bd` pasa. Esto es cobertura de decodificación, no una prueba
de que la partida arranque. Evidencia privada: `build/newgame-result.json`,
`build/newgame-decode.log`, `build/newgame-interp-tests.log`,
`build/newgame-unicorn-tests.log`.

Compilación web terminada con salida 0. Wasm servido:
`15e46e850bb21060057fa9cc8ef95b2fed6a269c243dcbef8d501645b1043164`.
Identidad del probe CPU:
`b84d9da4773e31e05ed5728faf19660575f87a9978986441cd43ed7fcf38e38d`.
Se conserva telemetría y el modo estricto. Queda pendiente comprobar en WebGPU
la continuación al iniciar partida. La captura también muestra una aserción
posterior de mutex, que no se ha aislado ni se declara corregida. Los 27 fallos
de la suite DX anterior y las interfaces opcionales no implementadas siguen
registrados en las secciones históricas siguientes.

## Listener del búfer primario y parámetros de audio 3D (2026-10-15)

El nuevo registro del navegador aportado por el usuario supera la fábrica EAX,
pero rechaza IDirectSound3DListener en un IDirectSoundBuffer. Después aborta en
un salto nulo desde `004f153c`; la captura muestra además un fallo posterior de
mutex pthread. El ejecutable sigue siendo
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
El Wasm servido al recibir ese informe era
`fffe4e4b468356f2db791b3d056efcde309b42b73d0dc1d7788cd9c87eddf97f`;
no se midió el hash cargado dentro del navegador.

La rutina original de creación usa flags 0x11 (PRIMARYBUFFER | CTRL3D) y pide
el listener al búfer primario. El runtime lo ofrecía solo en el dispositivo.
Ahora el búfer primario 3D expone esa interfaz sobre el mismo objeto COM, con
referencia propia que mantiene vivo el búfer. Las consultas desde búferes
secundarios o primarios sin CTRL3D se rechazan y ponen el resultado a cero.
Las consultas desde otras interfaces del búfer conservan esa restricción.
También se corrigió DS3DLISTENER: sus parámetros ocupan 64 bytes, no los 68
que exigía GetAllParameters y leía SetAllParameters. Se valida tamaño exacto.

La prueba enfocada ejecuta la fábrica EAX original traducida, crea el búfer
primario, obtiene su listener y libera la referencia inicial del búfer. Luego
GetAllParameters y SetAllParameters por las vtables originales pasan con un
registro de 64 bytes y canario posterior intacto. Salida 0, pila conservada.
Las pruebas DX añaden 37 comprobaciones sin nuevos fallos, incluyendo tamaño,
round trip, referencias y rechazo por capacidades. Total de la suite:
141.197 comprobaciones, **27 fallos** persistentes en layout del host, cursor
y fallback DirectDraw; no se declara que la suite completa pase.
Evidencia privada: `build/listener-result.json`,
`build/listener-factory-result.log`, `build/listener-dx-tests.log`.

Compilación web terminada con salida 0, página estricta HTTP 200 y telemetría
conservada. Wasm servido:
`45ff03479294726106c94f080659787065e8677d274dee1b5884767be3984848`.
Identidad de la prueba CPU:
`d37c00444de5db92b5f8fc18ca87f605e57a7e135a1d7a320a210e53a4cd9bb5`.
La compilación y estas llamadas aisladas no verifican el arranque posterior
en WebGPU, reproducción audible, menú, prólogo ni primera misión. El error de
mutex aparece después del aborto en el informe del usuario; no se ha aislado
su causa ni se afirma que esté corregido. FilterGraph e IKsPropertySet siguen
sin implementar.

## Enlace de DLL y creación de audio DirectSound8 (2026-10-15)

La captura aportada por el usuario verifica que aparece la pantalla original de
título/carga. No acredita menú ni juego. Su registro termina en una llamada nula
a GetCaps, retorno `004d9a25`, después de un éxito ficticio de `EAX.DLL!ord6`,
y sale con `c0000005`. El ejecutable sigue siendo
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
El Wasm servido al recibir el informe era
`68da1970d8c7e8a3e8e0b4fcf6e854a70f53bb9bc8d26f1e02e5b68b07f70bec`;
no se midió el módulo cargado dentro del navegador.

La exportación ordinal 6 de la DLL preparada es EAXDirectSoundCreate8. El
cargador enlazaba la IAT principal antes de mapear las DLL, dejando un trampoline
sin implementación en vez de la exportación original. Las importaciones entre
DLL también dependían del orden de configuración. Ahora primero verifica hashes
y mapea todas las imágenes; después enlaza las IAT por nombre/ordinal y guarda
las imágenes enlazadas para recarga. Se mantienen los límites PE originales.

Una prueba directa de esa exportación original reveló además que faltaba
CLSID_DirectSound8 y que IID_IDirectSound8 estaba mal registrado. Se corrigieron
ambos registros sobre el objeto DirectSound existente. No se reemplaza la DLL
original con un retorno simulado ni se desactiva el modo estricto.

La prueba enfocada con código traducido real verifica 58 importaciones entre
imágenes y sus snapshots de recarga. EAXDirectSoundCreate8 devuelve HRESULT 0,
objeto válido y pila conservada; la llamada GetCaps por su vtable original
también devuelve 0. La negativa IKsPropertySet sigue siendo explícita y la DLL
continúa por su alternativa soportada. Esto no demuestra reproducción audible
ni efectos EAX. Evidencia privada: `build/audio-factory-result.json` y
`build/audio-factory-result.log`.

La compilación web termina con salida 0 y ya se sirve el Wasm
`fffe4e4b468356f2db791b3d056efcde309b42b73d0dc1d7788cd9c87eddf97f`.
La página estricta responde HTTP 200 y conserva la telemetría local. La nueva
prueba CPU tiene identidad `93cc9525fb3580dae566458f2ec5ed9dac989c759d02a03e0ca1f431bcc8767b`.
La suite DX completa ejecuta 141.160 comprobaciones y termina con **27 fallos**:
expectativas de layout de host de 64 bits en wasm32, cursor aprendido y fallback
DirectDrawCreateEx. Los subtests de creación COM DirectSound/8 y de datos,
notificaciones y streaming de audio pasan. No se presenta la suite como verde.
Registro privado: `build/audio-dx-tests.log`.

Una ejecución CPU limitada a 45 segundos, anterior a la corrección COM, verificó
los enlaces y permaneció en el bucle de título; no alcanzó la inicialización de
audio y no sustituye la prueba enfocada. Se conserva su identidad en
`build/audio-link-probe-result.json`. Sigue pendiente la comprobación visual del
nuevo arranque en WebGPU y escuchar las voces/música originales. FilterGraph de
DirectShow sigue sin implementar. No están verificados el menú, prólogo,
primera misión ni estado jugable.

## Continuación de cámara y declaración de vértices (2026-10-15)

El usuario confirmó por registro del navegador que la corrección anterior
supera la creación de cámara e inicializa mods. Después rechaza un dibujo
sin FVF y aborta en `005908f7`. El ejecutable es
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
El Wasm servido al recibir el informe era
`97a801afbe5d5b8e606ee0065afa54fb765f5ea9d72c39f73c47cd2f5edba1f2`;
no se midió el hash del módulo cargado dentro del navegador. El bootlog local
contiene también una ejecución antigua sin modo estricto; no sustituye la
traza estricta pegada por el usuario.

Causa verificada: un listado truncado terminaba llamando a `007ee180`, que
retorna por un salto de despacho sin tener RET propio. El traductor lo
clasificaba globalmente como noreturn y omitía su continuación en `005908f7`.
La regla ahora conserva esas continuaciones. La nueva generación contiene
las instrucciones originales y la entrada compilada correspondiente, sin
el antiguo unknown_call en ese retorno. No se editaron fuentes generadas.

La primera regeneración se rechazó por una arista adicional: `0127f1df`
llama a un thunk que cambia el retorno de `0127f1e4` a `0127f292`. El
reconocedor existente `audit_checksum_call_thunks.inspect` verificó la
secuencia completa original, su checksum, destino calculado `0115cb30` y
RET 4. Solo entonces se registró el contrato local de no-fallthrough de ese
CALL y se repitió la traducción. Los archivos originales no se modifican y
RECOMP_STRICT_UNKNOWN permanece activado. Auditoría privada:
`build/fallthrough-checksum-contract.json`; contrato en el archivo de
configuración local indicado por no_fallthrough_calls_file del variant.
Los bloqueos del primer intento se conservan en
`build/fallthrough-initial-blockers.json`.

El dibujado fijo también acepta ahora declaraciones explícitas que coinciden
exactamente con los formatos FVF ya soportados. SetVertexDeclaration borra
el FVF, y antes esa ruta lo seguía exigiendo. Se validan tipos, offsets,
orden, stream y terminador; no se adivinan formatos ni se aceptan layouts
fuera del subconjunto implementado.

Verificación: 181 pruebas del traductor y 150 comprobaciones gráficas del
runtime pasan. La traducción completa termina con cero funciones fallidas,
cero instrucciones sin modelar, cero destinos literales colgantes y cero
huecos/sitios sin decodificar en las tablas. Las traducciones previamente
verificadas de las DLL de audio se conservaron. La compilación web final
termina con salida 0; los 32.182.155 bytes de symbols.json empaquetados
coinciden con la generación actual. V8 compila el Wasm servido y la página
estricta responde HTTP 200. Se conservan identidad y evidencia históricas.

El probe del entry original, con host gráfico/audio nulo y framebuffer CPU,
se limitó externamente a 20 segundos. Registró 59 presentaciones de 800x600,
hasta 281 de 4.949 muestras con color, sin reportes de llamada desconocida,
aborto ni rechazo del dibujado fijo. Terminó por el límite del ensayo;
no demuestra que el programa complete el arranque o que no pueda bloquearse
más adelante. Identidad de su Wasm y logs privados en progress.json.

Wasm web nuevo: `68da1970d8c7e8a3e8e0b4fcf6e854a70f53bb9bc8d26f1e02e5b68b07f70bec` (253710648 bytes). JS/data tienen sus hashes en
progress.json. El servidor local 8771 ya sirve esta compilación y conserva
el diagnóstico. Basta recargar el reproductor estricto con Ctrl+F5; no es
necesario repetir la importación del juego.

Pendiente: observar la imagen WebGPU en el navegador y cualquier bloqueo
posterior. El control de Windows no conecta con su canal nativo. Estas
comprobaciones CPU no verifican menú, introducción, misión, audio ni
jugabilidad, y no se declara resuelta toda la pantalla negra.


## Correcciones del runtime original (2026-10-15)

El registro del usuario llega a CreateDevice y termina con ExitProcess(0),
tras fallar la creación del raster de cámara. El ejecutable sigue siendo
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`. La traza anterior no prueba que el shader sea la causa única.
La identidad del Wasm anterior a esta recompilación no se capturó; no debe
atribuirse esa traza al binario nuevo.

Se corrigieron tres partes del runtime: el empaquetado web toma el mapa de
símbolos desde recomp/gen, donde sí existía; CreateDevice exclusivo sincroniza
el área de cliente con el back buffer, conserva la ventana de foco si se
omite la ventana del dispositivo y restaura la geometría al volver a modo
ventana; y los shaders independientes de vértices/píxeles ahora son objetos
COM con código validado, enlaces de pipeline y vida propia. Los programas
fuera del subconjunto soportado se rechazan. Referencia del contrato:
[CreatePixelShader](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-createpixelshader)
y [GetFunction](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3dpixelshader9-getfunction).

Compilación web con tools/build.py: salida 0. El paquete contiene los
31.806.103 bytes de symbols.json, idénticos al generado para este a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26.
139 comprobaciones de d3d9_ffp_tests pasan bajo Node/Wasm, incluyendo
creación/enlace/vida de shaders, dibujo programable real en framebuffer CPU
y GetClientRect 800x600 con restauración a 320x240. También pasan 4 pruebas
del servidor y 5 del bootstrap, los límites de literales del juego y
WebAssembly.compile sobre el Wasm servido. Son pruebas sin juego visual.

Wasm nuevo servido: `97a801afbe5d5b8e606ee0065afa54fb765f5ea9d72c39f73c47cd2f5edba1f2` (222734557 bytes).
Identidades JS/data y comprobaciones están en progress.json. El parche del
runtime conserva todos los cambios locales sobre la dependencia fijada.
La página de diagnóstico está actualizada en el servidor local 8771.
No requiere volver a importar los archivos originales.

Pendiente: recargar el reproductor con RECOMP_STRICT_UNKNOWN=1 y observar
si supera la cámara y qué bloqueo aparece después. El control de Windows
no conecta con su canal nativo; no se pudo ejecutar esa verificación visual.
No se declara resuelta la pantalla negra ni verificados menú, misión o audio.


## Pantalla negra del port original: diagnóstico del arranque

La captura del usuario muestra el canvas negro en el port singleplayer local.
Identidad del ejecutable: `a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
Wasm servido: `12c584f9c91d43022b157edcbe638bd363a73af1ae09cae7342189db3c374bab`, 202.564.142 bytes. Este cambio
no recompila ni sustituye el binario Wasm ni verifica juego en navegador.

Se verificaron dos defectos del arranque anterior: `tools/serve_variant.py`
solo ofrecía `gta_sa.exe` para importar y el reproductor ocultaba el estado
antes de entrar al motor. Los errores WebGPU y stderr quedaban en consola.
Esto no demuestra que falten archivos en el OPFS actual del usuario ni que
sea la única causa de la pantalla negra.

El servidor ahora inventaría exclusivamente los archivos preparados: 411
archivos, 5.001.060.148 bytes, incluidas las seis carpetas de recursos y las
bibliotecas preparadas. La nueva página reutiliza la importación del launcher
con hash del ejecutable, manifiesto reanudable y marca de finalización. No
modifica la instalación ni las partidas. El reproductor rechaza importaciones
sin esa marca o con carpetas requeridas vacías y conserva un registro visible
acotado de las fases y errores de arranque. Los cambios del runtime están
incluidos en el parche completo, conservando la dependencia fijada.

Comprobaciones: 5 pruebas del contrato JS de arranque, 3 de inventario/HTTP
y 6 del importador del launcher pasan (14 en total). También pasan la sintaxis
del módulo de importación, las peticiones HTTP reales a inventario/páginas/
archivo preparado y la comprobación inversa del parche completo. Son pruebas
sin renderizado y no acreditan menú, prólogo ni jugabilidad.

Para continuar: cerrar las otras pestañas del juego, abrir
`http://127.0.0.1:8771/seed.html`, pulsar Importar y comprobar archivos y,
al terminar, Iniciar port. El servidor se ejecuta con
`python tools/serve_variant.py`. El control de navegador disponible no
expone ninguna sesión conectada; quedan pendientes observar el OPFS, los
mensajes del motor tras importar y el primer fotograma. La pantalla negra
no se declara resuelta.


## Requisito: primera misi?n igual al original ? pendiente

El objetivo solicitado incluye audio, c?maras, animaciones y el paso real
hacia la BMX. La demo independiente no cumple ese requisito. No se declara
terminada la misi?n ni se sustituye el guion original por una transici?n
directa desde las escenas de prueba al circuito BMX.

Auditor?a reproducible del audio instalado: `npm run audit:opening-audio`,
desde `web/recreation/`. Las pistas PROLOG1 (706) y PROLOG3 (708) contienen
el mismo Ogg de 9.504 bytes y 1,18578125 segundos, con cuatro p?ginas cuyo
CRC es v?lido. Despu?s hay 330.107 y 1.116.893 bytes de ceros, respectivamente.
Las c?maras duran 22,333332 y 80 segundos. El hash del fragmento es
`be1e788caeb8e7f66f43f4c97505245bcc0723bb8ad3762568c15518ddb5b0f4`.
El archivo CUTS.IMG usado tiene hash
`28d9b9002ac5479106c06ce0fc390120f24e0ac2a2395517badbcbd0adf502cb`;
la identidad del EXE se conserva en las secciones anteriores y progress.json.
Los archivos CUTSCENE y CUTS.IMG extra?dos del RAR local coinciden por SHA-256
con los instalados; volver a extraer ese mismo RAR no cambia este resultado.

La validaci?n comprueba p?ginas, secuencia, fin de flujo y CRC seg?n la
[especificaci?n Ogg](https://xiph.org/ogg/doc/framing.html). FFmpeg decodific?
los dos fragmentos sin errores y produjo el mismo PCM. El fragmento no es
silencio digital puro; no debe describirse como un audio de duraci?n completa
ni como un error de volumen del navegador. Esto documenta las pistas le?das,
no descarta posibles modificaciones del cargador nativo. Queda pendiente
confirmar si esta misma instalaci?n reproduce las voces completas en PC.

Se a?adi? `SA_AUDIO_PATH`, que permite leer de otra instalaci?n sus archivos
y tablas de audio sin sobrescribir la copia actual. Ocho pruebas pasan,
incluyendo la selecci?n de una fuente independiente y el rechazo de un
checksum incorrecto. El diagn?stico local est? en
`web/recreation/checks/opening-audio.json` y permanece excluido de Git.
Los errores de animaci?n, la c?mara sin validaci?n nativa, PROLOG2 y la
l?gica de MAIN.SCM contin?an pendientes. No se verific? juego en navegador.


## Inicio original: trabajo en curso (2026-10-14)

El usuario aclar? que quiere la primera misi?n y la animaci?n de inicio
originales. La demo BMX anterior no satisface ese requisito. El men? ahora
la llama Demo BMX y enlaza por separado a un reproductor experimental.

Se a?adieron lectores de las definiciones CUT, c?maras DAT y animaciones
ANPK originales, acceso de solo lectura a los archivos de cinem?tica y
construcci?n del CJ con el esqueleto CSPLAY y las piezas CS_HEAD/CS_HANDS
indicadas por las reglas CUTS de la instalaci?n. No se incluyen archivos del
juego en Git ni se modifica la instalaci?n.

Comprobaciones: siete tests pasan; el ensayo CPU de PROLOG3 carga los 11
actores y los cuatro canales de c?mara, con duraci?n de 80 segundos. El
informe privado est? en `web/recreation/checks/cutscene.json`. Esta carga no
verifica una cinem?tica equivalente ni una misi?n en navegador.
La imagen de la instalaci?n sigue identificada por
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.

Bloqueos concretos:

- PROLOG1 no pasa la vinculaci?n estricta: L Toe0 de CJ contiene valores no
  finitos y tiene influencia en v?rtices visibles. Se produce un error y no
  se sustituye la animaci?n por una pose inventada.
- PROLOG3 presenta una deformaci?n de Pulaski en el instante cero del ensayo
  CPU. Falta comparar el tratamiento de las claves con el motor original.
- El lector de las pistas 706/708 obtiene un Ogg de aproximadamente 1,19
  segundos seguido de ceros, incompatible con las duraciones de las escenas.
  La ruta de audio lo rechaza. Esto requiere verificar los archivos y el
  lector; no demuestra por s? solo una instalaci?n da?ada. El reproductor
  permite inspeccionar animaciones sin audio, claramente identificado.
- Las claves ANPK no siempre est?n ordenadas por tiempo. El lector conserva
  sus valores y tiempos; el adaptador Three.js los ordena de forma estable.
  Esa adaptaci?n y la interpolaci?n de c?mara no tienen equivalencia validada.
- No hay navegador disponible en la herramienta de control de esta sesi?n.
  Renderizado, audio sincronizado, encuadres y actuaci?n siguen sin verificar.
- PROLOG2 y la l?gica de la primera misi?n en MAIN.SCM no se ejecutan.
  El reproductor no se presenta como una partida original completa.

Referencia t?cnica para el formato y el comportamiento:
[AnimManager](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Animation/AnimManager.cpp),
[CutsceneMgr](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/CutsceneMgr.cpp),
[tabla de pistas](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Audio/Managers/CutSceneStreamsPC.h),
[lector de audio](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Audio/Loaders/AETrackLoader.cpp).


## Recreación: El regreso (2026-10-14)

A petición del usuario se continuó el prototipo Three.js, conservando su
código en [web/recreation](../web/recreation/README.md). Tiene un primer
objetivo independiente: montar la BMX en Ganton, recorrer cuatro marcadores,
frenar frente a Grove Street, bajar y llegar a casa a pie. Incluye instrucciones,
marcador 3D, destino en radar, animaciones BMX, guardado de avance,
continuación y reinicio. No reproduce la misión SCM completa ni sus
cinemáticas, diálogos o persecuciones.

Evidencia local del 2026-10-14: tres pruebas de secuencia/guardado aprobadas;
prueba de recursos instalados y colisiones en CPU completó el recorrido y
la llegada a pie en aproximadamente 25 segundos simulados. Cargó 1.680
objetos del mundo sin fallos ni advertencias, el modelo BMX y sus animaciones.
Los puntos de paso tienen suelo comprobado a nivel de calle. El informe
reproducible se guarda localmente en `web/recreation/checks/opening.json`,
excluido de publicación. Identidad del ejecutable de la instalación usada:
`a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26`.
La recreación no ejecuta ese EXE y estos resultados no validan el port.

Bloqueo pendiente: no había navegadores disponibles en la herramienta de
control de esta sesión. Falta verificar renderizado, colocación visual de CJ
en el asiento, controles interactivos, radar, audio y guardado desde una
partida real de navegador. No se declara jugabilidad verificada.
Los recursos derivados de GTA permanecen locales e ignorados por Git.

## Evidencia del port original (histórico y trabajo independiente)

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

Triage del 2026-10-14 (imagen `a559aa77...`, solo lectura del EXE preparado):
10 fallidas dentro de rangos ejecutables, con mnemónicos sin soporte
(AAD en `00d52a60`/`00d53f60`/`00d55360`/`00f4fc03`, AAA en `00e38e40`,
IRETD en `00f73370`, CALLF en `010165e0`, FFREEP en `01020520`,
RETF en `0107fff0`, LDS en `010b6dd0`). Dos destinos pendientes
(`00d53f60`, `00d55360`) son a su vez funciones fallidas.
Muestra de 16 destinos únicos del log: 6 intra-imagen pero sin punto de
entrada (`00823b2d`, `0082aad3`, `00d3eee0`, `00d6309c` más las dos
fallidas) y 10 fuera de imagen y fuera de los buffers PE almacenados
(`01eaf735`, `1724475e`, `17247f17`, `172480f0`, `17268712`,
`1726891b`, `1726920c`, `8472872a`, `84728933`, `ed578108`).
`00823b2d` y `0082aad3` son la caída tras `FF15` (call a import) hacia
`CC` (INT3); `00d6309c` también cae sobre `CC`. Según `functions.tsv`,
`00823b2d` es el fin exacto de `___crtExitProcess` (47 bytes),
`00d3eee0` el fin exacto de `FUN_00d3ee1b` (197 bytes) y `0082aad3`
queda 7 bytes tras el fin de `report_failure`, en relleno `CC`.
Aceptarlos como entradas compilaría relleno como código; el rechazo
estricto es correcto y no se acepta ningún contrato con esta evidencia.
La lista completa de 147 no está exportada (el log solo imprime muestra);
el siguiente paso es extraerla y auditar caídas a relleno frente a
continuaciones con prefijo modificado, sin aceptar contratos a ciegas.
Regeneración estricta relanzada en fondo el 2026-10-14 para reescribir
`translate-report.blockers.json` con los 147 pares caller/target legibles;
el resultado esperado sigue siendo `needs_review`, solo se busca evidencia.

Xrefs en listados Ghidra de la variante (CALL/JMP estáticos): 7 fallidas
tienen llamantes (`00d52a60`←`0114c3c0`, `00d53f60`←`00d53e30`,`01097760`,
`00d55360`←`00d53a20`, `00e38e40`←8, `00f73370`←3, `010165e0`/`01020520`←2);
`00f4fc03`, `0107fff0` y `010b6dd0` no tienen ninguna referencia estática.
Las 10 están exportadas por Ghidra pero ninguna es alcanzable desde
`00824570` solo por aristas estáticas (BFS estático: 7.956 de 20.823);
el dispatch calculado/tablas puede alcanzarlas o no, sin probar en ningún
sentido. No se excluye ni se acepta nada con esta evidencia.

Clasificación completa de los 147 (`translate-report.blockers.json`
regenerado el 2026-10-14, 131 pares únicos): 99 fuera de imagen
(`01eaf735`, `0x172…`, `0x847…`, `0xed…`, 99 únicos), 30 contra 7 de las
fallidas (resolver esas 7 limpia esos 30) y 18 intra-imagen sin entrada
(caídas a relleno `CC`/fin de función). Las 3 fallidas sin xrefs
(`00f4fc03`, `0107fff0`, `010b6dd0`) son justo las no referenciadas por
ningún dangling. `translate.py:6662` devuelve 1 si hay fallidas aunque no
haya dangling: ambas clases bloquean. Plan: 1) soporte o exclusión
evidenciada de las 10 (AAD, AAA, IRETD, CALLF, FFREEP, RETF, LDS) vía
parche completo del runtime; 2) caídas a relleno con sitios no-retorno
evidenciados; 3) basura fuera de imagen tras calls sin retorno.

AAD implementado el 2026-10-14 (emisor en `translate.py` junto a CBW +
entrada `FLAG_EFFECT`; `CF/OF` a cero como calcula Unicorn, `SF/ZF/PF` del
AL resultante, `AF` intacta y muerta): fallidas 10→6 y dangling 147→146.
Se limpian las refs a las 3 AAD llamadas, pero los cuerpos recién traducidos
aportan 5 nuevas (`00d52a60`→`00d52a85`, `00d53f60`→`ed58988a`/`00d5404c`,
`00d55360`→`00d553bd`×2), incluido un call directo a basura fuera de imagen
dentro de función listada. Verificación: fórmula contra Unicorn exhaustiva
(65.536 AX × 6 bases = 393.216 casos, 0 discrepancias en EAX y
CF/PF/ZF/SF/OF/DF/AF); 309 suites proyecto/driver/SEH pasan; 4 casos harness
C añadidos a `test_translate_insns.py` pero omitidos aquí (sin clang en
PATH). Parche completo regenerado (`patches/current-vendor.patch`, 197.482
bytes). Siguiente más rentable: AAA (`00e38e40`, 14 refs, mayor hub).

AAA implementado el 2026-10-14 (emisor + `FLAG_EFFECT` con uso de AF;
3 casos harness): fallidas siguen en 6 porque `00e38e40` contiene también
AAS (`00e38fa3`, revelado al emitir AAA), y dangling 146→148. Verificación:
fórmula contra Unicorn exhaustiva (65.536 AX × 10 inicios de flags =
655.360 casos, 0 discrepancias). Hallazgo: Unicorn/QEMU ajusta como
`(AX+0x106)&0xFF0F` con máscara del nibble de AL siempre aplicada
(`0x0010`→`0x0000` sin ajustar) y acarreo de 16 bits hacia AH
(`0xFFFF`→`0x0105`), distinto del SDM; la emisión lo replica bit a bit y el
comentario lo documenta. Dinámica observada: cada mnemónico nuevo admite
más bloques del barrido (+77 funciones descubiertas con AAA, byte `0x37`
ubicuo) con su propio dangling; el soporte de instrucciones solo no cierra.
309 suites pasan; parche a 199.676 bytes. Siguiente: AAS en la misma función.

AAS implementado el 2026-10-14 (espejo de AAA con préstamo de 16 bits,
misma `FLAG_EFFECT`, 3 casos harness): fallidas 6→5 y dangling 148→134
(−14 exactos, las refs al hub; su cuerpo aporta 0 nuevas). Verificación:
655.360 casos exhaustivos contra Unicorn, 0 discrepancias; 309 suites pasan;
parche a 201.844 bytes. Quedan: IRETD (`00f73370`, 3 refs + 3 llamantes),
CALLF (`010165e0`, 4 refs + 2 llamantes), FFREEP (`01020520`, 2 refs + 2
llamantes), RETF/LDS (sin xrefs ni refs). Siguiente: IRETD.

IRETD implementado el 2026-10-14 (emisor como RET con `x86_set_eflags` del
dword superior y `ESP+=12`, sin caída en `successors`, ajuste de pila +12,
`FLAG_EFFECT` total, `readonly` + análisis de registros): fallidas 5→4 y
dangling 134→131 (−3 exactos del hub, 0 nuevos del cuerpo). Verificación:
modelo contra Unicorn con GDT (orden EIP/CS/EFLAGS, `ESP+=12`, EFLAGS
restaurado bit a bit salvo reserved 3/5 que el silicio enmascara igual que
ya hace POPFD del kit); sin caso harness C porque Unicorn sin GDT no
ejecuta IRET. 309 suites pasan; parche a 204.679 bytes. Quedan: CALLF
(`010165e0`, 4 refs + 2 llamantes), FFREEP (`01020520`, 2 refs + 2
llamantes), RETF/LDS (sin xrefs ni refs). Siguiente: CALLF.

CALLF (`010165e0`, 4 refs): NO es un emisor pendiente sino bytes
solapados mal decodificados. Evidencia: `CALL 0x01016680` salta al medio
del stream lineal (`FD 59 9A...` = STD/POP/CALLF), mientras en `01016680`
hay otro stream coherente (`ADD [ESP],0xad; PUSH [ESP]; ... PUSH SS;
POP SS; ... CALL 0x1751bf50` fuera de imagen). El selector `0x81d9` no
existe en el modelo plano; modelarlo sería mentir. Vía: prueba de
callejón-sin-retorno/solapamiento, no emisor. Contextos iguales en RETF
(`CALL 0x01080030; RETF 0x6ba2`, stub de 16 líneas) y LDS
(`LOOP; LDS EDX,[EBX+wild]` + cola `ADD AL,0x24...` idéntica a la de
`00e38e40`/`010165e0`).

FFREEP implementado el 2026-10-14 como `";"` junto a FFREE: Unicorn 2.1.4
lo ejecuta como no-op total (sin cambio de tags ni TOP en pilas
llena/parcial/vacía, confirmado vía FNSTSW) y el kit ya modela FFREE como
`";"`. Difiere del free+pop documentado por AMD; si evidencia de navegador
muestra desync x87 vivo, se revisa. Caso harness con FNSTSW. Fallidas 4→3,
dangling 131→129 (−2 exactos, 0 nuevos). 309 suites pasan. Quedan CALLF,
RETF y LDS, los tres en código solapado/basura. Siguiente: análisis de
retorno de sus CALLs previas.

CALLF/RETF/LDS resueltos el 2026-10-14 SIN emisores falsos: son colas
muertas tras CALLs a streams solapados (01016680, FUN_01080030 en bucle
infinito solapado, LOOP) con selectores salvajes (`#GP` seguro en HW).
CALLF/JMPF/RETF emiten trap en runtime pre-parseo (precedente AVX);
LDS/LES/LSS/LFS/LGS cargan el GPR y descartan el segmento (precedente
`MOV`-sreg ya existente); RETF/JMPF sin caída en `successors`.
Tres sitios hermanos ya los eliminaba la maquinaria no-retorno. Fallidas
3→0 y dangling 129→125 (−4 refs a CALLF). 309 suites pasan. Quedan 125
dangling (119 únicos, todos ≤2 refs): basura fuera de imagen + caídas a
relleno intra-imagen. Siguiente: sitios no-retorno auditados.

Clasificación de los 119 únicos (2026-10-14, `translate-report.blockers.json`
+ bytes originales): 103 fuera de imagen (`0x172…`, `0x847…`, `0xed…`,
`01eaf735`, calls/jumps decodificados tras calls sin retorno) y 16
intra-imagen, todos saltos directos (`goto_target`) a no-entradas: 3 tras
fin de función a relleno `CC` (`00823b2d` fin de `___crtExitProcess`,
`0082aad3` tras `report_failure`, `00d3eee0` fin de `FUN_00d3ee1b`), 4 a
`CC` desde bloques de barrido (`00d6309c`, `00d640a8`, `011eded6`,
`01283b80`), 5 a mitad de instrucción propia o ajena (`00d52a85` +1,
`00d5404c` JMP-a-HLT, `00d553bd` +2, `00e3b569` +6, `01297dd8` +5) y 4 entre
bloques de barrido (`011763c8`, `01287bb3`, `0128afd9`, `0128b8bd`).
`closed_noreturn_loop(FUN_01080030)` = False verificado: su JMP final cae a
mitad de instrucción (`01080055` = `RET 4` dentro del MOV), el kit no puede
seguir solapamientos y es correcto que no lo pruebe. Vía: sitios
no-retorno auditados en la config de la variante + auditoría de
solapamientos, nunca emisores falsos.

Dangling restante (2026-10-14): 223 de 238 direcciones implicadas
(targets + entries alternas) no tienen NINGUNA referencia CALL/JMP estática
en 20.823 listados (`analysis/dangling-xref.json`). Caso trabajado
`FUN_01017ce0`: sus 5 CALLs fuera de imagen están tras `XOR/JZ` y la prueba
`constant_zero_branches` los demuestra muertos… con roots mínimos (108
insns podadas). Pero el cuerpo emite con 8 entries alternas
(`01017cfa`, `01017d12`, …) de conjetura del barrido, cero refs estáticas;
con ellas, `reached()` alcanza `JMP EDI` (`01017e13`) y el veto de
`translate.py:2411` anula TODA la prueba → se emiten los 5 CALLs → 5
dangling. Bucle autosostenido: prueba anulada → CALLs vivos → sus
fallthroughs propagan entries → entries anulan la prueba. Arreglarlo toca
interacción descubrimiento/entries/veto: trabajo de diseño con regresión
propia, no un parche local. La puerta sancionada para calls fuera de imagen
(`--allow-unmodelled` → trap) sigue cerrada a propósito.

Censo de entries (2026-10-14, ledger temporal
`translate-report.blockers.seeders.json`, revertible): 102.379 entries
extra en total — 85.543 `call-fallthrough`, 16.831 preexistentes al loop,
5 `ud2-retry`. De las 8 alternas de `FUN_01017ce0`, 6 son preexistentes y
solo 2 las sembró el loop (desde los propios CALLs muertos, prueba ya
anulada: circularidad completa). Mecanismo verificado por replicación:
con roots mínimos la prueba poda 108/118 insns; con las 8 entries,
`reached()` alcanza `JMP EDI` y el veto (`translate.py:2411`) la anula
entera. La política «structural nunca se retira; una conjetura sí»
(`translate.py:5956`) ya existe para cuerpos; falta su dual para entries
que anulan pruebas: retirar conjeturas sin referencias ni provenance que
mantienen vivo código demostrablemente muerto. Siguiente: implementar ese
retiro acotado con regresión propia (patrón `test_translate_noreturn.py`),
suites, y pasada completa.

Retiro withdrawn_entries implementado el 2026-10-14 (config withdrawn_entries_file, filtro en propagacion y 	ranslate(), 4 regresiones con stub de bytes+capstone, auditoria de 8 entries sin refs): dangling 147 - 5 de FUN_01017ce0 = en curso; 317 suites. Mecanismo autocorrectivo via re-siembra.

Sitios no-retorno auditados el 2026-10-14 (
o_fallthrough_calls_file extendido a indirectos via IAT con nombre en NORETURN_IMPORTS, validacion ruidosa, trap unificado en emision, regresion): 8 sitios (ExitProcess x2, TerminateProcess x1, RaiseException x5). 318 suites.

orget_bodies_file implementado el 2026-10-14 (reutiliza la via orget existente; load_forget_bodies validado con regresion en 	est_translate_config.py): 94 cuerpos huerfanos auditados (fuera de toda span Ghidra, cero refs, basura probada por bytes) olvidados; la cascada de poda hizo el resto. 328 suites.

Regla off-image-CALL-noreturn el 2026-10-14 (
ever_returns cubre CALL directo fuera de imagen/shims/intrinsecos, con guarda sin-bytes para tests; regresion nueva): el trap NO limpia filas vivas, solo poda colas; verificado en la pasada. 329 suites.

Estado 2026-10-14: 0 fallidas, 9 dangling tras olvidar 3 huerfanos mas (97 forget total): 00d52a60→00d52a85, 00d53b90→01eaf735, 00d55360→00d553bd (x2), 012907c0→16ed3fc0, 01297d80→01297dd8. Fase 1 COMPLETA (traduccion estricta en verde). Fase 2 COMPLETA (wasm publicado, V8 OK). Fase 3 COMPLETA el 2026-10-15: el juego ABRE en el navegador (menu alcanzado, verificado por el usuario). Cadena de desbloqueos: CreateEx real (IDirectDraw7), presencia d3d8/dpnhpast, DirectSoundCreate8, modos de pantalla con 800x600x32, GetRenderTarget real, entrada 00750760, build XP SP2 2600. La puerta de salida del entry (008246fc) NO se dispara en el arranque real. Pendiente de verificar: menu operable, intro, mision, fisica.

## Criterios de aceptación pendientes

- Arranque del ejecutable actual con imports y destinos estrictos.
- Menú original renderizado y operable en el navegador.
- Intro y cinemática originales con audio y sincronización.
- Primera misión original, con sus scripts y condiciones reales.
- CJ animado correctamente y control del jugador.
- Vehículos con comportamiento físico original.
- Entrada, audio y guardado verificados durante juego real.

La demo de recursos y las pruebas con host sin gráficos no satisfacen estos
criterios. El conteo de funciones o una compilación Wasm tampoco los satisface.Retiro withdrawn_entries implementado el 2026-10-14 (config, filtro en propagacion y 	ranslate(), 4 regresiones con stub de bytes+capstone, auditoria inicial de 8 entries sin refs): dangling 125-120 (las 5 de FUN_01017ce0 fuera, 0 nuevas). 317 suites. Mecanismo autocorrectivo via re-siembra; oleada 1 (87 entries) movio el tablero en ambas direcciones y llevo a auditar el censo completo.

Sitios no-retorno auditados el 2026-10-14 (
o_fallthrough_calls_file extendido a indirectos via IAT con nombre en NORETURN_IMPORTS, validacion ruidosa, trap unificado en emision para ambas ramas de CALL, regresion): 8 sitios (ExitProcess x2, TerminateProcess x1, RaiseException x5, bytes verificados). Dangling 120-117 (las 3 colas a CC tras ExitProcess). 318 suites.

orget_bodies_file implementado el 2026-10-14 (reutiliza la via orget existente; load_forget_bodies validado con regresion en 	est_translate_config.py): 94 cuerpos huerfanos auditados (fuera de toda span Ghidra, cero refs, basura probada por bytes) olvidados; la cascada de poda hizo el resto. Dangling 117-12 (108 fuera, 3 huerfanos nuevos). 328 suites.

Regla off-image-CALL-noreturn el 2026-10-14 (
ever_returns cubre CALL directo fuera de imagen/shims/intrinsecos, con guarda sin-bytes para tests; regresion nueva; el trap NO limpia filas vivas, solo poda colas). Dangling 12-9 (fuera las 3 filas de CALLs fuera de imagen y tambien 00d3eee0/00d5404c/00e3b569 por dinamica de pruebas; 3 huerfanos nuevos auditados a forget, 97 total). 329 suites.

Estado 2026-10-14: 0 fallidas, 9 dangling: 00d52a60-00d52a85, 00d53b90-01eaf735, 00d55360-00d553bd (x2), 012907c0-16ed3fc0, 01297d80-01297dd8, mas 3 huerfanos en forget. Siguiente: medir la pasada en curso (PID 19392).
