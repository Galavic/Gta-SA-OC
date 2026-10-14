# Registro histórico

Estos resultados incluyen otras imágenes y no sustituyen docs/STATUS.md.

# GTA San Andreas PC → WebAssembly

## Revisión del avance de OpenCode

El motor original todavía no arranca ni es jugable. `game.toml` vuelve a
`analysis/curated-core-checksum-neutral`, derivado de `curated-core-local`: las rondas `dead1` a `dead9` se conservan para
investigar, pero su grafo de llamadas directas no prueba que sus exclusiones
sean seguras. La revisión está en `analysis/quarantine-handoff-review.json`:
152 listings retirados, 48 declaraciones de datos añadidas y cuatro cruces
con contratos de transferencias originales previamente verificados.
La compilación diagnóstica de `dead9` se detuvo después de que el descubrimiento
pasara de 20.158 a 49.081 cuerpos; no llegó al enlace Wasm.

Se conserva la corrección de `Image.recover` para detenerse ante datos
declarados, con pruebas de entrada, salto y continuación. Se desactivaron para
GTA las sustituciones `setjmp`/`longjmp` en direcciones fijas de otro ejecutable
(`legacy_address_intrinsics = false`). El parche acumulado actual está en
`patches/current-vendor.patch`; sustituye a los parches parciales sobre el
checkout fijado, no se aplica encima de ellos.

Validación actual: 252 pruebas Python; recuperación idéntica en 64 funciones
de inicio (2.107 instrucciones, tres recorridos); 1.449 ejecuciones comparadas
x86/Wasm de 161 prefijos originales, también contrastados con el análisis
activo. La continuaci?n de excepciones UD2 coincide con Windows x86 en seis casos;
dos casos Wasm comprueban la reanudaci?n de registros SEH despu?s de abandonar
el marco de llamada traducido. Se reconstruy? el cuerpo nativo de `00f1211a`
(131 instrucciones) sin modificar el EXE. La ?ltima revisi?n individual emite 13 de los 15 cuerpos que fallaron
en el intento completo; esa comprobaci?n aislada todav?a deja dos fallos.
El intento completo sobre `curated-core-checksum-neutral` termin? con 15
funciones fallidas y 229 referencias pendientes, antes de los nuevos fixes
de anotaciones de predicci?n de saltos y del alias SAL. Est? archivado en
`build/strict-neutral-full-blockers.json` y `build/strict-neutral-full.log`. Estas pruebas no ejecutan el motor completo. El runtime sigue sin
implementar Direct3D 9 y DirectInput 8: sus registros actuales son stubs.
Los resultados del intento completo están en `build/web-status.json` y
`build/web-build.log`; `playable_verified` permanece en `false`.

Optimización medida: la conversión de operandos evita una segunda copia de
las estructuras de Capstone. En 6.000 instrucciones originales y tres
recorridos, el tiempo mediano pasó de 0,123 a 0,081 segundos (1,52× en esa
muestra), con salida idéntica. Datos en `build/operand-conversion-benchmark.json`.
Esto no mide la traducción completa ni acelera por sí solo la compatibilidad.

Se evaluó `LostMyCode/d3d9-webgl`, revisión
`9f2543a8488133182cef920a58763765cff3ddf7`, como posible backend reutilizable.
Su C++ compila a objeto Wasm en `build/d3d9-webgl-probe.o`; no está integrado
con el EXE. La cobertura parcial, sin shaders programables, aún requiere
comprobar las necesidades reales de GTA y adaptar la interfaz de 32 bits.

```powershell
.venv/Scripts/python.exe -m pytest -q tests vendor/recomp-kit/tools/recomp/tests/test_translate_driver.py vendor/recomp-kit/tools/recomp/tests/test_translate_seh.py
.venv/Scripts/python.exe build.py --target web --regenerate --jobs 4
```

Objetivo: ejecutar el código original de PC recompilado, con su lógica,
misiones, menús, física y audio originales. El prototipo Three.js anterior
permanece en U: como herramienta de inspección de assets. El port continúa
en `.`.

## Estado comprobado

- Ejecutable local: PE32/i386, 15.806.464 bytes, base `0x00400000`,
  entrada `0x00825330`. Identidad fijada por SHA-256 en `game.toml`.
- Configuración preliminar aceptada por `recomp-kit`; instalación local validada
  y enlazada mediante una junction en `original/`.
- Ghidra 12.1.3 y Temurin JDK 25 instalados como herramientas portables,
  verificadas mediante SHA-256. Emscripten 6.0.12 instalado y responde a
  `emcc --version`; no se modificó el PATH global.
- Análisis automático de Ghidra terminado sin timeout: exportó 20.377
  funciones y 1.055.241 instrucciones. Esta detección incluye secciones
  adicionales del EXE y no demuestra recuperación completa ni distingue
  por sí sola todo el código de los datos.
- Prueba con `pcrecomp`: 64 funciones alcanzables mediante llamadas directas
  desde la entrada, 2.437 instrucciones traducidas a C.
- El motor principal todavía NO está compilado ni probado por equivalencia.
  Las DLL de audio compilan a objetos Wasm y algunas instrucciones tienen
  pruebas de ejecución x86/Wasm; aún no hay un juego original arrancable.
- Este muestreo no identifica todas las funciones: quedan llamadas indirectas,
  destinos directos pendientes, tablas de salto y módulos externos.

Los dos traductores tienen runtimes distintos. La prueba `pcrecomp` permite
examinar el código de entrada; sus fuentes no se pueden conectar directamente
al runtime `recomp-kit`.

## Repetir la prueba en Windows

Requiere Python 3.11 y Git. Herramientas externas fijadas:

- `pcrecomp`: `8f4aa77aaf9e70f486a0fbc6b39a7ee14ae4fda1`
- `recomp-kit`: `eb32cc42623e0e9e868b9d27423a57d5a5cba56b`

El kit tiene un parche local de caché y progreso del traductor, conservado en
`patches/recovery-cache.patch`. Sobre el checkout fijado:

```powershell
git -C vendor/recomp-kit apply ../../patches/recovery-cache.patch
```

Verificación del parche: 194 pruebas pasaron y la comparación
con el algoritmo original devolvió las mismas 2.107 instrucciones para las
64 funciones de la muestra, en tres recorridos. Esto no valida ejecución del
juego ni equivalencia de la traducción x86→C.

```powershell
.venv/Scripts/python.exe -m pytest -q tests vendor/recomp-kit/tools/recomp/tests/test_translate_driver.py
.venv/Scripts/python.exe verify_recovery.py
```

Desde `.` (el muestreo opcional requiere pcrecomp):

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe audit.py '<local-game-install>\gta_sa.exe'
```

Resultados privados en `analysis/pe.json`, `analysis/sections.txt`,
`analysis/startup-probe.json` y `build/startup-probe/*.c`.
`--max-functions` cambia el límite de la muestra, no establece cobertura total.

Para el análisis y la compilación con el runtime web:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
python bootstrap_analysis.py
python analyze.py
.venv/Scripts/python.exe audit_embedded.py
.venv/Scripts/python.exe imports_audit.py
python build.py --target web --regenerate
```

`bootstrap_analysis.py` descarga herramientas oficiales fijadas por checksum.
`analyze.py` guarda el proyecto Ghidra y exporta ensamblador e índice de funciones;
no usa pseudocódigo del decompilador como fuente. `build.py` requiere el SDK
activado en `<user-home>\GTASAWebToolchains\emsdk`, o `--emsdk RUTA`.
Versión instalada: Emscripten 6.0.12; revisión emsdk:
`35ff8a6d150541276abbc6bae512ca90bcfbe220`.

El inventario estático de registros del runtime encontró 180 manejadores por
nombre, seis registros stub y 28 importaciones sin registro localizado. Esto
no valida comportamiento, firmas ni llamadas dinámicas. Se conservan detalles
en `analysis/imports-coverage.json`.

## Trabajo pendiente para ejecutar el original

1. Traducir el análisis exportado de esta versión del EXE con `recomp-kit`.
   Las herramientas portables compatibles
   ya están instaladas; el Java 8 global permanece sin cambios.
2. Resolver direcciones indirectas, callbacks, DLLs y verificar la equivalencia
   de funciones traducidas. No se han inventado símbolos ni hooks de GTA.
3. Adaptar y comprobar la superficie Win32/Direct3D 9/audio de GTA. El kit
   contiene D3D9 sobre WebGPU, pero eso no demuestra compatibilidad con GTA.
   Las cuatro DLL originales de audio ya se han traducido a C mediante
   módulos auxiliares; sus llamadas y efectos de sonido aún necesitan
   validación en ejecución.
4. Compilar con LLVM/Emscripten en el entorno local y resolver errores del
   primer intento de build web. El preset web del kit no restringe el sistema
   anfitrión; esto permite probarlo en Windows, aunque su documentación cita
   regeneración en macOS o Linux. No se ha verificado que este port compile.
5. Verificar arranque, menú original, partida, misiones, audio y guardado en
   navegador con WebGPU y COOP/COEP. Ninguno está validado aún.

No usar `--stub` como demostración del juego: ese modo compila un programa
sustituto del kit, sin código de GTA.

## Referencias de la investigación

- [recomp-kit](https://github.com/veritr1x/recomp-kit): runtime y backend web.
- [nfsmw-recomp](https://github.com/veritr1x/nfsmw-recomp): integración de otro
  juego PC con este kit; no es una integración de GTA.
- [pcrecomp](https://github.com/sp00nznet/pcrecomp): análisis y prueba de traducción.
- [gta-reversed](https://github.com/gta-reversed/gta-reversed): inversión parcial,
  actualmente integrada mediante DLL/ASI; no constituye un port web completo.
- [Análisis de artefactos del caso GTA V](https://github.com/shadany7824/playgta5/blob/main/ENGINE_INVESTIGATION.md):
  identifica Wasm, símbolos RAGE y adaptaciones de navegador; no proporciona
  un procedimiento público para convertir este ejecutable de GTA SA.

El ejecutable, assets, fuentes traducidas y análisis permanecen locales e
ignorados. Las licencias de las herramientas permanecen en sus repositorios.

## Migración a C:

Análisis copiado con los 20.377 listados, índice y proyecto Ghidra conservados.
Entorno Python recreado localmente y 194 pruebas aprobadas. La comparación
con el recuperador original conserva las 2.107 instrucciones de la muestra
de 64 funciones en tres recorridos; esto no prueba ejecución del juego.

`audit_embedded.py` valida cinco programas PE almacenados y las dos tablas
antes confundidas con código del contenedor, sin modificar el EXE. Estos
programas necesitan carga y reubicación propias si se invocan. Los resultados
se guardan en `analysis/embedded-audit.json`.

## Entradas corregidas y dependencias originales

`curate_thunks.py --output analysis/curated-core-next` crea el análisis activo
sin modificar el export crudo de Ghidra: separa 1.683 trampolines decodificados
en la dirección exacta que almacena el EXE, incluidos saltos dentro de funciones.
`verify_curated_thunks.py --input analysis/curated-core-next` compara sus instrucciones con
los bytes originales y verifica los saltos, registros, banderas y pila en
Unicorn. Esto valida entradas de análisis, no la ejecución del C traducido.
También verifica que los 52 fragmentos separados solo cubran wrappers de su
propia función y que las otras instrucciones permanezcan idénticas. Las
844 llamadas con metadatos en línea conservan su CALL y dirección de retorno;
se detiene la recuperación de código en sus datos. La clasificación usa el
protocolo común y trazas acotadas de cinco entradas, no ejecución completa
del juego. Un retorno inesperado a esos datos produce un error explícito.
Se usa el modo del kit `resumable_stacks` para conservar las continuaciones
que se transfieren mediante RET y JMP indirectos.

Las cuatro DLL de audio se preparan en direcciones separadas; se verifican
9.741 relocaciones y se comprueba que no cambien otros bytes salvo base y
checksum. `original/` permanece intacto; `prepared/` contiene copias del EXE
y las DLL, con junctions a los assets. El EXE preparado conserva el mismo
SHA-256. Las identidades fuente están fijadas en `audio_modules.toml`.

```powershell
.venv/Scripts/python.exe prepare_audio_modules.py
./prepare_install.ps1
python analyze.py
.venv/Scripts/python.exe audit_core_data.py
.venv/Scripts/python.exe curate_thunks.py --output analysis/curated-core-enter
.venv/Scripts/python.exe verify_curated_thunks.py --input analysis/curated-core-enter
.venv/Scripts/python.exe analyze_audio.py
.venv/Scripts/python.exe translate_audio.py
.venv/Scripts/python.exe compile_audio_wasm.py
.venv/Scripts/python.exe audit_module_imports.py
.venv/Scripts/python.exe audit_overlapping_branches.py
.venv/Scripts/python.exe verify_branch_wasm.py
.venv/Scripts/python.exe verify_enter_wasm.py
.venv/Scripts/python.exe probe_failed_functions.py
python build.py --target web --regenerate --jobs 2
```

EAX, Ogg, Vorbis y VorbisFile pasaron la traducción estricta independiente.
Las cuatro bibliotecas también compilaron con Emscripten a 15 objetos
WebAssembly, archivados bajo `build/audio-wasm/`. No son un juego enlazado ni
una prueba de ejecución del audio.
El inventario ampliado contiene 58 importaciones servidas por sus exports,
401 registros de manejadores nativos, 15 registros stub y 16 sin registro.
Son conteos de importaciones entre cinco imágenes, no APIs únicas ni pruebas
de compatibilidad. Detalles en `analysis/all-module-imports.json`.

El primer intento completo en C: falló por 466 destinos de dispatch sin entrada;
el registro se conserva en `build/web-attempt-1.log`. El siguiente intento
usa el análisis corregido y soporte FEMMS, equivalente en los efectos definidos
de etiquetas a EMMS según el manual AMD APM, volumen 5. Todavía no se ha
verificado un juego WebAssembly arrancable.

El segundo intento terminó con 440 destinos de dispatch sin entrada. Quedan
fragmentos mal alineados y llamadas con datos en línea que deben analizarse
antes de regenerar; los errores no se aceptan como código funcional.

El tercer intento quedó interrumpido antes de terminar. Se inició una nueva
traducción estricta con los 1.683 wrappers verificados y 844 contratos de
llamada; su resultado se registra en `build/web-status.json`. El estado
`running` solo describe el proceso, no una compilación ni un juego jugable.

`audit_overlapping_branches.py` encontró 316 secuencias XOR/JZ adyacentes
en 135 funciones cuyo destino tomado cae dentro de otra instrucción listada.
Comprueba el patrón en los bytes originales y decodifica el destino exacto;
no cambia listados ni prueba la alcanzabilidad de la función entera. El
informe está en `analysis/overlapping-branches.json`.

El escaneo de punteros ahora consulta un índice de la unión de rangos de
tablas, en vez de recorrer todas las tablas por candidato. Diez casos nuevos
verifican límites, solapamientos, almacenamiento y prioridad de entradas ya
conocidas. Se reinició la traducción para usar este índice; el registro previo
se conserva en `build/web-attempt-pre-index.log`. No se ha medido aún su efecto
en el EXE completo.

## Instrucciones ejecutadas en WebAssembly

El último intento completo anterior a los cambios de ramas y segmentos terminó
con 178 funciones fallidas y 429 sitios de dispatch pendientes, correspondientes
a 94 destinos únicos. Se conserva en `build/strict-before-loop-segments.log`
y `build/strict-before-loop-segments-blockers.json`.

Se corrigió la recuperación de los destinos de LOOP, sus variantes dependientes
de ZF, JCXZ y los contadores CX/ECX según el tamaño de dirección. También se
admiten POP de segmentos que recargan exactamente el selector fijo del contexto
Win32 plano. El cambio de descriptor sigue sin estar modelado: se detiene de
forma explícita. POP SS también rechaza el modo de ejecución paso a paso,
porque el runtime no implementa su sombra de interrupciones y depuración.
Se conserva la lectura de la pila y su incremento de 2 o 4 bytes; no se ignora
la instrucción ni se habilita `--allow-unmodelled`.

`verify_branch_wasm.py` compila con Emscripten mediante el driver del kit y
ejecuta el C traducido en Node. Compara 405 ejecuciones de 10 formas de ramas,
4 formas de recarga SS y una función original de GTA con las mismas
instrucciones x86 en Unicorn. Para
los segmentos, Unicorn entra en CPL3 mediante IRET y descriptores GDT planos;
los registros, banderas y PC coinciden. Tres estados de segmento no admitidos
se rechazan explícitamente. La función original en `0x00407800` aporta 27
casos acotados de lectura de tabla; AF después de TEST es indefinida y solo
esa bandera se excluye de su comparación. Estos casos no ejecutan el juego.
El resultado queda en `build/branch-wasm-status.json`.

En la prueba individual de los 178 cuerpos fallidos, 104 ahora generan C y
74 todavía fallan. Esta prueba no repite el descubrimiento ni verifica todos
sus destinos; no reemplaza el build completo. Se inició otra traducción
estricta con estos cambios. El estado vigente está en `build/web-status.json`.

Ese intento completo terminó con 74 funciones fallidas y 468 sitios de
dispatch pendientes: 360 destinos únicos, con 280 sitios fuera de la imagen.
Se conserva en `build/strict-loop-segments.log` y
`build/strict-loop-segments-blockers.json`.
La reducción de funciones fallidas no implica que el motor pueda enlazarse;
el descubrimiento de más código también expone más destinos pendientes.

La entrada vacía de `0x00407800` se reparó con sus 20 bytes originales y un
caller directo verificado. También se añadieron dos instrucciones INT3
originales después de llamadas a ExitProcess en `0x008248ed` y `0x0082b3c3`.
`analysis/curated-core-followup` verifica estas tres reparaciones junto a
los 1.683 wrappers y 52 comprobaciones de propiedad de fragmentos. El nuevo
intento completo usa ese directorio; no representa aún un motor compilado.

ENTER de 32 bits ahora conserva la construcción de la pila, las copias de
marcos anidados y el nivel de anidamiento módulo 32, sin alterar banderas.
`verify_enter_wasm.py` compara 960 ejecuciones x86/Wasm de 64 formas, incluyendo
alias de pila, cruces de 64 KiB, tamaños de reserva y prefijo de dirección.
Coinciden registros, banderas, PC y los 128 bytes que puede escribir ENTER.
El operando de 16 bits se rechaza: el oráculo x86 discrepa en su semántica de
BP al cruzar 64 KiB y requiere una referencia adicional antes de admitirlo.
Son pruebas sintéticas sin fallos de memoria, no ejecución del motor.
Tres de los 74 cuerpos anteriores ahora generan C; los otros 71 siguen
fallando en la prueba individual, que no valida el enlace ni repite discovery.
El proceso completo iniciado antes de este cambio ENTER terminó con 74
funciones fallidas y 464 sitios pendientes (357 destinos únicos). Las tres
reparaciones de entradas resolvieron cuatro sitios de dispatch. El registro
y el informe se conservan en `build/strict-core-followup-before-enter.log`
y `build/strict-core-followup-before-enter-blockers.json`.

`audit_core_data.py` verifica que `0x00859b88..0x00859b94` son tres constantes
float originales en .rdata no ejecutable y de solo lectura: 0,0078125, 0,5 y 4.
Comprueba la identidad del EXE, los 12 bytes y sus lecturas x87 originales,
y rechaza transferencias directas hacia el rango encontradas en los listados.
El export las había convertido en una función con AAS; se declaran datos
conservando todos sus bytes para las operaciones matemáticas del juego.
`analysis/curated-core-enter` contiene esta clasificación y las reparaciones
previas; su verificador repite las comprobaciones de procedencia. La nueva
traducción completa usa ENTER y estos datos corregidos. El estado vigente
está en `build/web-status.json`; todavía no hay motor enlazado ni jugable.

## Introducción original local

```powershell
.venv/Scripts/python.exe prepare_intro.py
.venv/Scripts/python.exe serve_intro.py --port 8765
```

Abrir `http://127.0.0.1:8765/`. Reproduce Logo.mpg y GTAtitles.mpg de la
instalación en copias MP4 locales, con su audio y sin modificar las fuentes.
El servidor solo expone esa página, ambos vídeos y el estado resumido del
build. Se verificaron respuestas HTTP, rangos de vídeo y decodificación de
los MP4; el usuario confirmó la reproducción. Esta vista no ejecuta el
motor ni el menú y no demuestra que el port sea jugable.

## Trabajo paralelo verificado

La auditor?a de las entradas `0150a062` y `0150c2c2` se conserva en
`analysis/problematic-entry-audit.json`. Los bytes de salto que parecen
referenciarlas se leen como DWORDs de datos por el dispatcher en cuatro
recorridos originales, pero no hay prueba global de inalcanzabilidad y las
entradas se conservan. `analysis/dispatcher-coverage.json` registra siete
destinos indirectos ejecutados por el c?digo original y ausentes de todos
los listados activos; sus candidatos emiten C despu?s de normalizar SAL.
Las formas originales `/6` se compararon con SHL `/4` en Windows x86 real:
336 pares, 672 instrucciones; resultados y flags definidos coincidentes
(`build/sal-native-reference.json`). Los estados de esos recorridos son
sint?ticos y no prueban un arranque completo.

La etapa de reescritura de destinos retirados evita regex cuando falta su
prefijo literal. En 14 cuerpos originales, mediana 26,277 ms a 2,482 ms,
con salida id?ntica (`build/perf-retarget-withdrawn.json`). Ambos benchmarks
de optimizaci?n son de etapas concretas; falta medir el intento completo.

`tools/d3d9_bridge/guest_vertex.h` aporta decodificaci?n del ABI COM32, FVF y
copia acotada de v?rtices. Sus 387 comprobaciones pasan en Windows x86 y
Wasm, incluidos tama?os/slots del SDK y los bytes originales del FVF 0x252.
El resultado est? en `build/d3d9-bridge-vertex-status.json`. Todav?a no
registra Direct3DCreate9 ni dibuja el juego.
