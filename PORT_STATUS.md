# Estado actual del port de GTA SA

Instalacion seleccionada por el usuario:
<local-game-install>.

## Variante activa en preparacion

El ejecutable analizado se copio desde patch_1.dat sin modificar bytes a
variants/singleplayer/prepared/gta_sa.exe. Actualmente el mismo hash esta
en el gta_sa.exe instalado; la comprobacion actual esta en
variants/singleplayer/original-engine-acceptance.json.
SHA-256: a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26.
Entrada original: 00824570. No se ejecuto el programa nativo instalado.
Durante la preparacion anterior, gta_sa.exe identificaba Git LFS 2.13.3.
La ubicacion actual cambio, pero el hash del GTA preparado sigue coincidiendo.
La carpeta contiene cargadores adicionales; no se afirma que sea
una distribucion retail sin modificaciones.

La preparacion excluye SA-MP, DINPUT8.DLL, scripts, patch_0.dat y el cargador
vorbisFile.dll instalado. La biblioteca de audio original alojada como
vorbisHooked.dll coincide con la version original previamente verificada.
Las cuatro bibliotecas preparadas de audio se reutilizan con hashes exactos.
Se enlazaron anim, audio, data, models, movies y text desde la carpeta elegida.
No se modifico ningun archivo instalado ni se borro el port anterior.

## Analisis y traduccion

prepare_singleplayer.py preparo y valido una configuracion aislada.
Ghidra termino: 20.823 funciones y 1.230.152 instrucciones exportadas.
Se retomo la traduccion del motor original tras descartar la reconstruccion
de recursos como solucion 1:1. resume_singleplayer.py --background reutiliza
ese analisis, registra el resultado estricto y conserva los bloqueos.
No vuelve a ejecutar Ghidra ni permite omitir instrucciones.
Estado: variants/singleplayer/analysis-status.json.
Log activo: variants/singleplayer/translation-resume.log.
Preparacion e identidades: variants/singleplayer/preparation.json.
Esta variante no tiene todavia un Wasm compilado ni jugabilidad verificada.

La primera pasada completa se detuvo en cuatro tablas sin destinos. La
auditoria posterior verifico que las cuatro estan dentro de cinco archivos
PE almacenados como recursos: sus tablas son validas en sus propias imagenes,
no en las direcciones del EXE principal. Se declararon sus buffers como datos
conservando todos los bytes. La entrada principal queda fuera y no se hallaron
transferencias directas desde los listings externos hacia esos buffers.
Auditoria: variants/singleplayer/embedded-images-audit.json.
Clasificacion: variants/singleplayer/embedded-data-regions.json.
La nueva pasada estricta usa esta clasificacion. Si se invoca un programa
almacenado, debe cargarse y reubicarse por separado; eso sigue sin comprobarse.

## Criterios de comprobacion

La carga de modelos no demuestra equivalencia con GTA SA. Deben comprobarse
el arranque estricto del ejecutable actual, menu original, intro/cinematica,
primera mision original, animaciones, conduccion y fisica del motor original,
audio, entrada y guardado. Ninguno se marca verificado en esta variante.
La demo de gtasa-web-rebuild permanece separada y no es un port 1:1.

## Trabajo conservado

El runtime, traductor, D3D9, entrada, audio y herramientas permanecen en
vendor/recomp-kit. El port anterior sigue bajo build y analysis, con su
EXE preparado y sus configuraciones intactos. Su Wasm corresponde a otro
hash de ejecutable y no debe combinarse con el nuevo EXE.
Las rondas antiguas se detuvieron con needs_review; no hay un supervisor
antiguo traduciendo en paralelo la version descartada.

El servidor local http://127.0.0.1:8766/ reconoce los recursos actuales y
rechaza la importacion automatica cuando el EXE no coincide con el Wasm
publicado. Se conserva el importador; no se presenta esa pagina como juego
funcional de la nueva version.
