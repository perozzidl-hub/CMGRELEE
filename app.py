"""
app.py — AppCMG: Explorador de Contribución Marginal al detalle
==================================================================
Streamlit app para navegar al máximo nivel de detalle la venta (clientes,
locaciones, canales) y la Contribución Marginal calculada para cada
artículo, cliente, locación y canal.

CORRECCIONES respecto de la versión anterior:
  1. Tab "Datos crudos": se elimina el Styler que crasheaba (fmt_entero
     explotaba con códigos de cliente en formato texto). Ahora la columna
     "Cliente" se convierte a entero nullable (Int64) ANTES de mostrarla,
     y se renderiza con st.dataframe plano.
  2. fig_top_clientes: len(codigos) devolvía la cantidad de filas, no el
     largo del string. Truncado de etiquetas reescrito de forma vectorizada.
  3. Tendencia mensual: la CM se alinea por mes con .map(), no por posición.
  4. Tab artículo: st.stop() reemplazado por un if/else (ya no mata los
     demás tabs cuando no hay artículos para el filtro).
  5. fmt_n / fmt_pesos / fmt_entero: robustos ante strings, None y NaN.
  6. CM_%: división protegida contra Facturación Neta = 0.
  7. Insumos de artículo R: columnas filtradas por las que realmente existen.

Ejecutar con:
    streamlit run app.py
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_loader import cargar_todo
from calculo_cmg import calcular_cmg, COLUMNAS_CASCADA, PALLETS_POR_CAMION

st.set_page_config(
    page_title="AppCMG - Contribución Marginal al detalle",
    page_icon="🥤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================================
# IDENTIDAD VISUAL
# Paleta corporativa inspirada en Coca-Cola (aproximación para uso interno:
# si tenés el hex oficial de tu manual de marca, reemplazalo acá).
# ======================================================================
ROJO = "#E4032E"
CARBON = "#1A1A1A"
BLANCO = "#FFFFFF"
CREMA = "#FAFAF8"
GRIS_BORDE = "#E5E2DD"
GRIS_TEXTO = "#6B6B6B"
VERDE = "#1E8A44"
DORADO = "#B8902E"

PALETA_CATEGORICA = [ROJO, CARBON, DORADO, "#8C8C8C", "#F0A6A6", "#D9C48A", "#5C5C5C"]

PLOTLY_BASE = dict(
    font=dict(family="Inter, -apple-system, sans-serif", color=CARBON, size=13),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    separators=",.",  # formato local: decimal="," / miles="."
)


# ----------------------------------------------------------------------
# FORMATO NUMÉRICO (criterio local: miles con ".", decimales con ",")
# ----------------------------------------------------------------------
def _es_vacio(valor) -> bool:
    """True si el valor es None o NaN (escalar)."""
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def fmt_n(valor, decimales=0):
    """Número con criterio local: miles con ".", decimales con ",". NaN -> "—".
    Robusto: si el valor no es numérico, lo devuelve como texto en vez de explotar."""
    if _es_vacio(valor):
        return "—"
    try:
        s = f"{float(valor):,.{decimales}f}"
    except (ValueError, TypeError):
        return str(valor)
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_pesos(valor, decimales=0):
    return f"$ {fmt_n(valor, decimales)}"


def fmt_entero(valor):
    """Códigos de cliente: siempre enteros, sin decimales.
    Robusto: ante texto no numérico devuelve el texto original (no explota)."""
    if _es_vacio(valor):
        return "—"
    try:
        return str(int(round(float(valor))))
    except (ValueError, TypeError):
        return str(valor)


def aplicar_estilos():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        .stApp {{ background-color: {CREMA}; }}

        .cmg-encabezado {{ border-left: 4px solid {ROJO}; padding: 2px 0 2px 16px; margin-bottom: 6px; }}
        .cmg-encabezado h1 {{ font-size: 1.55rem; font-weight: 700; color: {CARBON}; margin: 0; }}
        .cmg-encabezado p {{ color: {GRIS_TEXTO}; font-size: 0.9rem; margin: 4px 0 0 0; }}

        div[data-testid="stMetric"] {{
            background: transparent; border: none;
            border-bottom: 3px solid {ROJO}; padding: 0 2px 10px 2px;
        }}
        div[data-testid="stMetricLabel"] {{ color: {GRIS_TEXTO}; font-weight: 500; font-size: 0.82rem; }}
        div[data-testid="stMetricValue"] {{ color: {CARBON}; font-weight: 700; }}

        .cmg-panel-titulo {{ font-weight: 600; color: {CARBON}; font-size: 1.02rem; margin-bottom: 1px; }}
        .cmg-panel-caption {{ color: {GRIS_TEXTO}; font-size: 0.83rem; margin-bottom: 8px; }}
        .cmg-divisor {{ border: none; border-top: 1px solid {GRIS_BORDE}; margin: 26px 0 16px 0; }}

        .cmg-badge {{ display:inline-block; padding: 2px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; vertical-align: middle; }}
        .cmg-badge-p {{ background: rgba(30,138,68,0.12); color: {VERDE}; }}
        .cmg-badge-r {{ background: rgba(184,144,46,0.18); color: {DORADO}; }}
        .cmg-badge-x {{ background: rgba(107,107,107,0.12); color: {GRIS_TEXTO}; }}

        [data-testid="stSidebar"] {{ background-color: {BLANCO}; border-right: 1px solid {GRIS_BORDE}; }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {CARBON}; font-weight: 600; }}
        .cmg-marca {{ font-size: 1.15rem; font-weight: 700; color: {CARBON}; border-bottom: 3px solid {ROJO}; display:inline-block; padding-bottom: 4px; }}
        [data-baseweb="tag"] {{ background-color: {ROJO} !important; }}

        button[data-baseweb="tab"] {{ font-weight: 600; color: {GRIS_TEXTO}; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: {ROJO}; }}
        div[data-baseweb="tab-highlight"] {{ background-color: {ROJO} !important; }}

        div[data-testid="stAlert"] {{ border-radius: 8px; }}
        [data-testid="stDataFrame"] {{ border: 1px solid {GRIS_BORDE}; border-radius: 6px; }}
        [data-testid="stSpinner"] {{ color: {CARBON}; font-weight: 500; }}
        .stButton > button, .stDownloadButton > button {{ border-radius: 6px; font-weight: 600; }}

        @media (max-width: 640px) {{
            div[data-testid="column"] {{ width: 100% !important; flex: 1 1 100% !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def titulo_panel(titulo, subtitulo=None):
    st.markdown(f'<div class="cmg-panel-titulo">{titulo}</div>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<div class="cmg-panel-caption">{subtitulo}</div>', unsafe_allow_html=True)


def divisor():
    st.markdown('<hr class="cmg-divisor">', unsafe_allow_html=True)


def badge_tipo_prod(tipo):
    clase = {"P": "cmg-badge-p", "R": "cmg-badge-r"}.get(tipo, "cmg-badge-x")
    return f'<span class="cmg-badge {clase}">{tipo}</span>'


def _hex_a_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


_ROJO_RGB, _DORADO_RGB, _VERDE_RGB = _hex_a_rgb(ROJO), _hex_a_rgb(DORADO), _hex_a_rgb(VERDE)


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _color_semaforo(valor, vmin, vmax):
    """Color relativo (rojo->dorado->verde) del valor DENTRO de esta tabla puntual.
    No es un benchmark de negocio: solo ordena visualmente lo que ya está en pantalla."""
    if _es_vacio(valor) or vmax == vmin:
        return ""
    t = max(0.0, min(1.0, (float(valor) - vmin) / (vmax - vmin)))
    if t < 0.5:
        r, g, b = _lerp(_ROJO_RGB, _DORADO_RGB, t / 0.5)
    else:
        r, g, b = _lerp(_DORADO_RGB, _VERDE_RGB, (t - 0.5) / 0.5)
    return f"background-color: rgba({r},{g},{b},0.30)"


def estilo_resumen(df):
    """Formatea $ / % / enteros (criterio local) y colorea CM_% en forma relativa.
    No cambia ningún valor."""
    fmt = {}
    for col in ("Facturacion_Neta", "CM_pesos"):
        if col in df.columns:
            fmt[col] = fmt_pesos
    for col in ("Cajas_Fisicas", "Clientes"):
        if col in df.columns:
            fmt[col] = fmt_n
    if "Cliente" in df.columns:  # código de cliente siempre entero
        fmt["Cliente"] = fmt_entero
    if "CM_%" in df.columns:
        fmt["CM_%"] = lambda v: f"{fmt_n(v, 1)}%"
    styler = df.style.format(fmt, na_rep="—")
    if "CM_%" in df.columns and df["CM_%"].notna().any():
        vmin, vmax = df["CM_%"].min(), df["CM_%"].max()
        styler = styler.map(lambda v: _color_semaforo(v, vmin, vmax), subset=["CM_%"])
    return styler


def estilo_cascada(df_cascada):
    ultimo = df_cascada.index[-1]

    def _fila(row):
        if row.name == ultimo:
            return [f"font-weight:700; color:{CARBON}; border-top:2px solid {CARBON};"] * len(row)
        color = ROJO if row["Monto"] < 0 else GRIS_TEXTO
        return [f"color:{color}"] * len(row)

    return df_cascada.style.format({"Monto": fmt_pesos}, na_rep="—").apply(_fila, axis=1)


def preparar_hoja_cruda(df: pd.DataFrame) -> pd.DataFrame:
    """Tab 'Datos crudos': devuelve la hoja tal cual, salvo la columna
    'Cliente', que se convierte a entero nullable (Int64) para que se vea
    siempre como entero SIN usar Styler (el Styler con fmt_entero crasheaba
    al renderizar cuando los códigos venían como texto)."""
    df = df.copy()
    if "Cliente" in df.columns:
        df["Cliente"] = pd.to_numeric(df["Cliente"], errors="coerce").astype("Int64")
    return df


def boton_descarga(df, nombre_archivo, label="⬇️ Descargar CSV"):
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=nombre_archivo,
        mime="text/csv",
        type="primary",
    )


def fig_tendencia_mensual(por_mes):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=por_mes["Mes"], y=por_mes["Facturacion Neta"],
        mode="lines+markers", name="Facturación Neta",
        line=dict(color=CARBON, width=2.5), marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=por_mes["Mes"], y=por_mes["Contribución Marginal"],
        mode="lines+markers", name="Contribución Marginal",
        line=dict(color=ROJO, width=2.5), marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(228,3,46,0.08)",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=320, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        yaxis=dict(gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f", automargin=True),
        margin=dict(l=8, r=8, t=36, b=8),
    )
    return fig


def fig_donut(df, categoria, valor, top_n=6):
    d = df[[categoria, valor]].copy().sort_values(valor, ascending=False)
    if len(d) > top_n:
        resto = d.iloc[top_n:][valor].sum()
        d = pd.concat([d.iloc[:top_n], pd.DataFrame({categoria: ["Otros"], valor: [resto]})], ignore_index=True)
    fig = go.Figure(go.Pie(
        labels=d[categoria], values=d[valor], hole=0.55,
        marker=dict(colors=PALETA_CATEGORICA, line=dict(color=BLANCO, width=2)),
        texttemplate="%{label}: %{percent}", textposition="outside",
        hovertemplate="%{label}<br>$ %{value:,.0f} (%{percent})<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(height=320, showlegend=False, margin=dict(l=40, r=40, t=20, b=20))
    return fig


def fig_cascada(df_cascada):
    n = len(df_cascada)
    medidas = ["absolute"] + ["relative"] * (n - 2) + ["total"]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=medidas,
        x=df_cascada["Concepto"], y=df_cascada["Monto"],
        text=[fmt_pesos(v) for v in df_cascada["Monto"]], textposition="outside",
        cliponaxis=False,
        connector=dict(line=dict(color=GRIS_BORDE, width=1)),
        increasing=dict(marker=dict(color=VERDE)),
        decreasing=dict(marker=dict(color=ROJO)),
        totals=dict(marker=dict(color=CARBON)),
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=380, showlegend=False,
        yaxis=dict(gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f", automargin=True),
        xaxis=dict(tickangle=-15, automargin=True),
        margin=dict(l=8, r=8, t=40, b=8),
    )
    return fig


def fig_top_clientes(por_cliente, columna_valor, top_n=10, titulo_eje_x=None):
    d = por_cliente.nlargest(top_n, columna_valor).sort_values(columna_valor, ascending=False).copy()

    # Etiqueta SIEMPRE "código - nombre": un mismo nombre con distinto código
    # es una boca distinta y tiene que verse como cliente distinto.
    nombres = d["Nom.Cliente"].fillna("").astype(str)
    codigos = d["Cliente"].map(fmt_entero)  # Series de strings
    # CORREGIDO: antes se usaba len(codigos), que devuelve la cantidad de
    # filas, no el largo de cada código. Ahora es vectorizado por fila.
    max_largo = 32
    limite_nombre = (max_largo - codigos.str.len() - 4).clip(lower=8)
    nombres_cortos = nombres.where(
        nombres.str.len() <= limite_nombre,
        nombres.str.slice(0, limite_nombre) + "…",
    )
    etiqueta = codigos + " - " + nombres_cortos

    if titulo_eje_x is None:
        titulo_eje_x = "Contribución Marginal ($)" if columna_valor == "CM_pesos" else "Facturación Neta ($)"

    fig = go.Figure(go.Bar(
        x=d[columna_valor], y=etiqueta, orientation="h",
        marker=dict(color=ROJO),
        text=[fmt_pesos(v) for v in d[columna_valor]], textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(280, 34 * len(d)),
        xaxis=dict(
            title=dict(text=titulo_eje_x, font=dict(size=12)),
            gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f", automargin=True,
        ),
        yaxis=dict(title=dict(text="Cliente", font=dict(size=12)), automargin=True,
                   categoryorder="total ascending"),
        margin=dict(l=10, r=100, t=30, b=10),
    )
    return fig


aplicar_estilos()

CONFIG_CHART = {"displayModeBar": False}


# ----------------------------------------------------------------------
# Carga de datos + cálculo de CM  (sin cambios respecto del original)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner="Leyendo, identificando y limpiando las fuentes...")
def cargar(archivos) -> dict[str, pd.DataFrame]:
    """Compatible con un único Excel integral o con múltiples Excel complementarios."""
    return cargar_todo(archivos)


@st.cache_data(show_spinner="Calculando Contribución Marginal...")
def calcular(_datos: dict, pallets_por_camion: int) -> pd.DataFrame:
    return calcular_cmg(_datos, pallets_por_camion=pallets_por_camion)


st.markdown(
    """
    <div class="cmg-encabezado">
        <h1>🥤 AppCMG — Contribución Marginal al detalle</h1>
        <p>Explorá la Contribución Marginal de la operación por artículo, cliente, canal y locación.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown('<span class="cmg-marca">AppCMG</span>', unsafe_allow_html=True)
archivos = st.sidebar.file_uploader(
    "Subí la fuente de datos AppCMG",
    type=["xlsx"],
    accept_multiple_files=True,
    help=(
        "Podés subir el Excel integral actual o varios archivos .xlsx complementarios. "
        "La app identifica las fuentes por nombre de hoja y, cuando es posible, por sus columnas."
    ),
)

if not archivos:
    titulo_panel("Subí los datos para empezar")
    st.info(
        "⬅️ Podés subir **un único Excel integral** (como el AppCMG actual) o **varios Excel**. "
        "Entre todos deben aportar estas 7 fuentes: **VENTA**, **Maestro Artículos**, **Receta**, "
        "**MO**, **DatosxLocacion**, **FletesT0** y **Exhibición**."
    )
    st.stop()

try:
    datos = cargar(archivos)
except Exception as exc:
    st.error(f"No se pudieron procesar las fuentes: {exc}")
    st.stop()

st.sidebar.header("Supuestos")
pallets_por_camion = st.sidebar.number_input(
    "Pallets por camión (Flete T1)",
    min_value=1,
    value=PALLETS_POR_CAMION,
    step=1,
    help="Cantidad de pallets que entran en un camión. Se usa para prorratear el costo de Flete T1 entre las unidades transportadas.",
)

venta_cm = calcular(datos, pallets_por_camion)
maestro = datos["maestro"]
receta = datos["receta"]
mo = datos["mo"]
dxl = datos["datosxlocacion"]
fletest0 = datos["fletest0"]

n_sin_costeo = (~venta_cm["CM_calculada"]).sum()
_n_archivos = len(archivos)
_etiqueta_archivos = "archivo" if _n_archivos == 1 else "archivos"
st.success(
    f"{_n_archivos} {_etiqueta_archivos} procesado{'s' if _n_archivos != 1 else ''}: "
    f"{fmt_n(len(venta_cm))} filas de venta."
)
if n_sin_costeo:
    tipos_sin_costeo = sorted(
        venta_cm.loc[~venta_cm["CM_calculada"], "Tipo de Prod."].dropna().unique()
    )
    st.warning(
        f"⚠️ {fmt_n(n_sin_costeo)} filas son de artículos con Tipo de Prod. {tipos_sin_costeo} "
        "— todavía sin regla de costeo definida (solo P y R están cubiertos). "
        "Quedan afuera de los totales de Contribución Marginal de abajo."
    )

# ----------------------------------------------------------------------
# Filtros globales (barra lateral) — sin cambios
# ----------------------------------------------------------------------
st.sidebar.header("Filtros")

meses_disp = sorted(venta_cm["Mes"].dropna().unique())
meses_sel = st.sidebar.multiselect(
    "Mes",
    options=meses_disp,
    default=meses_disp,
    format_func=lambda m: pd.Timestamp(m).strftime("%Y-%m"),
)
locaciones_sel = st.sidebar.multiselect(
    "Locación", options=sorted(venta_cm["Locación"].dropna().unique())
)
canales_sel = st.sidebar.multiselect(
    "Canal", options=sorted(venta_cm["Canal"].dropna().unique())
)

venta_f = venta_cm[venta_cm["Mes"].isin(meses_sel)]
if locaciones_sel:
    venta_f = venta_f[venta_f["Locación"].isin(locaciones_sel)]
if canales_sel:
    venta_f = venta_f[venta_f["Canal"].isin(canales_sel)]

# Solo filas con CM calculada para los totales/rankings de contribución marginal
venta_cm_f = venta_f[venta_f["CM_calculada"]]


def resumen_cm(df: pd.DataFrame, agrupar_por) -> pd.DataFrame:
    """Agrupa y arma Facturación Neta, CM $ y CM % (ponderado, no promedio simple)."""
    g = df.groupby(agrupar_por, as_index=False).agg(
        Facturacion_Neta=("Facturacion Neta", "sum"),
        Cajas_Fisicas=("Cajas Fisicas", "sum"),
        CM_pesos=("CM ($)", "sum"),
        Clientes=("Cliente", "nunique"),
    )
    # División protegida: si una agrupación tiene Facturación Neta = 0, CM_% queda vacío.
    # (No usar pd.NA acá: en pandas 3 convierte la columna a object y .round() explota
    # con "TypeError: type NAType doesn't define __round__ method".)
    g["CM_%"] = (g["CM_pesos"] / g["Facturacion_Neta"] * 100).where(g["Facturacion_Neta"] != 0).round(1)
    return g.sort_values("CM_pesos", ascending=False)


# ----------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------
tab_resumen, tab_articulo, tab_crudo = st.tabs(
    ["📊 Resumen general", "🔎 Detalle por artículo", "🗂️ Datos crudos"]
)

# --- Tab 1: Resumen general ------------------------------------------------
with tab_resumen:
    c1, c2, c3, c4 = st.columns(4)
    fact_total = venta_f["Facturacion Neta"].sum()
    cm_total = venta_cm_f["CM ($)"].sum()
    c1.metric(
        "Facturación Neta", fmt_pesos(fact_total),
        help="Suma de la Facturación Neta de todas las filas filtradas, incluyendo artículos sin regla de costeo definida.",
    )
    c2.metric(
        "Contribución Marginal", fmt_pesos(cm_total),
        help="Suma de la Contribución Marginal solo de las filas con regla de costeo definida (Tipo P o R).",
    )
    fact_cm = venta_cm_f["Facturacion Neta"].sum()
    cm_pct = cm_total / fact_cm * 100 if fact_cm else 0.0
    c3.metric(
        "CM % (ponderado)", f"{fmt_n(cm_pct, 1)}%",
        help="CM total dividida por la Facturación Neta de las filas con CM calculada (no por el total general de la primera tarjeta).",
    )
    c4.metric(
        "Clientes distintos", fmt_n(venta_f["Cliente"].nunique()),
        help="Clientes únicos en las filas filtradas (todas, no solo las que tienen CM calculada).",
    )

    divisor()
    titulo_panel("Tendencia mensual", "Evolución de la Facturación Neta y la Contribución Marginal, mes a mes.")
    por_mes = venta_f.groupby("Mes", as_index=False)["Facturacion Neta"].sum()
    if por_mes.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        # CORREGIDO: antes se asignaba .values por posición y, si faltaba un
        # mes en venta_cm_f, la CM se desalineaba. Ahora se alinea por mes.
        cm_por_mes = venta_cm_f.groupby("Mes")["CM ($)"].sum()
        por_mes["Contribución Marginal"] = por_mes["Mes"].map(cm_por_mes).fillna(0)
        por_mes["Mes"] = por_mes["Mes"].dt.strftime("%Y-%m")
        st.plotly_chart(fig_tendencia_mensual(por_mes), width="stretch", theme=None, config=CONFIG_CHART)

    divisor()
    col_a, col_b = st.columns(2)
    with col_a:
        titulo_panel("Contribución Marginal por Canal", "Participación de cada canal en la CM total del período filtrado.")
        resumen_canal = resumen_cm(venta_cm_f, "Canal")
        if resumen_canal.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            st.plotly_chart(fig_donut(resumen_canal, "Canal", "CM_pesos"), width="stretch", theme=None, config=CONFIG_CHART)
            with st.expander("Ver tabla completa"):
                st.dataframe(estilo_resumen(resumen_canal), width="stretch", hide_index=True)
                boton_descarga(resumen_canal, "cm_por_canal.csv")
    with col_b:
        titulo_panel("Contribución Marginal por Locación", "Participación de cada locación en la CM total del período filtrado.")
        resumen_locacion = resumen_cm(venta_cm_f, "Locación")
        if resumen_locacion.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            st.plotly_chart(fig_donut(resumen_locacion, "Locación", "CM_pesos"), width="stretch", theme=None, config=CONFIG_CHART)
            with st.expander("Ver tabla completa"):
                st.dataframe(estilo_resumen(resumen_locacion), width="stretch", hide_index=True)
                boton_descarga(resumen_locacion, "cm_por_locacion.csv")

# --- Tab 2: Detalle por artículo -------------------------------------------
with tab_articulo:
    articulos_disp = (
        venta_f[["Cod. Venta", "Descripción del material"]]
        .drop_duplicates()
        .sort_values("Cod. Venta")
    )
    # CORREGIDO: antes había un st.stop() acá, que cortaba TODA la app
    # (incluido el tab de datos crudos). Ahora solo se oculta el contenido.
    if articulos_disp.empty:
        st.warning("No hay artículos para los filtros seleccionados.")
    else:
        opciones = {
            f"{row['Cod. Venta']} - {row['Descripción del material']}": row["Cod. Venta"]
            for _, row in articulos_disp.iterrows()
        }
        elegido = st.selectbox("Elegí un artículo", options=list(opciones.keys()))
        cod = opciones[elegido]

        v_art = venta_f[venta_f["Cod. Venta"] == cod]
        info_art = maestro[maestro["Cod. Venta"] == cod]
        tipo_prod = info_art["Tipo de Prod."].iloc[0] if not info_art.empty else "?"
        calculable = tipo_prod in ("P", "R")

        st.markdown(
            f'<span class="cmg-panel-titulo" style="font-size:1.15rem;">Artículo {cod} &nbsp;{badge_tipo_prod(tipo_prod)}</span>',
            unsafe_allow_html=True,
        )
        st.caption("P = artículo propio, R = artículo de reventa.")
        if not calculable:
            st.warning(
                f"Tipo de producto '{tipo_prod}' todavía no tiene regla de costeo "
                "(solo P y R están definidos) — se muestra la venta, sin CM."
            )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Facturación Neta", fmt_pesos(v_art["Facturacion Neta"].sum()),
            help="Facturación neta de este artículo en el período y los filtros seleccionados.",
        )
        c2.metric(
            "Cajas Físicas", fmt_n(v_art["Cajas Fisicas"].sum()),
            help="Cajas físicas vendidas de este artículo en el período y los filtros seleccionados.",
        )
        if calculable:
            cm_art = v_art["CM ($)"].sum()
            fact_art = v_art["Facturacion Neta"].sum()
            cm_pct_art = cm_art / fact_art * 100 if fact_art else 0.0
            c3.metric("Contribución Marginal", fmt_pesos(cm_art))
            c4.metric("CM %", f"{fmt_n(cm_pct_art, 1)}%")
        else:
            c3.metric("Contribución Marginal", "—", help="No disponible: este tipo de producto todavía no tiene regla de costeo.")
            c4.metric("CM %", "—", help="No disponible: este tipo de producto todavía no tiene regla de costeo.")

        if calculable:
            divisor()
            titulo_panel("Cascada de Contribución Marginal", "De la Facturación Neta a la Contribución Marginal, paso a paso, para este artículo.")
            cascada = v_art[COLUMNAS_CASCADA].sum()
            filas_cascada = [{"Concepto": "Facturación Neta", "Monto": cascada["Facturacion Neta"]}]
            for c in COLUMNAS_CASCADA[1:-1]:
                filas_cascada.append({"Concepto": f"(–) {c}", "Monto": -cascada[c]})
            filas_cascada.append({"Concepto": "= Contribución Marginal ($)", "Monto": cascada["CM ($)"]})
            df_cascada = pd.DataFrame(filas_cascada)

            with st.container(border=True):
                st.plotly_chart(fig_cascada(df_cascada), width="stretch", theme=None, config=CONFIG_CHART)
                st.dataframe(estilo_cascada(df_cascada), width="stretch", hide_index=True)

        divisor()
        titulo_panel("Detalle por Cliente")
        cols_cliente = ["Cliente", "Nom.Cliente", "Canal", "Locación"]
        agg_cliente = dict(
            Cajas_Fisicas=("Cajas Fisicas", "sum"), Facturacion_Neta=("Facturacion Neta", "sum")
        )
        if calculable:
            agg_cliente["CM_pesos"] = ("CM ($)", "sum")
        por_cliente = v_art.groupby(cols_cliente, as_index=False).agg(**agg_cliente)
        if calculable:
            por_cliente["CM_%"] = (
                por_cliente["CM_pesos"] / por_cliente["Facturacion_Neta"] * 100
            ).where(por_cliente["Facturacion_Neta"] != 0).round(1)
        por_cliente = por_cliente.sort_values("Facturacion_Neta", ascending=False)

        columna_top = "CM_pesos" if calculable else "Facturacion_Neta"
        etiqueta_top = "Contribución Marginal" if calculable else "Facturación Neta"
        st.caption(f"Top {min(10, len(por_cliente))} clientes por {etiqueta_top}")
        if por_cliente.empty:
            st.info("No hay ventas de este artículo para los filtros seleccionados.")
        else:
            st.plotly_chart(
                fig_top_clientes(por_cliente, columna_top, titulo_eje_x=etiqueta_top + " ($)"),
                width="stretch", theme=None, config=CONFIG_CHART,
            )

            with st.expander(f"Ver el detalle completo de los {len(por_cliente)} clientes"):
                st.dataframe(estilo_resumen(por_cliente) if calculable else por_cliente, width="stretch", hide_index=True)
                boton_descarga(por_cliente, f"detalle_clientes_{cod}.csv")

        divisor()
        col_a, col_b = st.columns(2)
        with col_a:
            titulo_panel("Resumen por Locación")
            st.dataframe(
                estilo_resumen(resumen_cm(v_art, "Locación")) if calculable
                else v_art.groupby("Locación", as_index=False)["Facturacion Neta"].sum(),
                width="stretch", hide_index=True,
            )
        with col_b:
            titulo_panel("Resumen por Canal")
            st.dataframe(
                estilo_resumen(resumen_cm(v_art, "Canal")) if calculable
                else v_art.groupby("Canal", as_index=False)["Facturacion Neta"].sum(),
                width="stretch", hide_index=True,
            )

        st.divider()
        with st.expander("Ver los insumos de costo que alimentan este cálculo"):
            if tipo_prod == "P":
                st.caption("Artículo propio (P) → composición por insumos, hoja Receta:")
                st.dataframe(receta[receta["Cod. Venta"] == cod], width="stretch", hide_index=True)
                mo_art = mo[mo["Cod. Venta"] == cod]
                if not mo_art.empty:
                    st.caption("Mano de Obra (hoja MO):")
                    st.dataframe(mo_art, width="stretch", hide_index=True)
            elif tipo_prod == "R":
                st.caption("Artículo de reventa (R) → costo de compra, hoja Receta:")
                rec_r = receta[receta["Cod. Venta"] == cod]
                # CORREGIDO: solo se seleccionan las columnas que realmente
                # existen (antes un nombre distinto en el Excel tiraba KeyError).
                cols_r = ["Mes", "Costo Compra ($)", "Desperdicio PT (%)", "Desperdicio PT ($)"]
                cols_r = [c for c in cols_r if c in rec_r.columns]
                st.dataframe(rec_r[cols_r] if cols_r else rec_r, width="stretch", hide_index=True)
                st.caption("Flete T0 (ir a buscar el producto), hoja FletesT0:")
                st.dataframe(fletest0[fletest0["Cod. Venta"] == cod], width="stretch", hide_index=True)

            st.caption("Datos por Locación aplicables (hoja DatosxLocacion):")
            st.dataframe(
                dxl[dxl["Locación"].isin(v_art["Locación"].unique())],
                width="stretch", hide_index=True,
            )

# --- Tab 3: Datos crudos ----------------------------------------------------
with tab_crudo:
    opciones_hojas = {**datos, "venta (con CM calculada)": venta_cm}
    hoja = st.selectbox("Elegí una hoja", options=list(opciones_hojas.keys()))
    # CORREGIDO: ya no se usa Styler (crasheaba al renderizar porque
    # fmt_entero explotaba con códigos de cliente en formato texto).
    # Ahora la columna "Cliente" se convierte a Int64 y se muestra directo.
    df_hoja = preparar_hoja_cruda(opciones_hojas[hoja])
    st.dataframe(df_hoja, width="stretch")
    col_info, col_btn = st.columns([3, 1])
    col_info.caption(f"{fmt_n(df_hoja.shape[0])} filas x {df_hoja.shape[1]} columnas")
    with col_btn:
        boton_descarga(df_hoja, f"{str(hoja).replace(' ', '_')}.csv")
