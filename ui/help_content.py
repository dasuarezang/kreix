"""Contenido de la pagina de Ayuda: que significa cada cifra que muestra Kreix.

Texto pensado para quien no sabe de finanzas. Cada entrada explica el concepto con palabras
sencillas, dice como lo calcula Kreix y da un ejemplo con numeros. Sin dependencias de Qt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core import i18n
from core.i18n import N_
from core.categorizer import normalize


@dataclass(frozen=True, slots=True)
class HelpEntry:
    section: str
    term: str
    plain: str                          # que es, con palabras sencillas
    how: str = ""                       # como lo calcula Kreix
    example: str = ""
    note: str = ""                      # advertencia o matiz importante ("Ojo")
    todo: str = ""                      # que hacer si aparece un aviso
    keywords: tuple[str, ...] = ()      # sinonimos para el buscador


S_OVERVIEW = N_("Tu dinero de un vistazo")
S_ACCOUNTS = N_("Tus cuentas bancarias")
S_INVEST = N_("Tus inversiones")
S_RETURNS = N_("Rentabilidad: ¿cuánto he ganado?")
S_WARNINGS = N_("Avisos")
S_USE = N_("Usar Kreix")
SECTIONS = (S_OVERVIEW, S_ACCOUNTS, S_INVEST, S_RETURNS, S_WARNINGS, S_USE)

# icono (de ui.icons) y descripcion corta de cada seccion, para los botones del menu de ayuda
SECTION_INFO: dict[str, tuple[str, str]] = {
    S_OVERVIEW: ("pie", N_("Patrimonio, liquidez e inversión")),
    S_ACCOUNTS: ("card", N_("Saldo, ingresos, gastos y ahorro")),
    S_INVEST: ("trend", N_("Fondos, participaciones y aportaciones")),
    S_RETURNS: ("percent", N_("Plusvalía, TWR y TIR")),
    S_WARNINGS: ("alert", N_("Qué significan y qué hacer")),
    S_USE: ("book", N_("Importar, exportar y atajos")),
}

ENTRIES: tuple[HelpEntry, ...] = (
    # ------------------------------------------------------------------ Tu dinero de un vistazo
    HelpEntry(
        S_OVERVIEW, "Patrimonio neto",
        "Todo lo que tienes ahora mismo: el dinero que hay en tus cuentas más lo que valen tus inversiones. "
        "Es la cifra más importante para saber si tu situación económica mejora con el tiempo.",
        "Saldo de tus cuentas + valor de mercado actual de tu cartera. Kreix no registra deudas ni préstamos, "
        "así que no se restan.",
        "Tienes 1.000 € en la cuenta y 4.000 € en fondos: tu patrimonio neto es de 5.000 €.",
        keywords=("saldo total", "net worth", "patrimonio"),
    ),
    HelpEntry(
        S_OVERVIEW, "Liquidez",
        "El dinero que puedes usar ya, sin tener que vender nada: lo que hay en tus cuentas bancarias.",
        "Suma del saldo de todas tus cuentas.",
        "",
        keywords=("efectivo", "dinero disponible"),
    ),
    HelpEntry(
        S_OVERVIEW, "Inversión (cartera)",
        "El dinero que has puesto en fondos. Su valor sube y baja cada día según el mercado.",
        "Valor de mercado de tus fondos según el último extracto de cartera importado.",
        "",
        keywords=("cartera", "fondos"),
    ),
    HelpEntry(
        S_OVERVIEW, "Distribución de activos",
        "Cómo se reparte tu patrimonio entre dinero en cuenta (liquidez) y dinero invertido. "
        "Sirve para ver de un vistazo si tienes mucho dinero parado o muy poco colchón.",
        "Cada parte dividida entre el patrimonio neto.",
        "1.000 € en cuenta y 4.000 € invertidos: 20 % liquidez y 80 % inversión.",
        keywords=("donut", "reparto"),
    ),
    HelpEntry(
        S_OVERVIEW, "Evolución patrimonial",
        "Cómo ha cambiado tu patrimonio mes a mes. Se ven tres líneas: lo que has aportado, lo que vale tu cartera "
        "y tu patrimonio neto total. Cuando la cartera va por encima de lo aportado, la diferencia es lo que "
        "ha ganado tu inversión.",
        "Al final de cada mes: saldo de las cuentas + valor estimado de la cartera.",
        "",
        keywords=("gráfico", "grafico", "línea"),
    ),

    # ------------------------------------------------------------------ Tus cuentas bancarias
    HelpEntry(
        S_ACCOUNTS, "Saldo",
        "El dinero que hay en la cuenta. Si miras un mes concreto, es el saldo al cierre de ese mes: lo que "
        "quedaba tras el último movimiento.",
        "El saldo que indica el banco tras cada movimiento. Con varias cuentas se suman, cada una con su propio saldo.",
        "",
        keywords=("saldo al cierre",),
    ),
    HelpEntry(
        S_ACCOUNTS, "Ingresos",
        "El dinero que entra en tus cuentas: nómina, becas, transferencias recibidas...",
        "Suma de los movimientos positivos. Los Bizum recibidos y los traspasos entrantes cuentan si lo tienes "
        "activado en Ajustes. Lo que mueves hacia tus inversiones nunca cuenta como ingreso ni como gasto.",
        "",
        keywords=("entradas",),
    ),
    HelpEntry(
        S_ACCOUNTS, "Gastos",
        "El dinero que sale de tus cuentas: compras, suscripciones, recibos...",
        "Suma de los movimientos negativos, mostrada en positivo. Mover dinero entre tus propias cuentas o hacia "
        "tus inversiones no es gastarlo, así que no se cuenta.",
        "",
        keywords=("salidas",),
    ),
    HelpEntry(
        S_ACCOUNTS, "Flujo neto",
        "Lo que te ha sobrado (o te ha faltado) en un periodo. Si es positivo, has ingresado más de lo que has gastado.",
        "Ingresos - gastos.",
        "Ingresas 1.000 € y gastas 700 €: flujo neto de +300 €.",
        keywords=("ahorro neto",),
    ),
    HelpEntry(
        S_ACCOUNTS, "Tasa de ahorro",
        "El porcentaje de lo que ingresas que consigues no gastar. Cuanto más alta, más margen tienes para ahorrar o invertir.",
        "(ingresos - gastos) ÷ ingresos. Puede ser negativa si gastas más de lo que ingresas.",
        "Ingresas 1.000 € y gastas 700 €: ahorras 300 €, una tasa del 30 %. Si gastas 1.200 €, la tasa es del -20 %.",
        keywords=("ahorro", "porcentaje de ahorro"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Previsión a fin de mes",
        "Cuánto dinero tendrás en tus cuentas el último día del mes si todo sigue como hasta ahora.",
        "Parte del dinero de tus cuentas el último día con datos. Resta los pagos recurrentes que aún faltan por cobrar este mes, "
        "suma los ingresos fijos que aún faltan por llegar (por ejemplo, la nómina) y resta el gasto del día a día (lo que no es "
        "un pago fijo) al ritmo de los últimos 60 días. Es una estimación, no una promesa: no sabe de gastos extraordinarios ni de "
        "ingresos que no se repiten. Con menos de dos semanas de datos no estima el gasto diario (solo cuenta los pagos fijos) y "
        "no sale nada si el último día con datos ya es el último del mes.",
        "Tienes 2.000 € y quedan 10 días: falta un recibo de 50 € y sueles gastar unos 15 € al día. Previsión: 2.000 - 50 - 150 = 1.800 €.",
        keywords=("previsión", "prevision", "fin de mes", "proyección", "estimación", "saldo futuro"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Traspasos entre tus cuentas",
        "Si mueves dinero de una cuenta tuya a otra, Kreix lo reconoce y no lo cuenta ni como gasto ni como ingreso: el dinero solo "
        "ha cambiado de sitio.",
        "Une una salida y una entrada del mismo importe, en cuentas distintas y con menos de cuatro días de diferencia, cuando al "
        "menos una es un traspaso. Cada movimiento forma pareja una sola vez. En la tabla de movimientos se ven como «Traspaso entre "
        "tus cuentas». Si miras solo una de las dos cuentas, el traspaso sí cuenta según tu ajuste de traspasos entrantes.",
        "",
        keywords=("traspaso", "traspasos", "entre cuentas", "cuentas propias", "emparejar"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Gasto medio mensual y diario",
        "Cuánto gastas de media. En la vista global se muestra por mes; si eliges un mes, por día.",
        "Gastos del periodo ÷ meses transcurridos (o ÷ días transcurridos). En el mes en curso se cuenta hasta el "
        "último día con datos.",
        "Gastas 450 € en un mes de 30 días: 15 € de media al día.",
        keywords=("media",),
    ),
    HelpEntry(
        S_ACCOUNTS, "Comparación con el mes anterior",
        "Cuando miras un mes, las cifras de Ingresos y Gastos dicen cuánto han subido o bajado respecto al mes de antes, "
        "para que veas si vas mejor o peor sin hacer cuentas.",
        "(importe de este mes - importe del mes anterior) ÷ importe del mes anterior. Solo aparece si el mes anterior "
        "tiene datos. Si la diferencia es menor del 0,5 %, Kreix dice «Igual que».",
        "Gastaste 400 € en agosto y 440 € en septiembre: «+10 % frente a ago 26».",
        keywords=("variación", "mes anterior", "comparar"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Presupuestos",
        "Un tope de gasto al mes en una categoría (por ejemplo, 250 € en supermercado). Kreix te enseña cuánto llevas "
        "gastado y cuánto te queda, y avisa en rojo cuando te pasas. En Inicio, «Presupuestos del mes» los va mostrando "
        "todos, de uno en uno, cada pocos segundos; con las flechas, los puntos o las teclas ← → pasas tú, y se detiene "
        "mientras tienes el ratón encima.",
        "Gasto de la categoría en el periodo frente a tu tope. Barra verde: vas bien; amarilla: has usado más del 85 %; "
        "roja: te has pasado. Si miras todo el historial, se compara el gasto medio mensual con el tope.",
        "Tu tope de ocio es 60 € y llevas 51 €: barra amarilla, «Quedan 9,00 €».",
        "Los traspasos entre tus cuentas y las aportaciones a inversión no son gasto y no tienen presupuesto.",
        keywords=("tope", "límite", "gastar", "presupuesto"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Pagos recurrentes",
        "Suscripciones y recibos que se repiten cada mes por un importe parecido (Netflix, el gimnasio, la luz...). "
        "Sirven para saber cuánto dinero tienes comprometido antes de empezar el mes.",
        "Kreix los detecta solo: un cargo que se repite al menos tres meses seguidos, cada unos 30 días y con un importe "
        "estable (hasta un 20 % de diferencia). Si un cargo no vuelve a aparecer en mes y medio, se da por cancelado. "
        "La fecha del próximo cargo es una estimación. Los «Próximos pagos» de Inicio son estos mismos pagos, solo los que tocan en las próximas semanas.",
        "Netflix cobra 12,99 € cada mes: se muestra como 12,99 € al mes y 155,88 € al año.",
        "El supermercado no aparece aquí aunque gastes cada semana: varía de importe y se repite más de una vez al mes.",
        "Si Kreix no detecta una suscripción, o detecta una que no lo es, pulsa ••• (o clic derecho) sobre uno de sus movimientos en Cuentas y elige «Marcar como pago recurrente» o «No es un pago recurrente». Un pago marcado por ti aparece aunque solo tenga un cargo: Kreix usa el ritmo que vea en sus cargos (mensual si solo hay uno). Cualquier pago de Próximos pagos o de Pagos recurrentes se quita con clic derecho > «Quitar de pagos recurrentes», lo haya detectado Kreix o lo hayas marcado tú (por ejemplo, porque lo has dado de baja).",
        keywords=("suscripciones", "recibos", "domiciliaciones", "fijos", "mensuales"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Cambiar la categoría de un movimiento",
        "Si Kreix pone un movimiento en la categoría equivocada, pulsa ••• (o haz doble clic o clic derecho) sobre él y elige otra. Tu elección "
        "nunca se cambia sola. También puedes volver a la categoría automática.",
        "Con «Crear regla para…» le dices a Kreix que todos los conceptos con esa palabra van a una categoría, también "
        "los que importes en el futuro. Tus reglas mandan sobre las que trae Kreix y se gestionan en Ajustes.",
        "Pones la regla «PANADERIA» → Restaurantes: todos los pagos de panadería pasan a Restaurantes.",
        keywords=("recategorizar", "reglas", "clasificar", "categorizar", "corregir"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Mayor gasto",
        "El pago individual más grande del periodo. Útil para detectar gastos puntuales que distorsionan el mes.",
        "El movimiento negativo de mayor importe que cuenta como gasto.",
    ),
    HelpEntry(
        S_ACCOUNTS, "Categoría principal",
        "La categoría en la que más dinero se ha ido: supermercado, ocio, transporte...",
        "Kreix asigna cada gasto a una categoría buscando palabras clave en el concepto del banco (por ejemplo, "
        "«Mercadona» va a Supermercado). Lo que no reconoce queda como «Sin categoría».",
        "",
        keywords=("categorías", "categorias"),
    ),
    HelpEntry(
        S_ACCOUNTS, "Movimientos",
        "Cada entrada o salida de dinero que aparece en el extracto de tu banco. En la tabla están del más reciente "
        "al más antiguo; puedes buscar por concepto, filtrar por categoría y ordenar pulsando cualquier cabecera.",
        "Dentro de un mismo día se respeta el orden real, que Kreix reconstruye con la cadena de saldos.",
    ),
    HelpEntry(
        S_ACCOUNTS, "Bizum",
        "Pagos entre personas. Si repartes gastos con amigos, el Bizum que recibes no es un ingreso «de verdad», "
        "porque en realidad te devuelven dinero que adelantaste.",
        "Puedes decidir en Ajustes si los Bizum cuentan como ingresos y gastos. Por defecto cuentan.",
    ),
    HelpEntry(
        S_ACCOUNTS, "Traspaso",
        "Mover dinero entre cuentas tuyas (o recibirlo de otra cuenta tuya). No es ni ganar ni gastar dinero.",
        "Los traspasos que entran cuentan como ingreso (se puede cambiar en Ajustes); los que salen no cuentan como gasto.",
    ),
    HelpEntry(
        S_ACCOUNTS, "Gráficos de Cuentas",
        "Gastos por categoría: en qué se va tu dinero. Evolución del saldo: cuánto hay en la cuenta al cierre de cada "
        "día con movimientos. Ingresos y gastos por mes: si cada mes entra más de lo que sale.",
        "",
        "",
        keywords=("gráfico", "grafico"),
    ),

    # ------------------------------------------------------------------ Tus inversiones
    HelpEntry(
        S_INVEST, "Fondo indexado",
        "Un fondo que copia un índice (por ejemplo, las 500 mayores empresas de EE. UU.) en lugar de intentar "
        "ganarle al mercado. Suele tener comisiones muy bajas y es lo que se compra en MyInvestor.",
        "",
        "",
        keywords=("fondo", "indexado", "índice", "indice"),
    ),
    HelpEntry(
        S_INVEST, "Participación",
        "Cada «trocito» de un fondo. Al invertir compras participaciones; cuántas recibes depende del importe que "
        "pones y del valor liquidativo de ese día.",
        "",
        "Inviertes 500 € cuando cada participación vale 250 €: recibes 2 participaciones.",
    ),
    HelpEntry(
        S_INVEST, "Valor liquidativo (VL)",
        "El precio de una participación. Se calcula una vez al día. Cuando sube, tu inversión vale más.",
        "",
        "Tienes 2 participaciones y el valor liquidativo es 250 €: tu posición vale 500 €.",
        keywords=("vl", "precio", "valor liquidativo"),
    ),
    HelpEntry(
        S_INVEST, "Precio medio",
        "Lo que has pagado de media por cada participación, contando todas tus compras.",
        "Capital invertido ÷ participaciones.",
        "Compras 1 participación a 100 € y otra a 120 €: tu precio medio es 110 €.",
        keywords=("precio medio de compra",),
    ),
    HelpEntry(
        S_INVEST, "Aportado (capital invertido)",
        "El dinero que has puesto en total en tus inversiones, sin contar lo que ha ganado o perdido.",
        "Compras - ventas. En la vista por mes, lo aportado durante ese mes.",
        "Metes 1.000 € en enero y 500 € en febrero: has aportado 1.500 €.",
        keywords=("capital invertido", "aportaciones", "aportado"),
    ),
    HelpEntry(
        S_INVEST, "Valor de la cartera",
        "Lo que valdrían hoy todas tus participaciones si las vendieras.",
        "Participaciones × valor liquidativo de cada fondo, sumado. Es el valor del último extracto de cartera importado.",
        "",
        keywords=("valor de mercado",),
    ),
    HelpEntry(
        S_INVEST, "Aportación media mensual",
        "Cuánto dinero metes de media cada mes en tus inversiones.",
        "Aportado ÷ meses desde la primera compra.",
        "Has aportado 5.000 € en 10 meses: 500 € al mes de media.",
    ),
    HelpEntry(
        S_INVEST, "Posición mayor",
        "El fondo que más pesa en tu cartera y qué porcentaje de ella representa. Si es muy alto, dependes mucho de ese fondo.",
        "Valor de ese fondo ÷ valor de toda la cartera.",
    ),
    HelpEntry(
        S_INVEST, "Operaciones",
        "Las compras y ventas de fondos. En MyInvestor comprar se llama «suscripción» y vender, «reembolso».",
        "",
        "",
        keywords=("compra", "venta", "suscripción", "suscripcion", "reembolso"),
    ),
    HelpEntry(
        S_INVEST, "ISIN",
        "El código internacional de 12 caracteres que identifica cada fondo, como un DNI. Sirve para no confundir "
        "dos fondos con nombres parecidos.",
        "",
        "IE00B03HD191",
    ),
    HelpEntry(
        S_INVEST, "Aportado frente a valor",
        "Un gráfico con dos líneas: lo que has puesto y lo que vale tu cartera. La distancia entre ambas es lo que "
        "ha ganado (o perdido) tu inversión con el tiempo.",
        "",
        "",
        keywords=("gráfico", "grafico"),
    ),

    # ------------------------------------------------------------------ Rentabilidad
    HelpEntry(
        S_RETURNS, "Plusvalía y minusvalía",
        "La ganancia (plusvalía) o la pérdida (minusvalía) de tu inversión: lo que vale ahora menos lo que pusiste. "
        "Es una ganancia «sobre el papel»: solo se hace real si vendes.",
        "Valor de la cartera - capital invertido.",
        "Pusiste 4.000 € y hoy valen 4.200 €: plusvalía de +200 €.",
        keywords=("ganancia", "pérdida", "perdida"),
    ),
    HelpEntry(
        S_RETURNS, "Rentabilidad global",
        "El porcentaje que has ganado o perdido sobre lo que has puesto, sin importar cuánto tiempo haya pasado.",
        "Plusvalía ÷ capital invertido.",
        "Pusiste 1.000 € y hoy valen 1.100 €: rentabilidad de +10 %.",
        keywords=("rendimiento", "rentabilidad simple"),
    ),
    HelpEntry(
        S_RETURNS, "TWR (rentabilidad ponderada en el tiempo)",
        "Mide lo bien que han funcionado tus fondos, sin que influya cuándo ni cuánto dinero metiste. Es la mejor "
        "cifra para comparar tus fondos con un índice o con otros fondos.",
        "Kreix calcula la rentabilidad de cada tramo entre dos aportaciones y las encadena.",
        "Un fondo sube un 50 % y después baja un 20 %: el TWR es +20 % (1,5 × 0,8 = 1,2), aunque hayas aportado "
        "mucho más dinero justo antes de la bajada.",
        keywords=("twr", "time weighted", "ponderada"),
    ),
    HelpEntry(
        S_RETURNS, "TIR (tasa interna de retorno)",
        "La rentabilidad anual media de TU dinero, teniendo en cuenta cuándo pusiste cada euro. Responde a esta "
        "pregunta: «si hubiera tenido este dinero en una cuenta que paga un interés fijo al año, ¿qué interés "
        "tendría que pagar para darme el mismo resultado?».",
        "Se calcula con todas tus aportaciones, sus fechas y el valor actual de la cartera, y se expresa en tasa anual "
        "(año de 365 días).",
        "Un 4 % ganado en tres meses equivale a casi un 17 % anual.",
        "Con pocos meses de inversión la TIR exagera: no significa que vayas a ganar eso durante un año entero. "
        "Es más fiable cuando llevas más de un año.",
        keywords=("tir", "xirr", "irr", "rentabilidad anualizada"),
    ),
    HelpEntry(
        S_RETURNS, "¿Por qué la TIR y el TWR son distintos?",
        "Responden a preguntas diferentes. El TWR valora los fondos; la TIR valora tus decisiones de cuándo comprar. "
        "Si metes mucho dinero justo antes de una bajada, el TWR no lo nota pero tu TIR sí lo refleja. "
        "Es normal que no coincidan; si aportas siempre lo mismo y a intervalos regulares, suelen parecerse.",
    ),
    HelpEntry(
        S_RETURNS, "Variación del mes",
        "Cuánto ha subido o bajado tu cartera durante el mes sin contar el dinero nuevo que metiste.",
        "Valor al cierre - valor al inicio - aportado en el mes.",
        "La cartera pasa de 5.000 € a 5.600 € y has aportado 500 €: variación de +100 €.",
    ),
    HelpEntry(
        S_RETURNS, "Valor estimado al cierre",
        "En la vista por mes, Kreix no conoce el valor exacto de cada día: solo tiene la foto de la cartera del día "
        "en que la importaste. Por eso lo estima.",
        "Participaciones según tus operaciones × precio estimado, que se interpola entre los valores liquidativos conocidos.",
        "",
        keywords=("estimado",),
    ),

    # ------------------------------------------------------------------ Avisos
    HelpEntry(
        S_WARNINGS, "«La cartera no cuadra con las operaciones»",
        "Kreix compara las participaciones que dice tu extracto de cartera con las que suman tus operaciones "
        "importadas. Si no coinciden, falta algún historial. Para no enseñarte números falsos, la TIR y el TWR se "
        "ocultan hasta que cuadre.",
        "",
        "",
        "",
        "Exporta desde MyInvestor el historial completo de operaciones, desde la primera compra, y vuelve a importarlo.",
        keywords=("no cuadra", "aviso", "cuadre"),
    ),
    HelpEntry(
        S_WARNINGS, "«El saldo no cuadra»",
        "En el extracto de una cuenta, cada saldo debe ser el anterior más el importe del movimiento. Si no es así, "
        "probablemente falta algún movimiento porque descargaste un tramo incompleto.",
        "",
        "",
        "",
        "Descarga de nuevo el extracto cubriendo todo el periodo e impórtalo.",
        keywords=("saldo", "aviso", "cuadre"),
    ),
    HelpEntry(
        S_WARNINGS, "Sin categoría",
        "Gastos cuyo concepto Kreix no ha sabido clasificar, por ejemplo el nombre de una persona en un pago.",
        "Las categorías se asignan por palabras clave en el concepto del banco.",
    ),

    # ------------------------------------------------------------------ Usar Kreix
    HelpEntry(
        S_USE, "Primeros pasos y datos de ejemplo",
        "Si aún no has importado nada, la pantalla de inicio te explica qué hacer en tres pasos. Con «Probar con datos de "
        "ejemplo» puedes explorar Kreix con datos inventados, sin importar los tuyos.",
        "Los datos de ejemplo se ven con un aviso arriba. Con «Empezar con mis datos» se quitan, y también se quitan solos "
        "cuando importas tus extractos reales: nunca se mezclan con los tuyos. Cuando ya tienes datos, Inicio muestra "
        "una lista de primeros pasos con lo que te falta; puedes ocultarla.",
        "",
        keywords=("empezar", "demo", "ejemplo", "bienvenida", "tutorial", "primera vez"),
    ),
    HelpEntry(
        S_USE, "Revisar antes de importar",
        "Al soltar un extracto, Kreix no lo guarda a la primera: te enseña qué ha leído (cuántos movimientos, de qué fechas, "
        "cuántos son nuevos y cuántos ya estaban) y tú decides si importar.",
        "Los movimientos que ya tenías se ignoran. Si un archivo no se puede leer, Kreix te dice por qué y qué hacer "
        "(por ejemplo, descargarlo otra vez en CSV o Excel sin editarlo).",
        "",
        keywords=("vista previa", "importar", "confirmar", "error", "archivo", "duplicados"),
    ),
    HelpEntry(
        S_USE, "Avisos y Deshacer",
        "Cada cambio importante (importar, cambiar una categoría, crear una regla, borrar datos...) muestra un aviso breve "
        "abajo. Si te has equivocado, pulsa Deshacer mientras el aviso siga a la vista.",
        "Solo se puede deshacer el último cambio: al hacer otro, el anterior ya no se puede revertir. Kreix guarda una copia "
        "de tus datos justo antes de cada cambio, así que deshacer vuelve exactamente a cómo estaba todo.",
        "",
        keywords=("deshacer", "revertir", "error", "equivocación", "confirmación", "aviso"),
    ),
    HelpEntry(
        S_USE, "Buscar en todo (Ctrl+K)",
        "Con Ctrl+K se abre un buscador: escribe «presupuesto», «modo oscuro», el nombre de un comercio o «TIR» y salta "
        "directamente a esa página, acción, movimiento o explicación de la ayuda.",
        "Elige con las flechas y Intro. Entiende las palabras sin acentos y por el principio de cada palabra.",
        "",
        keywords=("buscador", "atajo", "comandos", "ir a", "paleta"),
    ),
    HelpEntry(
        S_USE, "Lo que te interesa: cuentas, inversiones o ambas",
        "La primera vez, Kreix te pregunta qué quieres gestionar: tus cuentas bancarias, tus inversiones o las dos cosas. "
        "Se elige con dos interruptores y siempre tiene que quedar al menos uno activado.",
        "Inicio se adapta: sin inversiones no muestra el rendimiento ni el reparto de activos; sin cuentas no muestra la tasa "
        "de ahorro, el flujo de caja, los pagos recurrentes ni los presupuestos. Lo desactivado no se borra: su pestaña sigue "
        "ahí y ofrece un botón para activarlo. También puedes cambiarlo en Ajustes, en «Lo que te interesa». Se guarda con "
        "tus datos y viaja con ellos al exportar e importar.",
        "",
        keywords=("interés", "intereses", "gestionar", "activar", "desactivar", "solo cuentas", "solo inversiones"),
    ),
    HelpEntry(
        S_USE, "Idioma de la aplicación",
        "Kreix está en castellano, català y English. La primera vez eliges el idioma en el mismo cuadro donde te pregunta "
        "el nombre y lo que te interesa; cada idioma lleva la bandera de su país o región.",
        "Puedes cambiarlo cuando quieras en Ajustes, en «Idioma»: toda la aplicación (menús, ayuda, avisos, fechas y "
        "números) cambia al instante, sin perder tu sitio. El idioma se guarda con tus datos y viaja con ellos al exportar "
        "e importar. En inglés los números se escriben como 1,234.56; en castellano y catalán, como 1.234,56.",
        "",
        keywords=("idioma", "lengua", "castellano", "catalán", "català", "english", "inglés", "bandera", "language"),
    ),
    HelpEntry(
        S_USE, "Tu nombre y el saludo",
        "Inicio te saluda según la hora: buenos días, buenas tardes o buenas noches, seguido de tu nombre y de un punto. "
        "Kreix te lo pregunta la primera vez que lo abres, y puedes cambiarlo o quitarlo cuando quieras en Ajustes, en «Tu nombre».",
        "El nombre se guarda en tu ordenador junto al resto de ajustes. Al exportar tus datos a un archivo .kreix viaja "
        "con ellos, y al importarlo en otro equipo Kreix te saluda igual, sin volver a preguntarte. Debajo del saludo, Inicio "
        "muestra el día y la hora (siempre al día) y la fecha de la última actualización de tus datos: el último día en que "
        "importaste algo.",
        "",
        keywords=("nombre", "usuario", "saludo", "perfil", "buenos días", "inicio"),
    ),
    HelpEntry(
        S_USE, "Cielo y luz según la hora",
        "Junto a tu nombre, Inicio dibuja un sol que sale por la mañana y sube hasta el mediodía, el mismo sol bajando por la "
        "tarde hasta ponerse, y una luna con estrellas por la noche. Se mueve despacio: los rayos giran, pasa una nube, las "
        "estrellas centellean. Recorre su ciclo completo con la hora real, aunque dejes Kreix abierto todo el día.",
        "Además, por la tarde y por la noche la pantalla baja su brillo muy poco (como mucho un 7 %), sin cambiar de tema ni de "
        "colores. Si lo prefieres quieto y sin atenuar, desactiva «Cielo animado y luz según la hora» en Ajustes. "
        "Las horas son: sol de 6 a 21, luna de 21 a 6.",
        "",
        keywords=("sol", "luna", "animación", "noche", "día", "brillo", "atenuar", "ambiente"),
    ),
    HelpEntry(
        S_USE, "Importar extractos",
        "Arrastra a la pantalla Importar los archivos que descargas del banco (CSV o Excel). Kreix reconoce solo de qué "
        "banco y de qué tipo son, aunque no tengan extensión. Importar dos veces el mismo extracto no duplica nada.",
        "Si tienes varias cuentas, elige a cuál pertenece el extracto. El extracto de cartera de MyInvestor no trae fecha: "
        "indica a qué día corresponde.",
        "",
        keywords=("importar", "csv", "excel", "extracto"),
    ),
    HelpEntry(
        S_USE, "Todo el historial o un mes",
        "En Cuentas e Inversiones puedes ver todo el historial o un mes concreto con el selector de arriba. Las cifras, "
        "los gráficos y las tablas se ajustan al periodo elegido. Las flechas saltan al mes anterior o siguiente.",
    ),
    HelpEntry(
        S_USE, "Varias cuentas",
        "En Cuentas puedes añadir, renombrar o eliminar cuentas bancarias y ver una sola o todas juntas. "
        "Al importar eliges a qué cuenta va cada extracto. La cartera de inversión es una sola.",
    ),
    HelpEntry(
        S_USE, "Exportar movimientos a CSV o Excel",
        "En Cuentas, el botón Exportar guarda en un archivo CSV o Excel los movimientos que estás viendo, para abrirlos "
        "en una hoja de cálculo o llevárselos a tu asesor.",
        "Se exportan solo las filas visibles, con el filtro y el orden que tengas en la tabla. Los importes van como "
        "números en Excel y con coma decimal en CSV. Kreix no exporta a PDF.",
        "",
        keywords=("csv", "excel", "descargar", "hoja de cálculo", "xlsx"),
    ),
    HelpEntry(
        S_USE, "Exportar e importar tus datos",
        "Exportar crea un único archivo .kreix con todos tus datos para guardarlo o llevarlo a otro ordenador. "
        "En el otro equipo, arrástralo a Importar: sus datos serán idénticos a los de origen.",
        "",
        "",
        "Importar un archivo .kreix reemplaza los datos que hubiera en ese equipo. El archivo no está cifrado: "
        "contiene tu información financiera, guárdalo en un sitio seguro.",
        keywords=("exportar", "copia de seguridad", "backup", "mover datos", "kreix"),
    ),
    HelpEntry(
        S_USE, "Bloqueo automático",
        "Si dejas de usar el equipo unos minutos, minimizas la ventana, bloqueas Windows (Win+L) o suspendes el equipo, Kreix "
        "esconde tus datos y vuelve a pedir la contraseña maestra. También puedes bloquearlo a mano con Ctrl+L o desde Ajustes.",
        "En Ajustes, en Seguridad, eliges el tiempo (o «Nunca») y si quieres que se bloquee al minimizar. Tras varias "
        "contraseñas incorrectas seguidas, Kreix te hace esperar unos segundos antes del siguiente intento, y la espera "
        "crece. Un cuadro que tuvieras abierto se cierra al bloquear; tus datos ya estaban guardados. Al crear o cambiar la "
        "contraseña, un medidor te dice lo difícil que sería adivinarla: mezcla letras, números y símbolos, o usa una frase larga.",
        "",
        keywords=("bloqueo", "bloquear", "inactividad", "minimizar", "contraseña", "seguridad", "candado"),
    ),
    HelpEntry(
        S_USE, "Copias de seguridad automáticas",
        "Kreix guarda solo una copia cifrada de tus datos en una carpeta: al abrir, si aún no hay ninguna; después de hacer "
        "cambios, como mucho una por hora; y al cerrar. Se conservan las últimas 3, 5, 10 o 20, y las más viejas se borran.",
        "Abajo a la izquierda ves cuándo se hizo la última. «Comprobar la última copia», en Ajustes, la abre de verdad y te dice si "
        "sirve. Cada copia es un archivo .kreix con la fecha en el nombre, cifrado con tu contraseña maestra. En Ajustes eliges la "
        "carpeta (por ejemplo, un disco externo o una carpeta sincronizada). Para recuperar una, pulsa Restaurar junto a ella "
        "y escribe tu contraseña maestra: sustituye los datos actuales y puedes deshacerlo. Si cambias la contraseña, las "
        "copias se vuelven a cifrar con la nueva.",
        "",
        keywords=("copia", "copias", "backup", "seguridad", "restaurar", "recuperar", "carpeta"),
    ),
    HelpEntry(
        S_USE, "Importar de otro banco",
        "Si Kreix no reconoce un CSV o Excel porque no es de Imagin ni de MyInvestor, te deja decirle qué columna es cada "
        "cosa: la fecha, el concepto, el importe y, si la hay, el saldo.",
        "Ves las primeras filas del archivo y Kreix propone las columnas por sus títulos; tú las corriges. Si el banco separa "
        "ingresos y gastos en dos columnas, eliges «Dos columnas». También indicas si los decimales llevan coma o punto y el "
        "orden de la fecha. Antes de guardar ves cuántos movimientos se leen y los primeros, para comprobar fechas e importes. "
        "El formato se guarda con el nombre que le pongas y se aplica solo a los archivos siguientes; en Importar puedes "
        "olvidarlo. Solo CSV y Excel, nunca PDF.",
        "",
        keywords=("otro banco", "columnas", "formato", "importar", "csv", "excel", "asistente"),
    ),
    HelpEntry(
        S_USE, "Modo privacidad",
        "El ojo de la barra lateral (o Ctrl+H) oculta todas las cantidades en euros: difumina cada importe: se ve que hay una cifra, nunca cuál. Sirve para "
        "mirar Kreix con alguien al lado o compartir la pantalla.",
        "Se ocultan los importes de las cifras, los gráficos (incluidos sus ejes), las tablas y los avisos. Los porcentajes se "
        "siguen viendo. Se recuerda al cerrar y abrir Kreix. Los cuadros donde tú escribes un importe (presupuestos, metas) "
        "muestran lo que escribes.",
        "",
        keywords=("privacidad", "ocultar", "cifras", "ojo", "dinero", "pantalla", "compartir"),
    ),
    HelpEntry(
        S_USE, "Por clasificar y reglas sugeridas",
        "En Inicio, «Por clasificar» te dice cuántos movimientos aún no tienen categoría y, si un mismo comercio se repite, te propone "
        "una regla para clasificarlos de una vez.",
        "Pulsa «Crear regla…» junto a un comercio: se abre el cuadro de nueva regla con su palabra ya escrita y solo tienes que elegir "
        "la categoría. La regla se aplica a todos los movimientos con esa palabra, también a los que importes después. «Ver los "
        "movimientos» abre Cuentas filtrado por «Sin categoría».",
        "",
        keywords=("clasificar", "categoría", "sin categoría", "regla", "reglas", "sugerencia", "comercio"),
    ),
    HelpEntry(
        S_USE, "Tamaño del texto",
        "En Ajustes puedes hacer más grande la letra de toda la aplicación: normal, grande (110 %) o muy grande (125 %).",
        "Cambia menús, tablas, gráficos y cuadros, y se aplica al momento. También vale para la pantalla de la contraseña. Si algo "
        "no se lee bien, prueba con un tamaño mayor.",
        "",
        keywords=("tamaño", "letra", "texto", "accesibilidad", "grande", "zoom"),
    ),
    HelpEntry(
        S_USE, "Privacidad",
        "Todo se guarda solo en tu ordenador. Kreix no usa internet, no tiene cuentas y no envía datos a ningún servidor.",
        "",
        "",
        keywords=("datos", "seguridad"),
    ),
    HelpEntry(
        S_USE, "Atajos de teclado",
        "Ctrl+1 Inicio, Ctrl+2 Cuentas, Ctrl+3 Inversiones, Ctrl+4 Importar, Ctrl+5 Exportar, Ctrl+6 Ajustes, "
        "Ctrl+7 Ayuda. Ctrl+T cambia entre modo claro y oscuro, Ctrl+K busca en todo, Ctrl+F busca en tus movimientos, "
        "Ctrl+L bloquea Kreix, Ctrl+H oculta las cantidades y F5 recalcula la página.",
        "",
        "",
        keywords=("teclado", "ctrl"),
    ),
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", normalize(text))


def search(entries: tuple[HelpEntry, ...] | list[HelpEntry], query: str) -> list[HelpEntry]:
    """Entradas cuyo texto contiene cada palabra de la busqueda COMO COMIENZO DE PALABRA (sin distinguir
    mayusculas ni acentos): "tir" encuentra la TIR pero no "invertir". Van primero las que
    coinciden en el titulo, luego en los sinonimos y despues en el cuerpo."""
    words = _tokens(query)
    if not words:
        return list(entries)
    ranked: list[tuple[int, int, HelpEntry]] = []
    for position, e in enumerate(entries):
        body = _tokens(" ".join((e.term, e.plain, e.how, e.example, e.note, e.todo, *e.keywords)))
        if not all(any(t.startswith(w) for t in body) for w in words):
            continue
        title = _tokens(e.term)
        head = _tokens(" ".join((e.term, *e.keywords)))
        tier = 0 if all(any(t.startswith(w) for t in title) for w in words) else (
            1 if all(any(t.startswith(w) for t in head) for w in words) else 2)
        ranked.append((tier, position, e))
    return [e for _, _, e in sorted(ranked, key=lambda r: (r[0], r[1]))]


def grouped(entries: list[HelpEntry] | tuple[HelpEntry, ...]) -> list[tuple[str, list[HelpEntry]]]:
    """Entradas agrupadas por seccion, en el orden de SECTIONS."""
    return [(s, [e for e in entries if e.section == s]) for s in SECTIONS if any(e.section == s for e in entries)]


def localized_entries() -> tuple[HelpEntry, ...]:
    """Las entradas del glosario en el idioma activo (en castellano son las originales). Lo que no tenga traduccion
    se queda en castellano; la seccion siempre es la clave original (se traduce al mostrarla)."""
    language = i18n.language()
    if language == i18n.DEFAULT:
        return ENTRIES
    texts = _help_texts(language)
    out: list[HelpEntry] = []
    for entry in ENTRIES:
        t = texts.get(entry.term)
        if t is None:
            out.append(entry)
            continue
        out.append(HelpEntry(
            entry.section, t.get("term", entry.term), t.get("plain", entry.plain), t.get("how", entry.how),
            t.get("example", entry.example), t.get("note", entry.note), t.get("todo", entry.todo),
            tuple(t.get("keywords", entry.keywords)),
        ))
    return tuple(out)


def localized_term(term: str) -> str:
    """El nombre de un termino del glosario (clave en castellano) en el idioma activo, para buscarlo en la Ayuda."""
    for original, shown in zip(ENTRIES, localized_entries()):
        if original.term == term:
            return shown.term
    return term


def _help_texts(language: str) -> dict[str, dict]:
    import importlib

    return importlib.import_module(f"ui.help_texts.{language}").HELP
