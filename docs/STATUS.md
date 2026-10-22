# Estado actual

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
