# Descarga bajo demanda del port web

El importador anterior divide las transferencias en bloques, pero espera a
completar la instalacion antes de escribir `.stamp` y permitir el arranque.
La nueva ruta separa la preparacion del ejecutable/DLL de las lecturas del juego.
No cambia el codigo original de streaming de GTA ni elimina archivos del inventario.

1. El launcher descarga y verifica el ejecutable y las DLL compatibles.
2. Guarda un descriptor `.streaming.json`, el inventario y la lista del montaje.
   No escribe el sello de instalacion completa para una descarga parcial.
3. El runtime monta los nombres de los archivos con WasmFS en `/stream-game`.
   Los archivos ya importados completos siguen apuntando a su copia local.
4. Las lecturas del juego solicitan solo los bloques que cubren sus offsets,
   incluso cuando un IMG esta dividido en varios objetos alojados.
5. Se comprueban HTTP 206, Content-Range, longitud y SHA256 antes de entregar
   datos al motor. Los errores producen EIO; no se sustituyen por ceros.

Los archivos que ya estaban importados completos siguen siendo locales.
Tambien se pueden reutilizar bloques de una importacion anterior interrumpida:
el journal debe corresponder al mismo build y cada bloque se vuelve a comprobar
contra su SHA256 antes de usarlo. Los huecos y los bloques sin verificar se
solicitan a la red.

Las peticiones y las lecturas persistentes ocurren en un worker de WasmFS.
La cache en memoria mantiene hasta 32 MiB y las descargas simultaneas se limitan
a cuatro. La cache persistente conserva bloques verificados con un limite
conservador de 256 entradas de hasta 4 MiB, aproximadamente 1 GiB; el navegador
puede desalojarlos. Si el almacenamiento falla, se usa la memoria y la red.
No se descarga todo el inventario en segundo plano. La partida espera cuando
necesita datos que aun no estan disponibles; no se garantiza una mejora de FPS.
El player muestra un aviso discreto durante esperas de descarga prolongadas.

## Probar una compilacion separada

El runtime debe recompilarse con los cambios de `patches/current-vendor.patch`.
Incluye el montaje C++ y `host/sdl/library_demand_files.js`. Un runtime anterior
no admite una instalacion parcial. Las herramientas comprueban sus marcadores
antes de activar esta modalidad; la seleccion permanece explicita.

Con un sitio candidato que contiene los tres archivos compilados del runtime
y `games.json`, se puede usar la copia preparada local como servidor de rangos:

```powershell
.venv/Scripts/python.exe tools/serve_variant.py --port 8788 --site build/demand-files/site --demand-manifest build/game-assets/<game-build>/game-assets.fast.json
```

El servidor conserva los offsets de los objetos alojados sin copiar los IMG.
El sitio y los logs de esta prueba quedan separados del sitio habitual.
La identidad y los resultados de la prueba actual estan en `docs/STATUS.md`.

## Preparar una publicacion

```powershell
.venv/Scripts/python.exe tools/prepare_cloudflare.py --output build/cloudflare-demand-candidate --site build/demand-files/site --game-manifest build/game-assets/<game-build>/game-assets.fast.json --demand-files
```

Se utiliza el inventario existente de bloques de 4 MiB. En el mismo bucket no
requiere volver a subir los objetos del juego; al cambiar de cuenta hay que
copiarlos al almacenamiento de destino. El registro de subida debe quedar
separado por cuenta y bucket para no confundir objetos ya presentes en el origen. La publicacion debe incluir el nuevo Wasm/JS,
el player y los modulos del importador. `--site` selecciona el candidato validado
sin sustituir el sitio local habitual.
Preparar un directorio no lo publica ni modifica el despliegue activo.

El empaquetador tambien genera variantes gzip reproducibles del Wasm y del
paquete de recursos. Se suben los cuatro objetos del manifiesto del runtime.
El Worker negocia gzip con el navegador y conserva el MIME original; si falta
la variante comprimida puede usar la original. Los rangos de los archivos del
juego conservan sus bytes y hashes originales, sin comprimir esos objetos.

El Wasm y el paquete de recursos del motor siguen siendo una descarga inicial
independiente. Deben medirse por separado de los archivos originales del juego.
La verificacion con servidor local no mide latencia real de Internet ni prueba
misiones completas, sesiones largas o un recorrido por toda la ciudad.

## Comprobaciones reproducibles

```powershell
node --test tools/tests/demand-files.test.mjs tools/web/launcher/hosted-import.test.mjs
.venv/Scripts/python.exe -m pytest -q tests tools/tests
```

Cubren offsets, limites de objetos, EOF, identidad, reanudacion, cache,
concurrencia, datos corruptos, fallos de red y el servidor local de rangos.
Son pruebas de infraestructura; la evidencia del juego en navegador se registra
por separado y con el hash del artefacto ejecutado.
