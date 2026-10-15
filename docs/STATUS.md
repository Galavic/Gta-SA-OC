# Estado actual

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

Estado 2026-10-14: 0 fallidas, 9 dangling tras olvidar 3 huerfanos mas (97 forget total): 00d52a60→00d52a85, 00d53b90→01eaf735, 00d55360→00d553bd (x2), 012907c0→16ed3fc0, 01297d80→01297dd8. Fase 1 COMPLETA (traduccion estricta en verde). Fase 2 COMPLETA (wasm publicado, V8 OK). Fase 3 en curso: el arranque estricto del 2026-10-14 llegaba a ExitProcess(0) tras el mensaje de DirectX 9 (DirectDrawCreateEx devolvia DDERR_UNSUPPORTED siempre). Implementado IDirectDraw7 minimo (vtable v4 + StartModeTest/EvaluateMode con nombre, CreateEx real, registro com_define/bind/iid). Siguiente arranque estricto: pasar del check DX (FUN_00745650 busca 0x900) hacia D3D9.

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
