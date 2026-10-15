<p align="center">
  <img src="logo-mejorado/kreix-logotipo-claro.png" alt="Kreix" width="420">
</p>

<p align="center">
  Finanzas personales y cartera de inversión, 100 % offline.<br>
  Importa tus extractos de <b>Imagin</b> y <b>MyInvestor</b> y ve tu patrimonio, tu ahorro y tu rentabilidad en un solo sitio.
</p>

<p align="center">
  <img src="docs/screenshots/resumen-oscuro.png" alt="Resumen en modo oscuro" width="49%">
  <img src="docs/screenshots/resumen-claro.png" alt="Resumen en modo claro" width="49%">
</p>

> Las capturas usan datos de demostración inventados (`tools/demo_data.py`).

## Qué hace

- **Importa extractos arrastrándolos a la ventana.** Kreix detecta el banco y el tipo de archivo por las cabeceras, no por el nombre ni la extensión, y **te enseña lo que ha leído antes de guardar nada**: cuántos movimientos, de qué fechas, cuántos son nuevos y cuántos ya estaban.
- **Pensado para no perderse:** una guía de tres pasos la primera vez, datos de ejemplo para explorar sin importar nada, una lista de primeros pasos en el Resumen, una frase bajo cada gráfico que dice lo que cuenta y errores que explican qué hacer.
- **Todo se confirma y se puede deshacer:** cada cambio importante avisa con un mensaje breve y un botón **Deshacer** (importar, categorías, reglas, presupuestos, borrados...).
- **Búsqueda en todo (`Ctrl+K`):** páginas, acciones, movimientos y explicaciones de la ayuda.
- **Nunca duplica movimientos.** Puedes reimportar el mismo extracto, o varios que se solapan, y solo se añade lo nuevo. Dos pagos idénticos el mismo día se distinguen por el saldo posterior.
- **Categoriza los gastos** con reglas por palabras clave (supermercado, suscripciones, ocio, restaurantes, transporte, vivienda, salud, Bizum...) y **tú mandas**: cambia la categoría de un movimiento con clic derecho o crea tus propias reglas.
- **Presupuestos por categoría:** fija un tope mensual y mira cuánto llevas gastado; el Resumen avisa de los que estás a punto de superar o ya has superado.
- **Pagos recurrentes:** detecta tus suscripciones y recibos mensuales, te dice cuánto suman al mes y al año y cuándo toca el siguiente.
- **Comparación con el mes anterior** en ingresos y gastos.
- **Calcula las métricas que importan:** patrimonio neto, rendimiento global, tasa de ahorro, TIR y TWR.
- **Una pestaña para tus cuentas y otra para tu inversión**, cada una con sus métricas, sus gráficos y todos sus movimientos, para un mes concreto o para todo el historial (ver más abajo).
- **Varias cuentas bancarias:** añade, renombra o elimina cuentas, y mira una sola o todas a la vez.
- **Avisa de lo que no cuadra** en vez de importar en silencio: saldos con huecos, cartera que no coincide con las operaciones, importes incoherentes.
- **Modo claro y oscuro** intercambiables en caliente (`Ctrl+T`), con la paleta amarilla y roja de la marca.
- **Fluido con muchos datos:** los movimientos se ordenan, filtran y cargan en una fracción de segundo incluso con decenas de miles de filas, solo se recalcula la página que estás viendo y la ventana recuerda su tamaño y la última página.
- **Privado por diseño:** todo se procesa y se guarda en tu equipo. No hay red, cuentas ni telemetría.

## Las pestañas

Arriba a la izquierda están las tres vistas de tus datos; abajo, en forma de píldora con icono, las herramientas (de arriba abajo: Importar, Exportar, Ajustes y Ayuda), y debajo el conmutador de modo claro y oscuro (un sol y una luna).

| Pestaña | Para qué sirve |
|---|---|
| **Resumen** | Patrimonio neto, rendimiento global y tasa de ahorro del mes; los próximos pagos recurrentes y los presupuestos del mes en riesgo; la distribución de activos y la evolución patrimonial. |
| **Cuentas** | Todo lo de tus cuentas bancarias: saldo, ingresos, gastos, tasa de ahorro, gasto medio, mayor gasto y categoría principal; gastos por categoría, evolución del saldo, ingresos y gastos por mes; presupuestos, pagos recurrentes y la tabla de movimientos. |
| **Inversiones** | Todo lo de tu cartera: valor, aportado, plusvalía, rentabilidad (TWR y TIR), distribución por fondo, aportado frente a valor, posiciones actuales y operaciones. |
| **Importar** | Arrastra extractos y elige a qué cuenta pertenecen. También restaura un archivo `.kreix`. |
| **Exportar** | Guarda todos tus datos en un único archivo `.kreix` para hacer una copia o llevarlos a otro ordenador. |
| **Ajustes** | Qué cuenta como ingreso, tus reglas de categorías, borrar datos, ruta de la base de datos. |
| **Ayuda** | Qué significa cada cifra y cada gráfico, explicado sin tecnicismos y con ejemplos. |

Atajos: `Ctrl+1` a `Ctrl+7` cambian de página en el orden de la tabla, `Ctrl+K` busca en todo, `Ctrl+T` alterna el modo claro y oscuro, `Ctrl+F` va al buscador de movimientos y `F5` recalcula la página.

<p align="center">
  <img src="docs/screenshots/bienvenida-oscuro.png" alt="Pantalla de bienvenida" width="49%">
  <img src="docs/screenshots/importar-oscuro.png" alt="Vista previa de la importación" width="49%">
</p>

**La primera vez.** Con la app vacía, la pantalla de inicio explica en tres pasos qué descargar y dónde soltarlo, y ofrece **Probar con datos de ejemplo**: datos inventados con un aviso arriba y un botón *Empezar con mis datos*. Se quitan solos al importar tus extractos reales, así que nunca se mezclan con los tuyos. Con datos ya cargados, el Resumen muestra una lista de **primeros pasos** (importar la cuenta, las operaciones, la cartera, definir un presupuesto) que puedes ocultar.

**Revisar antes de importar.** Al soltar archivos, Kreix muestra una tarjeta por archivo (tipo, número de filas, fechas, nuevas, ya importadas y, en la cartera, las que se actualizan) y espera a que pulses *Importar*. Si un archivo no se puede leer, explica el motivo y qué hacer (por ejemplo, descargarlo otra vez en CSV o Excel sin editarlo). Un archivo `.kreix` se restaura directamente, con su propia confirmación.

**Avisos y Deshacer.** Tras cada cambio importante aparece un aviso abajo. Mientras siga a la vista, *Deshacer* devuelve los datos exactamente a como estaban: antes de cada cambio Kreix guarda una copia de la base de datos. Solo se deshace el último cambio.

**Ayuda.** Un menú de seis temas (Tu dinero de un vistazo, Tus cuentas bancarias, Tus inversiones, Rentabilidad, Avisos y Usar Kreix); cada botón abre su sección y una flecha vuelve al menú. Es un glosario para quien no sabe de finanzas: patrimonio neto, tasa de ahorro, valor liquidativo, plusvalía, TWR, TIR y el resto de términos que muestra Kreix. Cada uno explica qué es, cómo lo calcula Kreix y da un ejemplo con números. Buscar "tir" encuentra la TIR, pero no "invertir".

**Exportar y mover tus datos.** *Exportar* crea un archivo `.kreix` (un ZIP con una copia consistente de la base de datos y una ficha con la versión y los totales). Para llevarlo a otro ordenador, instala Kreix allí, ve a *Importar* y arrastra el archivo: los datos quedan idénticos a los de origen (cuentas, movimientos, categorías, operaciones, cartera y ajustes, incluida la protección anti-duplicados). Importar un `.kreix` **reemplaza** los datos que hubiera en ese ordenador, y pide confirmación si ya había datos. Un archivo recibido se trata como no fiable: solo se aceptan sus dos entradas, se comprueba la integridad de la base de datos y se rechaza si trae disparadores o vistas, si es de una versión más reciente o si es demasiado grande. **El archivo no está cifrado**: contiene tu información financiera, guárdalo en un sitio seguro.

<p align="center">
  <img src="docs/screenshots/cuentas-oscuro.png" alt="Pestaña Cuentas" width="49%">
  <img src="docs/screenshots/inversion-claro.png" alt="Pestaña Inversiones" width="49%">
</p>

<p align="center">
  <img src="docs/screenshots/ayuda-oscuro.png" alt="Página de Ayuda" width="49%">
  <img src="docs/screenshots/exportar-claro.png" alt="Página de Exportar" width="49%">
</p>

**Por mes o en global.** En Cuentas e Inversión, el selector de arriba cambia entre "Todo el historial" y cada mes con datos (las flechas saltan al mes anterior o siguiente). Las métricas, los gráficos y las tablas se ajustan al periodo elegido:

- En Cuentas, el saldo es el **saldo al cierre** del mes y la media de gasto pasa de mensual a diaria.
- En Inversión, el mes muestra el valor estimado al cierre, lo aportado en el mes, la variación sin contar aportaciones y la rentabilidad del mes.

**Acciones visibles.** Cada movimiento tiene un botón **•••** (también doble clic o clic derecho) para cambiar su categoría, crear una regla o copiar el concepto. Pulsar una categoría en el gráfico de gastos, o un presupuesto, filtra la tabla con esos movimientos.

**Movimientos.** La tabla de Cuentas ordena los movimientos del más reciente al más antiguo y, dentro de un mismo día, en su orden real (se reconstruye con la cadena de saldos). Se puede buscar por concepto, filtrar por categoría y ordenar pulsando cualquier cabecera. Con varias cuentas aparece una columna "Cuenta".

**Categorías a tu gusto.** Con ••• (o clic derecho) sobre un movimiento: *Cambiar categoría* (tu elección no la pisa ninguna regla), *Volver a la categoría automática* o *Crear regla para…*, que lleva a una categoría todos los conceptos con esa palabra, también los que importes después. Tus reglas mandan sobre las que trae Kreix y se gestionan en **Ajustes > Reglas de categorías**.

**Presupuestos.** En Cuentas, el panel *Presupuestos* (botón *Definir presupuestos*) fija un tope mensual por categoría. La barra se pone verde mientras te sobra, amarilla al pasar del 85 % y roja al superarlo. Con un mes elegido compara el gasto de ese mes; con todo el historial, el gasto medio mensual.

**Pagos recurrentes.** Un cargo cuenta como recurrente si se repite al menos tres meses seguidos, cada unos 30 días y con un importe estable (hasta un 20 % de diferencia); si deja de aparecer durante mes y medio se da por cancelado. El supermercado no entra: varía de importe y se repite más de una vez al mes. Los traspasos, Bizum e ingresos nunca cuentan.

**Exportar movimientos.** El botón *Exportar* de la tabla guarda en CSV (UTF-8, separado por `;`, coma decimal) o Excel (importes como números) las filas que se ven, con el filtro y el orden actuales. No exporta a PDF.

**Varias cuentas.** En Cuentas, **Gestionar cuentas** permite añadir, renombrar y eliminar cuentas. En Importar eliges la cuenta de destino de cada extracto de Imagin. El mismo extracto importado en dos cuentas distintas no cuenta como duplicado. La cartera de inversión es una sola.

## Qué archivos acepta

| Origen | Archivo | Cabeceras que reconoce |
|---|---|---|
| Imagin | Extracto de movimientos (CSV o Excel) | `Concepto; Fecha; Importe; Saldo` |
| MyInvestor | Operaciones (CSV o Excel) | `Fecha Operación; ...; ISIN; Tipo Operación; Participaciones; ...` |
| MyInvestor | Cartera (CSV o Excel) | `Producto; ISIN; Participaciones Totales; ...; Valor Liquidativo Actual` |

- Admite CSV con `;`, `,` o tabulador, en UTF-8 o Windows-1252, y Excel con títulos antes de la tabla.
- **No importa la extensión:** archivos como `extractImagin` (sin extensión) o `.csv.txt` funcionan igual, porque el tipo se detecta por las cabeceras.
- Los importes en formato español (`-2,99EUR`, `1.234,56 €`) se limpian automáticamente.
- **Solo CSV y Excel:** Kreix no importa PDF. Descarga el extracto en uno de esos dos formatos desde tu banco.
- El extracto de cartera de MyInvestor no incluye fecha, así que Kreix te pide a qué día corresponde.

## Instalación y ejecución

Requiere Python 3.11 o superior (desarrollado y probado con 3.14). Es ligero: solo `PySide6-Essentials`, `SQLAlchemy` y `openpyxl` (unos 215 MB en total) y arranca en alrededor de un segundo.

**En Windows, lo más fácil:** haz doble clic en `Kreix.bat`. La primera vez crea el entorno e instala lo necesario; después abre la aplicación directamente.

**A mano:**

```powershell
git clone https://github.com/dasuarezang/kreix.git
cd kreix
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

En macOS o Linux usa `.venv/bin/python` en lugar de `.venv\Scripts\python`. Para desarrollar (tests, generar capturas y fuentes) instala `requirements-dev.txt`.

Si importaste algo mal, **Ajustes > Borrar todos los datos** deja la base de datos vacía (los ajustes se conservan) para volver a empezar.

Los datos se guardan en `%APPDATA%\Kreix\kreix.db` (Windows), `~/Library/Application Support/Kreix/` (macOS) o `~/.local/share/Kreix/` (Linux). Para probar sin tocar tus datos:

```powershell
.venv\Scripts\python tools\demo_data.py demo          # genera extractos inventados en .\demo
.venv\Scripts\python main.py --db prueba.db           # usa una base de datos aparte
```

## Cómo se calculan las cifras

| Métrica | Definición |
|---|---|
| **Patrimonio neto** | Saldo de Imagin + valor de mercado de la última foto de cartera de cada fondo. |
| **Rendimiento global** | (valor de mercado - capital invertido) / capital invertido, según el extracto de cartera. |
| **Tasa de ahorro** | (ingresos - gastos) / ingresos del mes. Puede ser negativa. |
| **TIR** | Tasa interna de retorno anualizada con fechas irregulares (XIRR, base 365 días). |
| **TWR** | Rentabilidad ponderada en el tiempo: encadena los tramos entre aportaciones, así que el momento de aportar no la afecta. |

**Qué cuenta como ingreso o gasto**

- Los traspasos entre cuentas propias que **entran** cuentan como ingreso; los que salen son neutros. Es una opción en Ajustes.
- Los Bizum cuentan como ingreso o gasto. También es una opción en Ajustes.
- Las aportaciones a MyInvestor no son gasto: se calculan desde las compras de MyInvestor, para no contarlas dos veces.

**Fiabilidad.** La TIR y el TWR se reconstruyen desde el historial de operaciones. Si falta alguna, la cartera no cuadra con las operaciones: Kreix lo avisa y **oculta la TIR y el TWR** hasta que se corrija, en lugar de enseñar cifras engañosas. Exporta el historial completo desde el inicio.

## Arquitectura

Clean Architecture: las dependencias apuntan hacia el dominio, y `core` no sabe nada de la interfaz, de la base de datos ni de bibliotecas pesadas.

```
main.py                 ensambla las capas y arranca la interfaz
ui/                     PySide6: ventana, vistas, gráficos, tema claro/oscuro
services/               casos de uso: importar, resumen, cuentas, inversión, categorías y presupuestos,
                        ajustes, exportar movimientos, exportar/restaurar
etl/                    lectores de CSV/Excel y parsers (Imagin, MyInvestor), cuadre
data/                   modelos SQLAlchemy, repositorios idempotentes y migraciones
core/                   lógica pura: métricas (generales, por cuenta y de inversión),
                        periodos, categorizador, pagos recurrentes, presupuestos, entidades, enumeraciones
logo-mejorado/          logotipos e iconos de la marca
assets/fonts/           tipografías incluidas (Montserrat y DM Sans, licencia OFL)
tools/                  capturas, generador de fuentes y atajo para los datos de demostración
                        (la lógica de los datos de ejemplo vive en services/demo_data.py)
tests/                  suite de pruebas
```

Decisiones de diseño relevantes:

- **Dinero exacto.** Los importes se guardan como enteros escalados (x10⁶) mediante un tipo propio, `Decimal6`. No hay errores de coma flotante y `SUM()` sigue funcionando en SQL.
- **Idempotencia.** Cada movimiento tiene un `tx_hash` único (que incluye la cuenta) y se inserta con `ON CONFLICT DO NOTHING`. Las bases de datos anteriores se migran solas al abrir (`PRAGMA user_version`).
- **Preparado para cifrar.** El motor se crea en un único punto (`make_engine`), así que cambiar a una base cifrada (SQLCipher) no toca el resto del código.
- **Fluidez.** Las tablas ordenan en el propio modelo (claves precalculadas y `list.sort`), no con el orden de Qt: 20 000 movimientos se ordenan en menos de medio segundo en lugar de cuatro. Las series de patrimonio ordenan una sola vez los saldos por cuenta y buscan por bisección, y solo se recalcula la página visible.
- **Gráficos propios**, pintados con QPainter (barras redondeadas con degradado, curvas suaves, donut con leyenda e importes), con animación de entrada y tarjeta de detalle al pasar el ratón. Se adaptan al tema activo.

## Diseño

- **Tipografía:** Montserrat ExtraBold (la del logotipo) para títulos y cifras grandes, y DM Sans para el texto. Los archivos van dentro del programa, así que se ve igual en cualquier ordenador. Ambas son libres (SIL Open Font License); las licencias están en `assets/fonts/LICENCIAS.txt`.
- **Color:** el amarillo y el rojo del logotipo sobre carbón (modo oscuro) o papel cálido (modo claro). El amarillo se reserva para lo importante, el verde marca lo positivo y el rojo lo negativo.
- **Motivo de marca:** las tres franjas inclinadas de la K del logotipo aparecen en las cabeceras y en la zona de importación.
- **Estructura:** una cifra principal grande en el Resumen y bandas de cifras en Cuentas e Inversiones, en lugar de muchas cajas iguales.

## Desarrollo

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q          # toda la suite
.venv\Scripts\python tools\screenshots.py  # regenera las capturas del README
```

Los tests de interfaz usan Qt sin pantalla (`QT_QPA_PLATFORM=offscreen`) y simulan el arrastre de archivos. Las pruebas del ETL y de los servicios usan archivos de ejemplo inventados en `tests/fixtures/`.

## Hoja de ruta

- Migraciones de base de datos con Alembic.
- Cifrado de la base de datos y del archivo `.kreix` exportado.
- Empaquetado como ejecutable (`.exe` / `.app`).
- Iconos «?» junto a cada cifra que abran su explicación en la Ayuda.

## Privacidad

Los extractos bancarios son datos sensibles, y el archivo `.kreix` exportado también (no está cifrado). El repositorio ignora por defecto las bases de datos (`*.db`) y la carpeta `ejemplos/`. No subas extractos reales al control de versiones.

## Licencia

Proyecto privado. Todos los derechos reservados.
