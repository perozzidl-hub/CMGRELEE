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

        .cmg-section-label {{
            text-transform: uppercase; letter-spacing: .08em; font-size: .72rem;
            font-weight: 700; color: {GRIS_TEXTO}; margin-bottom: 3px;
        }}
        .cmg-insight {{
            background: {BLANCO}; border: 1px solid {GRIS_BORDE}; border-radius: 10px;
            padding: 14px 16px; min-height: 92px; height: 100%;
        }}
        .cmg-insight strong {{ color: {CARBON}; font-size: .92rem; }}
        .cmg-insight p {{ color: {GRIS_TEXTO}; margin: 5px 0 0 0; font-size: .84rem; line-height: 1.35; }}
        .cmg-status-ok {{ color: {VERDE}; font-weight: 700; }}
        .cmg-status-warn {{ color: {DORADO}; font-weight: 700; }}
        .cmg-status-bad {{ color: {ROJO}; font-weight: 700; }}
        .cmg-kpi-caption {{ color: {GRIS_TEXTO}; font-size: .74rem; margin-top: -8px; }}
        .cmg-breadcrumb {{
            background: {BLANCO}; border: 1px solid {GRIS_BORDE}; border-radius: 8px;
            padding: 9px 12px; color: {GRIS_TEXTO}; font-size: .82rem; margin: 4px 0 14px 0;
        }}
        .cmg-breadcrumb strong {{ color: {CARBON}; }}

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
    """Tendencia mensual legible incluso cuando hay uno o dos meses.

    Forzamos el eje X a categórico para que valores como ``2026-07`` no sean
    reinterpretados por Plotly como fechas continuas. Esto evita que, con un
    único mes, aparezca un rango artificial de días/semanas alrededor del dato.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=por_mes["Mes"], y=por_mes["Facturacion Neta"],
        mode="lines+markers", name="Facturación Neta",
        line=dict(color=CARBON, width=2.5), marker=dict(size=7),
    ))
    fig.add_trace(go.Scatter(
        x=por_mes["Mes"], y=por_mes["Contribución Marginal"],
        mode="lines+markers", name="Contribución Marginal",
        line=dict(color=ROJO, width=2.5), marker=dict(size=7),
        fill="tozeroy", fillcolor="rgba(228,3,46,0.08)",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=370, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        xaxis=dict(type="category", title=None, automargin=True, tickangle=0),
        yaxis=dict(
            gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f",
            automargin=True, separatethousands=True, zeroline=True,
        ),
        margin=dict(l=95, r=35, t=50, b=55),
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
    #
    # IMPORTANTE: no usar .str.slice(0, Series). Pandas/PyArrow exigen que
    # ``stop`` sea un entero escalar y Streamlit Cloud puede usar el backend
    # Arrow para strings. El truncado se hace fila por fila para que funcione
    # igual con pandas 2.x/3.x y cualquier backend de strings.
    nombres = d["Nom.Cliente"].fillna("").map(str)
    codigos = d["Cliente"].map(fmt_entero).map(str)
    max_largo = 32

    etiquetas = []
    for codigo, nombre in zip(codigos.tolist(), nombres.tolist()):
        limite_nombre = max(8, max_largo - len(codigo) - 4)
        nombre_corto = nombre if len(nombre) <= limite_nombre else nombre[:limite_nombre] + "…"
        etiquetas.append(f"{codigo} - {nombre_corto}")

    etiqueta = pd.Series(etiquetas, index=d.index, dtype="object")

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


def _delta_pct(actual, anterior):
    """Variación porcentual segura. Devuelve None si no hay base comparable."""
    try:
        actual = float(actual)
        anterior = float(anterior)
    except (TypeError, ValueError):
        return None
    if anterior == 0 or pd.isna(anterior):
        return None
    return (actual / anterior - 1) * 100


def _delta_pp(actual, anterior):
    try:
        return float(actual) - float(anterior)
    except (TypeError, ValueError):
        return None


def _texto_delta(valor, sufijo="%"):
    if valor is None or pd.isna(valor):
        return None
    signo = "+" if valor > 0 else ""
    return f"{signo}{fmt_n(valor, 1)}{sufijo} vs período anterior"


def fig_barras_cm(df, categoria, top_n=10):
    """Barras divergentes de CM: admite correctamente valores negativos."""
    d = df.copy().sort_values("CM_pesos", ascending=False)
    if len(d) > top_n:
        # Conserva los extremos: mejores y peores, evitando esconder CM negativa.
        n_pos = max(1, top_n // 2)
        n_neg = top_n - n_pos
        idx = list(d.head(n_pos).index) + list(d.tail(n_neg).index)
        d = d.loc[list(dict.fromkeys(idx))].sort_values("CM_pesos", ascending=True)
    else:
        d = d.sort_values("CM_pesos", ascending=True)

    colores = [VERDE if v >= 0 else ROJO for v in d["CM_pesos"]]
    custom = d[["Facturacion_Neta", "CM_%", "Cajas_Fisicas"]].to_numpy()
    fig = go.Figure(go.Bar(
        x=d["CM_pesos"], y=d[categoria].astype(str), orientation="h",
        marker=dict(color=colores),
        customdata=custom,
        hovertemplate=(
            "<b>%{y}</b><br>CM: $ %{x:,.0f}<br>"
            "Facturación: $ %{customdata[0]:,.0f}<br>"
            "CM %: %{customdata[1]:.1f}%<br>"
            "Cajas: %{customdata[2]:,.0f}<extra></extra>"
        ),
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(310, 34 * len(d)), showlegend=False,
        xaxis=dict(title="Contribución Marginal ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=8, r=25, t=20, b=35),
    )
    fig.add_vline(x=0, line_width=1, line_color=CARBON)
    return fig


def fig_matriz_rentabilidad(productos):
    """Matriz volumen x rentabilidad. Cada burbuja es un SKU."""
    d = productos.copy()
    d = d[(d["Cajas_Fisicas"] > 0) & d["CM_%"].notna()].copy()
    if d.empty:
        return go.Figure()

    # Tamaño acotado para que una venta extrema no opaque todo el gráfico.
    fact_pos = d["Facturacion_Neta"].clip(lower=0)
    max_fact = fact_pos.max()
    tamanos = 14 + (fact_pos / max_fact * 34 if max_fact else 0)
    colores = [VERDE if v >= 0 else ROJO for v in d["CM_%"]]
    custom = d[["Cod. Venta", "Descripción del material", "Facturacion_Neta", "CM_pesos"]].to_numpy()

    # Cuando quedan pocos SKU, mostrar el código junto a la burbuja aporta más
    # que dejar grandes áreas vacías sin identificación visual.
    mostrar_etiquetas = len(d) <= 12
    modo = "markers+text" if mostrar_etiquetas else "markers"
    textos = d["Cod. Venta"].map(fmt_entero) if mostrar_etiquetas else None

    fig = go.Figure(go.Scatter(
        x=d["Cajas_Fisicas"], y=d["CM_%"], mode=modo,
        text=textos, textposition="top center", textfont=dict(size=11, color=CARBON),
        marker=dict(size=tamanos, color=colores, opacity=0.72, line=dict(width=1, color=BLANCO)),
        customdata=custom,
        hovertemplate=(
            "<b>%{customdata[0]} - %{customdata[1]}</b><br>"
            "Cajas: %{x:,.0f}<br>CM %: %{y:.1f}%<br>"
            "Facturación: $ %{customdata[2]:,.0f}<br>CM: $ %{customdata[3]:,.0f}<extra></extra>"
        ),
    ))
    med_x = d["Cajas_Fisicas"].median()
    med_y = d["CM_%"].median()
    fig.add_vline(x=med_x, line_dash="dot", line_color=GRIS_TEXTO, opacity=.65)
    fig.add_hline(y=med_y, line_dash="dot", line_color=GRIS_TEXTO, opacity=.65)
    fig.add_hline(y=0, line_width=1.4, line_color=ROJO, opacity=.75)
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=540,
        xaxis=dict(
            title="Volumen (Cajas Físicas)", gridcolor=GRIS_BORDE,
            tickformat=",.0f", automargin=True, separatethousands=True,
        ),
        yaxis=dict(
            title="CM %", gridcolor=GRIS_BORDE, ticksuffix="%",
            tickformat=".1f", automargin=True,
        ),
        margin=dict(l=90, r=40, t=45, b=70),
        showlegend=False,
    )
    return fig


def fig_ranking_productos(productos, mejores=True, top_n=10):
    d = productos.copy()
    if mejores:
        d = d.nlargest(top_n, "CM_pesos").sort_values("CM_pesos", ascending=True)
    else:
        d = d.nsmallest(top_n, "CM_pesos").sort_values("CM_pesos", ascending=False)

    etiquetas = []
    for _, row in d.iterrows():
        desc = str(row.get("Descripción del material", ""))
        if len(desc) > 30:
            desc = desc[:29] + "…"
        etiquetas.append(f"{fmt_entero(row['Cod. Venta'])} - {desc}")
    color = VERDE if mejores else ROJO
    fig = go.Figure(go.Bar(
        x=d["CM_pesos"], y=etiquetas, orientation="h", marker=dict(color=color),
        customdata=d[["CM_%", "Facturacion_Neta", "Cajas_Fisicas"]].to_numpy(),
        hovertemplate=(
            "<b>%{y}</b><br>CM: $ %{x:,.0f}<br>CM %: %{customdata[0]:.1f}%<br>"
            "Facturación: $ %{customdata[1]:,.0f}<br>Cajas: %{customdata[2]:,.0f}<extra></extra>"
        ),
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(330, 33 * len(d)), showlegend=False,
        xaxis=dict(title="Contribución Marginal ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=8, r=25, t=15, b=35),
    )
    return fig


def fig_pareto(productos):
    """Pareto sobre CM positiva para mostrar concentración de generación de margen."""
    d = productos[productos["CM_pesos"] > 0].copy().sort_values("CM_pesos", ascending=False)
    if d.empty:
        return go.Figure()
    d["Acum_%"] = d["CM_pesos"].cumsum() / d["CM_pesos"].sum() * 100
    d = d.head(min(30, len(d))).copy()
    etiquetas = d["Cod. Venta"].map(fmt_entero)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=etiquetas, y=d["CM_pesos"], name="CM ($)", marker=dict(color=CARBON),
        hovertemplate="SKU %{x}<br>CM: $ %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=etiquetas, y=d["Acum_%"], name="CM acumulada %", yaxis="y2",
        mode="lines+markers", line=dict(color=ROJO, width=2.2), marker=dict(size=6),
        hovertemplate="SKU %{x}<br>CM acumulada: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=80, yref="y2", line_dash="dot", line_color=DORADO)
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=470, hovermode="x unified",
        # Los códigos son identificadores, no magnitudes. Forzar category evita
        # que Plotly los trate como números y dibuje barras con anchos absurdos.
        xaxis=dict(
            type="category", title="SKU (ordenados por CM)", tickangle=-45,
            automargin=True, categoryorder="array", categoryarray=list(etiquetas),
        ),
        yaxis=dict(
            title="CM ($)", gridcolor=GRIS_BORDE, tickprefix="$ ",
            tickformat="~s", automargin=True, separatethousands=True,
        ),
        yaxis2=dict(
            title="CM acumulada %", overlaying="y", side="right", range=[0, 105],
            ticksuffix="%", tickformat=".0f", automargin=True,
            tickmode="array", tickvals=[0, 20, 40, 60, 80, 100],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0),
        margin=dict(l=100, r=90, t=60, b=95),
        bargap=0.18,
    )
    return fig



def fig_matriz_clientes(clientes, max_puntos=1200):
    """Mapa volumen x margen para clientes. Limita solo la visual, no los cálculos."""
    d = clientes.copy()
    d = d[(d["Cajas_Fisicas"] > 0) & d["CM_%"].notna()].copy()
    if d.empty:
        return go.Figure(), 0
    total = len(d)
    if total > max_puntos:
        d = d.nlargest(max_puntos, "Facturacion_Neta").copy()

    fact_pos = d["Facturacion_Neta"].clip(lower=0)
    max_fact = fact_pos.max()
    tamanos = 8 + (fact_pos / max_fact * 26 if max_fact else 0)
    colores = [VERDE if v >= 0 else ROJO for v in d["CM_%"]]
    custom = d[["Cliente", "Nom.Cliente", "Canal", "Locación", "Facturacion_Neta", "CM_pesos"]].to_numpy()

    fig = go.Figure(go.Scattergl(
        x=d["Cajas_Fisicas"], y=d["CM_%"], mode="markers",
        marker=dict(size=tamanos, color=colores, opacity=.58, line=dict(width=.5, color=BLANCO)),
        customdata=custom,
        hovertemplate=(
            "<b>%{customdata[0]} - %{customdata[1]}</b><br>"
            "Canal: %{customdata[2]}<br>Locación: %{customdata[3]}<br>"
            "Cajas: %{x:,.0f}<br>CM %: %{y:.1f}%<br>"
            "Facturación: $ %{customdata[4]:,.0f}<br>CM: $ %{customdata[5]:,.0f}<extra></extra>"
        ),
    ))
    med_x = d["Cajas_Fisicas"].median()
    med_y = d["CM_%"].median()
    fig.add_vline(x=med_x, line_dash="dot", line_color=GRIS_TEXTO, opacity=.55)
    fig.add_hline(y=med_y, line_dash="dot", line_color=GRIS_TEXTO, opacity=.55)
    fig.add_hline(y=0, line_width=1.4, line_color=ROJO, opacity=.8)
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=500, showlegend=False,
        xaxis=dict(title="Volumen (Cajas Físicas)", gridcolor=GRIS_BORDE, tickformat=",.0f"),
        yaxis=dict(title="CM %", gridcolor=GRIS_BORDE, ticksuffix="%"),
        margin=dict(l=15, r=15, t=25, b=45),
    )
    return fig, total


def fig_ranking_clientes_cmg(clientes, mejores=True, top_n=12):
    d = clientes.copy()
    if d.empty:
        return go.Figure()
    if mejores:
        d = d.nlargest(top_n, "CM_pesos").sort_values("CM_pesos", ascending=True)
    else:
        d = d.nsmallest(top_n, "CM_pesos").sort_values("CM_pesos", ascending=False)

    etiquetas = []
    for _, row in d.iterrows():
        cod = fmt_entero(row["Cliente"])
        nom = str(row.get("Nom.Cliente", ""))
        if len(nom) > 28:
            nom = nom[:27] + "…"
        etiquetas.append(f"{cod} - {nom}")
    colores = [VERDE if v >= 0 else ROJO for v in d["CM_pesos"]]
    fig = go.Figure(go.Bar(
        x=d["CM_pesos"], y=etiquetas, orientation="h", marker=dict(color=colores),
        customdata=d[["CM_%", "Facturacion_Neta", "Cajas_Fisicas", "Canal", "Locación"]].to_numpy(),
        hovertemplate=(
            "<b>%{y}</b><br>CM: $ %{x:,.0f}<br>CM %: %{customdata[0]:.1f}%<br>"
            "Facturación: $ %{customdata[1]:,.0f}<br>Cajas: %{customdata[2]:,.0f}<br>"
            "Canal: %{customdata[3]}<br>Locación: %{customdata[4]}<extra></extra>"
        ),
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(350, 32 * len(d)), showlegend=False,
        xaxis=dict(title="Contribución Marginal ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=8, r=20, t=15, b=35),
    )
    fig.add_vline(x=0, line_width=1, line_color=CARBON)
    return fig


def fig_costos_scope(df_scope, top_n=12):
    """Estructura de costos agregada para cualquier selección de filas costeadas."""
    if df_scope.empty:
        return go.Figure()
    cols_costos = [c for c in COLUMNAS_CASCADA[1:-1] if c in df_scope.columns]
    if not cols_costos:
        return go.Figure()
    valores = pd.to_numeric(df_scope[cols_costos].sum(), errors="coerce").fillna(0)
    d = pd.DataFrame({"Concepto": valores.index, "Monto": valores.values})
    d = d[d["Monto"].abs() > 0].copy()
    if d.empty:
        return go.Figure()
    d["Abs"] = d["Monto"].abs()
    d = d.nlargest(top_n, "Abs").sort_values("Abs", ascending=True)
    fact = pd.to_numeric(df_scope["Facturacion Neta"], errors="coerce").sum()
    d["Pct_fact"] = d["Monto"] / fact * 100 if fact else 0.0
    colores = [ROJO if v >= 0 else VERDE for v in d["Monto"]]
    fig = go.Figure(go.Bar(
        x=d["Monto"], y=d["Concepto"], orientation="h", marker=dict(color=colores),
        customdata=d[["Pct_fact"]].to_numpy(),
        hovertemplate="<b>%{y}</b><br>Costo: $ %{x:,.0f}<br>% Facturación: %{customdata[0]:.1f}%<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(350, 31 * len(d)), showlegend=False,
        xaxis=dict(title="Costo ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=8, r=20, t=15, b=35),
    )
    return fig


def fig_mix_productos(productos, top_n=12):
    """Mix de productos por facturación, con margen suficiente para leer etiquetas."""
    if productos.empty:
        return go.Figure()
    d = productos.nlargest(top_n, "Facturacion_Neta").sort_values("Facturacion_Neta", ascending=True).copy()
    etiquetas = []
    for _, row in d.iterrows():
        desc = str(row.get("Descripción del material", ""))
        if len(desc) > 34:
            desc = desc[:33] + "…"
        etiquetas.append(f"{fmt_entero(row['Cod. Venta'])} - {desc}")
    colores = [VERDE if v >= 0 else ROJO for v in d["CM_pesos"]]
    fig = go.Figure(go.Bar(
        x=d["Facturacion_Neta"], y=etiquetas, orientation="h", marker=dict(color=colores),
        text=[fmt_pesos(v) for v in d["Facturacion_Neta"]], textposition="outside", cliponaxis=False,
        customdata=d[["CM_pesos", "CM_%", "Cajas_Fisicas"]].to_numpy(),
        hovertemplate=(
            "<b>%{y}</b><br>Facturación: $ %{x:,.0f}<br>CM: $ %{customdata[0]:,.0f}<br>"
            "CM %: %{customdata[1]:.1f}%<br>Cajas: %{customdata[2]:,.0f}<extra></extra>"
        ),
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(330, 44 * len(d) + 100), showlegend=False,
        xaxis=dict(
            title="Facturación Neta ($)", gridcolor=GRIS_BORDE, tickprefix="$ ",
            tickformat=",.0f", automargin=True, separatethousands=True,
        ),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=25, r=120, t=25, b=75),
    )
    return fig



# ----------------------------------------------------------------------
# FASE 3 — COSTOS Y EXPLICACIÓN DE VARIACIONES
# ----------------------------------------------------------------------
COSTOS_CMG = [c for c in COLUMNAS_CASCADA if c not in ("Facturacion Neta", "CM ($)")]


def _suma_num(df: pd.DataFrame, columna: str) -> float:
    if df is None or df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())


def resumen_costos_periodo(df_cm: pd.DataFrame) -> pd.DataFrame:
    """Estructura de costos del alcance costeado, en $ / caja / % facturación."""
    fact = _suma_num(df_cm, "Facturacion Neta")
    cajas = _suma_num(df_cm, "Cajas Fisicas")
    filas = []
    for c in COSTOS_CMG:
        costo = _suma_num(df_cm, c)
        filas.append({
            "Concepto": c.replace("Costo ", ""),
            "Columna": c,
            "Costo": costo,
            "Costo_Caja": costo / cajas if cajas else float("nan"),
            "%_Facturacion": costo / fact * 100 if fact else float("nan"),
        })
    return pd.DataFrame(filas).sort_values("Costo", ascending=False)



def fig_estructura_costos(costos: pd.DataFrame, top_n=15):
    """Composición actual del costo en barras horizontales."""
    if costos is None or costos.empty:
        return go.Figure()
    d = costos.copy().nlargest(top_n, "Costo").sort_values("Costo", ascending=True)
    fig = go.Figure(go.Bar(
        x=d["Costo"], y=d["Concepto"], orientation="h", marker=dict(color=CARBON),
        customdata=d[["Costo_Caja", "%_Facturacion"]].to_numpy(),
        hovertemplate=(
            "<b>%{y}</b><br>Costo: $ %{x:,.0f}<br>"
            "Costo/Caja: $ %{customdata[0]:,.2f}<br>"
            "% Facturación: %{customdata[1]:.2f}%<extra></extra>"
        ),
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(410, 30 * len(d)), showlegend=False,
        xaxis=dict(title="Costo total ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=10, r=20, t=15, b=45),
    )
    return fig

def comparar_costos(df_actual_cm: pd.DataFrame, df_anterior_cm: pd.DataFrame) -> pd.DataFrame:
    """Compara cada componente. Impacto_CM > 0 mejora CM; < 0 la deteriora."""
    fact_a = _suma_num(df_actual_cm, "Facturacion Neta")
    fact_p = _suma_num(df_anterior_cm, "Facturacion Neta")
    cajas_a = _suma_num(df_actual_cm, "Cajas Fisicas")
    cajas_p = _suma_num(df_anterior_cm, "Cajas Fisicas")
    filas = []
    for c in COSTOS_CMG:
        actual = _suma_num(df_actual_cm, c)
        anterior = _suma_num(df_anterior_cm, c)
        variacion = actual - anterior
        filas.append({
            "Concepto": c.replace("Costo ", ""),
            "Columna": c,
            "Actual": actual,
            "Anterior": anterior,
            "Variacion_Costo": variacion,
            # Si el costo sube, resta CM; si baja, libera CM.
            "Impacto_CM": -variacion,
            "Actual_Caja": actual / cajas_a if cajas_a else float("nan"),
            "Anterior_Caja": anterior / cajas_p if cajas_p else float("nan"),
            "Var_Caja_%": _delta_pct(actual / cajas_a if cajas_a else float("nan"), anterior / cajas_p if cajas_p else float("nan")),
            "Actual_%Fact": actual / fact_a * 100 if fact_a else float("nan"),
            "Anterior_%Fact": anterior / fact_p * 100 if fact_p else float("nan"),
            "Var_pp": (actual / fact_a * 100 - anterior / fact_p * 100) if fact_a and fact_p else float("nan"),
        })
    return pd.DataFrame(filas)


def fig_bridge_variacion_cm(df_actual_cm: pd.DataFrame, df_anterior_cm: pd.DataFrame, top_n_costos=9):
    """Bridge exacto: CM anterior + ΔFacturación - ΔCostos = CM actual.

    Es una reconciliación aritmética, no una descomposición causal precio/volumen/mix.
    """
    cm_prev = _suma_num(df_anterior_cm, "CM ($)")
    cm_act = _suma_num(df_actual_cm, "CM ($)")
    fact_prev = _suma_num(df_anterior_cm, "Facturacion Neta")
    fact_act = _suma_num(df_actual_cm, "Facturacion Neta")
    delta_fact = fact_act - fact_prev
    comp = comparar_costos(df_actual_cm, df_anterior_cm)
    comp = comp.sort_values("Impacto_CM", key=lambda x: x.abs(), ascending=False)

    principales = comp.head(top_n_costos).copy()
    otros = comp.iloc[top_n_costos:]["Impacto_CM"].sum() if len(comp) > top_n_costos else 0.0

    conceptos = ["CM anterior", "Δ Facturación"]
    valores = [cm_prev, delta_fact]
    medidas = ["absolute", "relative"]
    for _, r in principales.iterrows():
        conceptos.append(r["Concepto"])
        valores.append(r["Impacto_CM"])
        medidas.append("relative")
    if abs(otros) > 0.5:
        conceptos.append("Otros costos")
        valores.append(otros)
        medidas.append("relative")
    conceptos.append("CM actual")
    valores.append(cm_act)
    medidas.append("total")

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=medidas, x=conceptos, y=valores,
        text=[fmt_pesos(v) for v in valores], textposition="outside", cliponaxis=False,
        connector=dict(line=dict(color=GRIS_BORDE, width=1)),
        increasing=dict(marker=dict(color=VERDE)),
        decreasing=dict(marker=dict(color=ROJO)),
        totals=dict(marker=dict(color=CARBON)),
        hovertemplate="%{x}<br>$ %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=470, showlegend=False,
        yaxis=dict(title="Impacto sobre CM ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        xaxis=dict(tickangle=-25, automargin=True),
        margin=dict(l=10, r=10, t=35, b=95),
    )
    return fig


def fig_impacto_costos(comp: pd.DataFrame, top_n=12):
    """Ranking de componentes según cuánto ayudaron/perjudicaron la variación de CM."""
    if comp.empty:
        return go.Figure()
    d = comp.copy()
    d = d.reindex(d["Impacto_CM"].abs().sort_values(ascending=False).index).head(top_n)
    d = d.sort_values("Impacto_CM")
    colores = [VERDE if v >= 0 else ROJO for v in d["Impacto_CM"]]
    fig = go.Figure(go.Bar(
        x=d["Impacto_CM"], y=d["Concepto"], orientation="h", marker=dict(color=colores),
        customdata=d[["Actual", "Anterior", "Variacion_Costo"]].to_numpy(),
        hovertemplate=(
            "<b>%{y}</b><br>Impacto sobre CM: $ %{x:,.0f}<br>"
            "Costo actual: $ %{customdata[0]:,.0f}<br>"
            "Costo anterior: $ %{customdata[1]:,.0f}<br>"
            "Δ costo: $ %{customdata[2]:,.0f}<extra></extra>"
        ),
    ))
    fig.add_vline(x=0, line_width=1, line_color=CARBON)
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(360, 32 * len(d)), showlegend=False,
        xaxis=dict(title="Impacto sobre la variación de CM ($)", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.0f"),
        yaxis=dict(title=None, automargin=True),
        margin=dict(l=10, r=25, t=20, b=45),
    )
    return fig


def fig_costos_unitarios(comp: pd.DataFrame, top_n=10):
    """Costo por caja actual vs anterior, priorizando componentes materiales."""
    if comp.empty:
        return go.Figure()
    d = comp.copy()
    d["materialidad"] = d[["Actual", "Anterior"]].abs().max(axis=1)
    d = d.nlargest(top_n, "materialidad").sort_values("Actual_Caja", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["Anterior_Caja"], y=d["Concepto"], orientation="h", name="Período anterior",
        marker=dict(color="#B9B9B9"),
        hovertemplate="%{y}<br>Anterior: $ %{x:,.2f}/caja<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=d["Actual_Caja"], y=d["Concepto"], orientation="h", name="Período actual",
        marker=dict(color=ROJO),
        hovertemplate="%{y}<br>Actual: $ %{x:,.2f}/caja<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        barmode="group", height=max(390, 34 * len(d)),
        xaxis=dict(title="Costo por Caja Física", gridcolor=GRIS_BORDE, tickprefix="$ ", tickformat=",.2f"),
        yaxis=dict(title=None, automargin=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=20, t=45, b=45),
    )
    return fig


def fig_mix_costos(comp: pd.DataFrame, top_n=10):
    """Peso de cada costo sobre facturación: actual vs anterior."""
    if comp.empty:
        return go.Figure()
    d = comp.copy()
    d["materialidad"] = d[["Actual_%Fact", "Anterior_%Fact"]].abs().max(axis=1)
    d = d.nlargest(top_n, "materialidad").sort_values("Actual_%Fact", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["Anterior_%Fact"], y=d["Concepto"], orientation="h", name="Período anterior",
        marker=dict(color="#B9B9B9"),
        hovertemplate="%{y}<br>Anterior: %{x:.2f}% de facturación<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=d["Actual_%Fact"], y=d["Concepto"], orientation="h", name="Período actual",
        marker=dict(color=CARBON),
        hovertemplate="%{y}<br>Actual: %{x:.2f}% de facturación<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        barmode="group", height=max(390, 34 * len(d)),
        xaxis=dict(title="Costo / Facturación Neta", gridcolor=GRIS_BORDE, ticksuffix="%"),
        yaxis=dict(title=None, automargin=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=20, t=45, b=45),
    )
    return fig


def fig_tendencia_eficiencia(df_cm: pd.DataFrame):
    """Evolución mensual de Costo/Caja y CM/Caja con ejes legibles."""
    if df_cm is None or df_cm.empty:
        return go.Figure()
    d = df_cm.groupby("Mes", as_index=False).agg(
        Facturacion_Neta=("Facturacion Neta", "sum"),
        Cajas_Fisicas=("Cajas Fisicas", "sum"),
        Costo_Total=("Costo Total", "sum"),
        CM_pesos=("CM ($)", "sum"),
    )
    cajas = pd.to_numeric(d["Cajas_Fisicas"], errors="coerce").replace(0, float("nan"))
    fact = pd.to_numeric(d["Facturacion_Neta"], errors="coerce").replace(0, float("nan"))
    d["Costo_Caja"] = pd.to_numeric(d["Costo_Total"], errors="coerce") / cajas
    d["CM_Caja"] = pd.to_numeric(d["CM_pesos"], errors="coerce") / cajas
    d["CM_%"] = pd.to_numeric(d["CM_pesos"], errors="coerce") / fact * 100
    d["Mes_txt"] = pd.to_datetime(d["Mes"]).dt.strftime("%Y-%m")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["Mes_txt"], y=d["Costo_Caja"], mode="lines+markers", name="Costo / Caja",
        line=dict(color=CARBON, width=2.5), marker=dict(size=7),
        hovertemplate="%{x}<br>Costo/Caja: $ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=d["Mes_txt"], y=d["CM_Caja"], mode="lines+markers", name="CM / Caja",
        line=dict(color=ROJO, width=2.5), marker=dict(size=7),
        hovertemplate="%{x}<br>CM/Caja: $ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=450, hovermode="x unified",
        xaxis=dict(type="category", title=None, automargin=True, tickangle=0),
        yaxis=dict(
            title="$ por Caja Física", gridcolor=GRIS_BORDE, tickprefix="$ ",
            tickformat=",.2f", automargin=True, separatethousands=True,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        margin=dict(l=115, r=35, t=55, b=60),
    )
    return fig

def tarjeta_insight(titulo, texto, estado="info"):
    clase = {"ok": "cmg-status-ok", "warn": "cmg-status-warn", "bad": "cmg-status-bad"}.get(estado, "")
    st.markdown(
        f'<div class="cmg-insight"><strong class="{clase}">{titulo}</strong><p>{texto}</p></div>',
        unsafe_allow_html=True,
    )


aplicar_estilos()

CONFIG_CHART = {"displayModeBar": False}


# ----------------------------------------------------------------------
# Carga de datos + cálculo de CM  (sin cambios respecto del original)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner="Leyendo, identificando y limpiando las fuentes...")
def cargar(archivos) -> dict[str, pd.DataFrame]:
    """Compatible con un único Excel integral o con múltiples Excel complementarios.

    Streamlit devuelve SIEMPRE una lista cuando ``accept_multiple_files=True``,
    incluso si el usuario sube un solo archivo. Para mantener compatibilidad
    con el loader histórico (que esperaba un archivo individual), cuando hay
    una sola fuente la desempaquetamos antes de llamar a ``cargar_todo``.
    El loader V2 acepta ambas formas, por lo que esto también funciona con la
    arquitectura multiarchivo nueva.
    """
    if isinstance(archivos, (list, tuple)):
        if len(archivos) == 1:
            return cargar_todo(archivos[0])
        return cargar_todo(list(archivos))
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
# FILTROS GLOBALES
# ----------------------------------------------------------------------
st.sidebar.header("Filtros")

meses_disp = sorted(venta_cm["Mes"].dropna().unique())
locaciones_disp = sorted(venta_cm["Locación"].dropna().unique())
canales_disp = sorted(venta_cm["Canal"].dropna().unique())

# Estado persistente: los botones limpian/restablecen filtros sin tocar el uploader.
if "filtro_meses" not in st.session_state:
    st.session_state.filtro_meses = list(meses_disp)
else:
    st.session_state.filtro_meses = [m for m in st.session_state.filtro_meses if m in meses_disp]
if "filtro_locaciones" not in st.session_state:
    st.session_state.filtro_locaciones = []
else:
    st.session_state.filtro_locaciones = [x for x in st.session_state.filtro_locaciones if x in locaciones_disp]
if "filtro_canales" not in st.session_state:
    st.session_state.filtro_canales = []
else:
    st.session_state.filtro_canales = [x for x in st.session_state.filtro_canales if x in canales_disp]

b1, b2 = st.sidebar.columns(2)
if b1.button("↺ Todo", width="stretch", help="Restablece todos los filtros sin volver a cargar los archivos."):
    st.session_state.filtro_meses = list(meses_disp)
    st.session_state.filtro_locaciones = []
    st.session_state.filtro_canales = []
    st.rerun()
if b2.button("Último mes", width="stretch"):
    st.session_state.filtro_meses = [meses_disp[-1]] if meses_disp else []
    st.session_state.filtro_locaciones = []
    st.session_state.filtro_canales = []
    st.rerun()

meses_sel = st.sidebar.multiselect(
    "Mes", options=meses_disp, key="filtro_meses",
    format_func=lambda m: pd.Timestamp(m).strftime("%Y-%m"),
    help="Si dejás Mes vacío se interpreta como todos los meses.",
)
locaciones_sel = st.sidebar.multiselect("Locación", options=locaciones_disp, key="filtro_locaciones")
canales_sel = st.sidebar.multiselect("Canal", options=canales_disp, key="filtro_canales")

venta_f = venta_cm.copy()
if meses_sel:
    venta_f = venta_f[venta_f["Mes"].isin(meses_sel)]
if locaciones_sel:
    venta_f = venta_f[venta_f["Locación"].isin(locaciones_sel)]
if canales_sel:
    venta_f = venta_f[venta_f["Canal"].isin(canales_sel)]

# Solo filas con CM calculada para métricas/rankings de contribución marginal.
venta_cm_f = venta_f[venta_f["CM_calculada"]].copy()


def porcentaje_seguro(numerador: pd.Series, denominador: pd.Series, decimales=1) -> pd.Series:
    """Porcentaje robusto ante ceros, pd.NA y columnas dtype object."""
    num = pd.to_numeric(numerador, errors="coerce").astype("float64")
    den = pd.to_numeric(denominador, errors="coerce").astype("float64")
    den = den.mask(den == 0)
    return (num.div(den).mul(100)).round(decimales)


def resumen_cm(df: pd.DataFrame, agrupar_por) -> pd.DataFrame:
    """Agrupa Facturación, cajas, CM $ y CM % ponderado."""
    if df.empty:
        cols = ([agrupar_por] if isinstance(agrupar_por, str) else list(agrupar_por)) + [
            "Facturacion_Neta", "Cajas_Fisicas", "CM_pesos", "Clientes", "CM_%"
        ]
        return pd.DataFrame(columns=cols)
    g = df.groupby(agrupar_por, as_index=False, dropna=False).agg(
        Facturacion_Neta=("Facturacion Neta", "sum"),
        Cajas_Fisicas=("Cajas Fisicas", "sum"),
        CM_pesos=("CM ($)", "sum"),
        Clientes=("Cliente", "nunique"),
    )
    g["CM_%"] = porcentaje_seguro(g["CM_pesos"], g["Facturacion_Neta"], 1)
    return g.sort_values("CM_pesos", ascending=False)


def resumen_productos(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Cod. Venta", "Descripción del material"]
    if df.empty:
        return pd.DataFrame(columns=cols + ["Facturacion_Neta", "Cajas_Fisicas", "CM_pesos", "Clientes", "CM_%", "CM_Caja"])
    g = df.groupby(cols, as_index=False, dropna=False).agg(
        Facturacion_Neta=("Facturacion Neta", "sum"),
        Cajas_Fisicas=("Cajas Fisicas", "sum"),
        CM_pesos=("CM ($)", "sum"),
        Clientes=("Cliente", "nunique"),
    )
    g["CM_%"] = porcentaje_seguro(g["CM_pesos"], g["Facturacion_Neta"], 1)
    cajas = pd.to_numeric(g["Cajas_Fisicas"], errors="coerce").replace(0, float("nan"))
    g["CM_Caja"] = pd.to_numeric(g["CM_pesos"], errors="coerce") / cajas
    return g.sort_values("CM_pesos", ascending=False)



def resumen_entidad_integral(df_all: pd.DataFrame, df_cm: pd.DataFrame, agrupar_por, incluir_clientes=False) -> pd.DataFrame:
    """Resumen que conserva facturación total y calcula CM solo sobre filas costeadas.

    Esto evita esconder venta sin regla de costeo y expone explícitamente la cobertura.
    """
    keys = [agrupar_por] if isinstance(agrupar_por, str) else list(agrupar_por)
    columnas = keys + ["Facturacion_Neta", "Cajas_Fisicas", "Facturacion_Costeada", "Cajas_Costeadas", "CM_pesos", "CM_%", "CM_Caja", "Cobertura_%", "SKU"]
    if incluir_clientes:
        columnas.append("Clientes")
    if df_all.empty:
        return pd.DataFrame(columns=columnas)

    agg_all = {
        "Facturacion_Neta": ("Facturacion Neta", "sum"),
        "Cajas_Fisicas": ("Cajas Fisicas", "sum"),
        "SKU": ("Cod. Venta", "nunique"),
    }
    if incluir_clientes:
        agg_all["Clientes"] = ("Cliente", "nunique")
    base = df_all.groupby(keys, as_index=False, dropna=False).agg(**agg_all)

    if df_cm.empty:
        base["Facturacion_Costeada"] = 0.0
        base["Cajas_Costeadas"] = 0.0
        base["CM_pesos"] = 0.0
    else:
        rent = df_cm.groupby(keys, as_index=False, dropna=False).agg(
            Facturacion_Costeada=("Facturacion Neta", "sum"),
            Cajas_Costeadas=("Cajas Fisicas", "sum"),
            CM_pesos=("CM ($)", "sum"),
        )
        base = base.merge(rent, on=keys, how="left")
        for c in ["Facturacion_Costeada", "Cajas_Costeadas", "CM_pesos"]:
            base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0.0)

    base["CM_%"] = porcentaje_seguro(base["CM_pesos"], base["Facturacion_Costeada"], 1)
    cajas_cost = pd.to_numeric(base["Cajas_Costeadas"], errors="coerce").replace(0, float("nan"))
    base["CM_Caja"] = pd.to_numeric(base["CM_pesos"], errors="coerce") / cajas_cost
    base["Cobertura_%"] = porcentaje_seguro(base["Facturacion_Costeada"], base["Facturacion_Neta"], 1)
    return base.sort_values("CM_pesos", ascending=False)


def resumen_clientes_integral(df_all: pd.DataFrame, df_cm: pd.DataFrame) -> pd.DataFrame:
    return resumen_entidad_integral(
        df_all, df_cm, ["Cliente", "Nom.Cliente", "Canal", "Locación"], incluir_clientes=False
    )


def _tendencia_scope(df_all: pd.DataFrame, df_cm: pd.DataFrame) -> pd.DataFrame:
    por_mes = df_all.groupby("Mes", as_index=False)["Facturacion Neta"].sum()
    if por_mes.empty:
        return por_mes
    cm_mes = df_cm.groupby("Mes")["CM ($)"].sum() if not df_cm.empty else pd.Series(dtype=float)
    por_mes["Contribución Marginal"] = por_mes["Mes"].map(cm_mes).fillna(0)
    por_mes["Mes"] = por_mes["Mes"].dt.strftime("%Y-%m")
    return por_mes


def _metricas_scope(df_all: pd.DataFrame, df_cm: pd.DataFrame):
    fact = pd.to_numeric(df_all["Facturacion Neta"], errors="coerce").sum() if not df_all.empty else 0.0
    cajas = pd.to_numeric(df_all["Cajas Fisicas"], errors="coerce").sum() if not df_all.empty else 0.0
    fact_cm = pd.to_numeric(df_cm["Facturacion Neta"], errors="coerce").sum() if not df_cm.empty else 0.0
    cajas_cm = pd.to_numeric(df_cm["Cajas Fisicas"], errors="coerce").sum() if not df_cm.empty else 0.0
    cm = pd.to_numeric(df_cm["CM ($)"], errors="coerce").sum() if not df_cm.empty else 0.0
    cm_pct = cm / fact_cm * 100 if fact_cm else 0.0
    cm_caja = cm / cajas_cm if cajas_cm else 0.0
    cobertura = fact_cm / fact * 100 if fact else 0.0
    return fact, cajas, cm, cm_pct, cm_caja, cobertura


def _tabla_entidad_estilo(df):
    formatos = {}
    for c in ["Facturacion_Neta", "Facturacion_Costeada", "CM_pesos"]:
        if c in df.columns: formatos[c] = fmt_pesos
    for c in ["Cajas_Fisicas", "Cajas_Costeadas", "Clientes", "SKU"]:
        if c in df.columns: formatos[c] = fmt_n
    if "Cliente" in df.columns: formatos["Cliente"] = fmt_entero
    if "CM_%" in df.columns: formatos["CM_%"] = lambda v: f"{fmt_n(v, 1)}%"
    if "Cobertura_%" in df.columns: formatos["Cobertura_%"] = lambda v: f"{fmt_n(v, 1)}%"
    if "CM_Caja" in df.columns: formatos["CM_Caja"] = lambda v: fmt_pesos(v, 2)
    return df.style.format(formatos, na_rep="—")


def _aplicar_filtros_dimension(df, locaciones, canales):
    out = df.copy()
    if locaciones:
        out = out[out["Locación"].isin(locaciones)]
    if canales:
        out = out[out["Canal"].isin(canales)]
    return out


def periodo_anterior_comparable():
    """Devuelve dataset del período inmediatamente anterior si Mes es contiguo."""
    seleccion = sorted(pd.Timestamp(m) for m in (meses_sel or meses_disp))
    if not seleccion:
        return None
    esperado = list(pd.date_range(seleccion[0], periods=len(seleccion), freq="MS"))
    if seleccion != esperado:
        return None
    meses_prev = list(pd.date_range(end=seleccion[0] - pd.offsets.MonthBegin(1), periods=len(seleccion), freq="MS"))
    disponibles = set(pd.Timestamp(m) for m in meses_disp)
    if not set(meses_prev).issubset(disponibles):
        return None
    prev = venta_cm[venta_cm["Mes"].isin(meses_prev)]
    prev = _aplicar_filtros_dimension(prev, locaciones_sel, canales_sel)
    return prev


productos = resumen_productos(venta_cm_f)
resumen_canal = resumen_cm(venta_cm_f, "Canal")
resumen_locacion = resumen_cm(venta_cm_f, "Locación")
clientes = resumen_clientes_integral(venta_f, venta_cm_f)
canales_detalle = resumen_entidad_integral(venta_f, venta_cm_f, "Canal", incluir_clientes=True)
locaciones_detalle = resumen_entidad_integral(venta_f, venta_cm_f, "Locación", incluir_clientes=True)

# Período anterior para deltas ejecutivos.
venta_prev = periodo_anterior_comparable()
venta_prev_cm = venta_prev[venta_prev["CM_calculada"]] if venta_prev is not None else None

# ----------------------------------------------------------------------
# NAVEGACIÓN
# ----------------------------------------------------------------------
tab_resumen, tab_rentabilidad, tab_costos, tab_clientes, tab_canales, tab_locaciones, tab_explorador, tab_articulo, tab_calidad, tab_crudo = st.tabs(
    [
        "🏠 Resumen ejecutivo", "💰 Rentabilidad", "📉 Costos & Variaciones", "👥 Clientes", "🏪 Canales",
        "🏭 Locaciones", "🧭 Explorador", "🔎 Artículo", "✅ Calidad", "🗂️ Datos"
    ]
)

# --- Tab 1: Resumen ejecutivo ---------------------------------------------
with tab_resumen:
    st.markdown('<div class="cmg-section-label">Cockpit de rentabilidad</div>', unsafe_allow_html=True)

    fact_total = venta_f["Facturacion Neta"].sum()
    cm_total = venta_cm_f["CM ($)"].sum()
    fact_cm = venta_cm_f["Facturacion Neta"].sum()
    cm_pct = cm_total / fact_cm * 100 if fact_cm else 0.0
    cajas_total = venta_f["Cajas Fisicas"].sum()
    cm_caja = cm_total / venta_cm_f["Cajas Fisicas"].sum() if venta_cm_f["Cajas Fisicas"].sum() else 0.0
    cobertura = fact_cm / fact_total * 100 if fact_total else 0.0

    delta_fact = delta_cm = delta_cmpct = None
    if venta_prev is not None and not venta_prev.empty:
        fact_prev = venta_prev["Facturacion Neta"].sum()
        cm_prev = venta_prev_cm["CM ($)"].sum()
        fact_prev_cm = venta_prev_cm["Facturacion Neta"].sum()
        cmpct_prev = cm_prev / fact_prev_cm * 100 if fact_prev_cm else 0.0
        delta_fact = _delta_pct(fact_total, fact_prev)
        delta_cm = _delta_pct(cm_total, cm_prev)
        delta_cmpct = _delta_pp(cm_pct, cmpct_prev)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Facturación Neta", fmt_pesos(fact_total), delta=_texto_delta(delta_fact))
    k2.metric("Contribución Marginal", fmt_pesos(cm_total), delta=_texto_delta(delta_cm))
    k3.metric("CM %", f"{fmt_n(cm_pct, 1)}%", delta=_texto_delta(delta_cmpct, " pp"))
    k4.metric("Cajas Físicas", fmt_n(cajas_total), help="Volumen total para los filtros seleccionados.")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("CM por Caja", fmt_pesos(cm_caja, 2), help="CM total / Cajas Físicas de artículos costeados.")
    k6.metric("Clientes", fmt_n(venta_f["Cliente"].nunique()))
    k7.metric("SKU", fmt_n(venta_f["Cod. Venta"].nunique()))
    k8.metric(
        "Cobertura de costeo", f"{fmt_n(cobertura, 1)}%",
        help="Facturación de filas con regla de CM / Facturación total filtrada.",
    )

    divisor()
    titulo_panel("Qué requiere atención", "Hallazgos automáticos derivados de los filtros actuales; no son recomendaciones comerciales automáticas.")

    neg = productos[productos["CM_pesos"] < 0]
    n_neg = len(neg)
    perdida_total = -neg["CM_pesos"].sum() if n_neg else 0.0
    top5_perdida = -neg.nsmallest(5, "CM_pesos")["CM_pesos"].sum() if n_neg else 0.0
    conc_perdida = top5_perdida / perdida_total * 100 if perdida_total else 0.0
    peor_loc = resumen_locacion.sort_values("CM_%").iloc[0] if not resumen_locacion.empty else None

    i1, i2, i3, i4 = st.columns(4)
    with i1:
        tarjeta_insight(
            f"{'Sin' if n_neg == 0 else fmt_n(n_neg)} SKU con CM negativa",
            "No se detectan productos destruyendo margen en el período." if n_neg == 0 else f"La pérdida agregada de esos SKU es {fmt_pesos(perdida_total)}.",
            "ok" if n_neg == 0 else "bad",
        )
    with i2:
        tarjeta_insight(
            "Concentración de pérdidas",
            "No hay pérdida de CM para concentrar." if n_neg == 0 else f"Los 5 SKU más negativos explican {fmt_n(conc_perdida, 1)}% de la pérdida de CM.",
            "ok" if n_neg == 0 else ("bad" if conc_perdida >= 60 else "warn"),
        )
    with i3:
        tarjeta_insight(
            "Cobertura del costeo",
            f"{fmt_n(cobertura, 1)}% de la facturación tiene una regla de CM calculada.",
            "ok" if cobertura >= 99 else ("warn" if cobertura >= 95 else "bad"),
        )
    with i4:
        if peor_loc is None:
            tarjeta_insight("Locaciones", "No hay información para los filtros actuales.", "warn")
        else:
            tarjeta_insight(
                "Menor CM % por locación",
                f"{peor_loc['Locación']}: {fmt_n(peor_loc['CM_%'], 1)}% sobre {fmt_pesos(peor_loc['Facturacion_Neta'])} de facturación.",
                "bad" if peor_loc["CM_%"] < 0 else "warn",
            )

    divisor()
    titulo_panel("Tendencia mensual", "Facturación Neta y Contribución Marginal. Los filtros de Canal y Locación se mantienen.")
    por_mes = venta_f.groupby("Mes", as_index=False)["Facturacion Neta"].sum()
    if por_mes.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        cm_por_mes = venta_cm_f.groupby("Mes")["CM ($)"].sum()
        por_mes["Contribución Marginal"] = por_mes["Mes"].map(cm_por_mes).fillna(0)
        por_mes["Mes"] = por_mes["Mes"].dt.strftime("%Y-%m")
        st.plotly_chart(fig_tendencia_mensual(por_mes), width="stretch", theme=None, config=CONFIG_CHART, key="resumen_tendencia_mensual")

    divisor()
    col_a, col_b = st.columns(2)
    with col_a:
        titulo_panel("Rentabilidad por Canal", "CM positiva y negativa sin distorsiones de un gráfico circular.")
        if resumen_canal.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            st.plotly_chart(fig_barras_cm(resumen_canal, "Canal"), width="stretch", theme=None, config=CONFIG_CHART, key="resumen_cm_canal")
            with st.expander("Ver tabla completa"):
                st.dataframe(estilo_resumen(resumen_canal), width="stretch", hide_index=True)
                boton_descarga(resumen_canal, "cm_por_canal.csv")
    with col_b:
        titulo_panel("Rentabilidad por Locación", "Comparación directa de la CM generada por cada operación.")
        if resumen_locacion.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            st.plotly_chart(fig_barras_cm(resumen_locacion, "Locación"), width="stretch", theme=None, config=CONFIG_CHART, key="resumen_cm_locacion")
            with st.expander("Ver tabla completa"):
                st.dataframe(estilo_resumen(resumen_locacion), width="stretch", hide_index=True)
                boton_descarga(resumen_locacion, "cm_por_locacion.csv")

# --- Tab 2: Rentabilidad ---------------------------------------------------
with tab_rentabilidad:
    titulo_panel("Mapa de rentabilidad de productos", "Cada burbuja es un SKU: volumen en X, CM % en Y y tamaño según facturación. Las líneas punteadas son las medianas del conjunto filtrado.")
    if productos.empty:
        st.info("No hay productos costeados para los filtros seleccionados.")
    else:
        st.plotly_chart(fig_matriz_rentabilidad(productos), width="stretch", theme=None, config=CONFIG_CHART, key="rentabilidad_matriz_productos")

        divisor()
        a, b = st.columns(2)
        with a:
            titulo_panel("Top generadores de CM", "Productos con mayor contribución marginal absoluta.")
            st.plotly_chart(fig_ranking_productos(productos, mejores=True), width="stretch", theme=None, config=CONFIG_CHART, key="rentabilidad_top_productos")
        with b:
            titulo_panel("Productos que destruyen CM", "Los SKU con menor contribución marginal aparecen primero.")
            if (productos["CM_pesos"] < 0).any():
                st.plotly_chart(fig_ranking_productos(productos[productos["CM_pesos"] < 0], mejores=False), width="stretch", theme=None, config=CONFIG_CHART, key="rentabilidad_peores_productos")
            else:
                st.success("No hay SKU con Contribución Marginal negativa para los filtros actuales.")

        divisor()
        titulo_panel("Pareto de generación de margen", "Muestra qué tan concentrada está la CM positiva en los principales SKU.")
        st.plotly_chart(fig_pareto(productos), width="stretch", theme=None, config=CONFIG_CHART, key="rentabilidad_pareto_productos")

        divisor()
        titulo_panel("Tabla ejecutiva de productos", "Ordená y filtrá visualmente para detectar combinaciones de volumen, margen y concentración de clientes.")
        tabla_prod = productos.copy()
        tabla_prod["Estado"] = tabla_prod["CM_pesos"].map(lambda x: "🔴 CM negativa" if x < 0 else "🟢 CM positiva")
        cols = ["Cod. Venta", "Descripción del material", "Facturacion_Neta", "Cajas_Fisicas", "CM_pesos", "CM_%", "CM_Caja", "Clientes", "Estado"]
        st.dataframe(
            tabla_prod[cols].style.format({
                "Cod. Venta": fmt_entero,
                "Facturacion_Neta": fmt_pesos,
                "Cajas_Fisicas": fmt_n,
                "CM_pesos": fmt_pesos,
                "CM_%": lambda v: f"{fmt_n(v, 1)}%",
                "CM_Caja": lambda v: fmt_pesos(v, 2),
                "Clientes": fmt_n,
            }, na_rep="—"),
            width="stretch", hide_index=True, height=520,
        )
        boton_descarga(tabla_prod[cols], "rentabilidad_productos.csv", "⬇️ Descargar análisis de productos")


# --- Tab 3: Costos y Variaciones -------------------------------------------
with tab_costos:
    titulo_panel(
        "Costos y explicación de variaciones",
        "Reconciliá la CM entre períodos y detectá qué componentes de costo presionaron o liberaron margen.",
    )

    # Cuando la selección global tiene una ventana anterior completa, se usa como
    # opción principal. Si no, el modo mes-a-mes permite analizar igualmente.
    _prev_global_ok = venta_prev is not None and not venta_prev.empty
    opciones_modo = ["Período filtrado vs período anterior", "Mes vs mes anterior"]
    modo_default = 0 if _prev_global_ok else 1
    modo_costos = st.radio(
        "Modo de comparación",
        opciones_modo,
        index=modo_default,
        horizontal=True,
        key="costos_modo_comparacion",
        help=(
            "El primer modo toma exactamente los meses de los filtros globales y busca una ventana inmediatamente anterior de igual longitud. "
            "El segundo compara un mes puntual contra el mes calendario anterior."
        ),
    )

    if modo_costos == "Período filtrado vs período anterior":
        actual_scope = venta_f.copy()
        actual_cm_scope = venta_cm_f.copy()
        anterior_scope = venta_prev.copy() if _prev_global_ok else None
        anterior_cm_scope = anterior_scope[anterior_scope["CM_calculada"]].copy() if anterior_scope is not None else None
        meses_actual_txt = sorted(pd.Timestamp(m).strftime("%Y-%m") for m in actual_scope["Mes"].dropna().unique())
        meses_prev_txt = sorted(pd.Timestamp(m).strftime("%Y-%m") for m in anterior_scope["Mes"].dropna().unique()) if anterior_scope is not None else []
        etiqueta_actual = f"Período actual ({meses_actual_txt[0]} a {meses_actual_txt[-1]})" if meses_actual_txt else "Período actual"
        etiqueta_prev = f"Período anterior ({meses_prev_txt[0]} a {meses_prev_txt[-1]})" if meses_prev_txt else "Período anterior"
    else:
        disponibles_ts = sorted(pd.Timestamp(m) for m in meses_disp)
        set_disp = set(disponibles_ts)
        meses_ref = sorted(pd.Timestamp(m) for m in (meses_sel or meses_disp))
        candidatos = [m for m in meses_ref if (m - pd.offsets.MonthBegin(1)) in set_disp]
        if not candidatos:
            candidatos = [m for m in disponibles_ts if (m - pd.offsets.MonthBegin(1)) in set_disp]

        if not candidatos:
            actual_scope = anterior_scope = actual_cm_scope = anterior_cm_scope = None
            etiqueta_actual = etiqueta_prev = ""
            st.warning("No hay dos meses consecutivos disponibles para realizar una comparación mes contra mes.")
        else:
            mes_costos = st.selectbox(
                "Mes actual a analizar",
                options=candidatos,
                index=len(candidatos) - 1,
                format_func=lambda m: pd.Timestamp(m).strftime("%Y-%m"),
                key="costos_mes_actual",
            )
            mes_costos = pd.Timestamp(mes_costos)
            mes_prev_costos = mes_costos - pd.offsets.MonthBegin(1)
            actual_scope = venta_cm[venta_cm["Mes"] == mes_costos].copy()
            anterior_scope = venta_cm[venta_cm["Mes"] == mes_prev_costos].copy()
            actual_scope = _aplicar_filtros_dimension(actual_scope, locaciones_sel, canales_sel)
            anterior_scope = _aplicar_filtros_dimension(anterior_scope, locaciones_sel, canales_sel)
            actual_cm_scope = actual_scope[actual_scope["CM_calculada"]].copy()
            anterior_cm_scope = anterior_scope[anterior_scope["CM_calculada"]].copy()
            etiqueta_actual = f"Mes actual ({mes_costos.strftime('%Y-%m')})"
            etiqueta_prev = f"Mes anterior ({mes_prev_costos.strftime('%Y-%m')})"

    if actual_scope is not None and not actual_scope.empty:
        # Estructura actual siempre visible, incluso si no existe comparación válida.
        fact_a, cajas_a, cm_a, cmpct_a, cmcaja_a, cobertura_a = _metricas_scope(actual_scope, actual_cm_scope)
        costo_a = _suma_num(actual_cm_scope, "Costo Total")
        cajas_cost_a = _suma_num(actual_cm_scope, "Cajas Fisicas")
        costo_caja_a = costo_a / cajas_cost_a if cajas_cost_a else 0.0

        tiene_prev = anterior_scope is not None and anterior_cm_scope is not None and not anterior_scope.empty
        if tiene_prev:
            fact_p, cajas_p, cm_p, cmpct_p, cmcaja_p, cobertura_p = _metricas_scope(anterior_scope, anterior_cm_scope)
            costo_p = _suma_num(anterior_cm_scope, "Costo Total")
            cajas_cost_p = _suma_num(anterior_cm_scope, "Cajas Fisicas")
            costo_caja_p = costo_p / cajas_cost_p if cajas_cost_p else 0.0
        else:
            fact_p = cajas_p = cm_p = cmpct_p = cmcaja_p = cobertura_p = costo_p = costo_caja_p = 0.0

        st.caption(f"**{etiqueta_actual}**" + (f"  vs  **{etiqueta_prev}**" if tiene_prev else ""))

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Facturación costeada", fmt_pesos(_suma_num(actual_cm_scope, "Facturacion Neta")), delta=_texto_delta(_delta_pct(_suma_num(actual_cm_scope, "Facturacion Neta"), _suma_num(anterior_cm_scope, "Facturacion Neta"))) if tiene_prev else None)
        k2.metric("CM", fmt_pesos(cm_a), delta=_texto_delta(_delta_pct(cm_a, cm_p)) if tiene_prev else None)
        k3.metric("CM %", f"{fmt_n(cmpct_a, 1)}%", delta=_texto_delta(_delta_pp(cmpct_a, cmpct_p), " pp") if tiene_prev else None)
        k4.metric("Costo / Caja", fmt_pesos(costo_caja_a, 2), delta=_texto_delta(_delta_pct(costo_caja_a, costo_caja_p)) if tiene_prev else None, delta_color="inverse")
        k5.metric("Cobertura de costeo", f"{fmt_n(cobertura_a, 1)}%", delta=_texto_delta(_delta_pp(cobertura_a, cobertura_p), " pp") if tiene_prev else None)

        # Composición del costo del período actual.
        divisor()
        titulo_panel("Estructura de costos actual", "Peso de cada componente dentro del período elegido. Se calcula únicamente sobre filas con CM disponible.")
        costos_actual = resumen_costos_periodo(actual_cm_scope)
        if costos_actual.empty:
            st.info("No hay costos calculados para este alcance.")
        else:
            tabla_costos = costos_actual[["Concepto", "Costo", "Costo_Caja", "%_Facturacion"]].copy()
            c_graf, c_tabla = st.columns([1.35, 1])
            with c_graf:
                st.plotly_chart(fig_estructura_costos(costos_actual), width="stretch", theme=None, config=CONFIG_CHART, key="costos_estructura_actual")
            with c_tabla:
                st.dataframe(
                    tabla_costos.style.format({
                        "Costo": fmt_pesos,
                        "Costo_Caja": lambda v: fmt_pesos(v, 2),
                        "%_Facturacion": lambda v: f"{fmt_n(v, 2)}%",
                    }, na_rep="—"),
                    width="stretch", hide_index=True, height=455,
                )

        if tiene_prev:
            comp_costos = comparar_costos(actual_cm_scope, anterior_cm_scope)
            delta_vol = _delta_pct(_suma_num(actual_cm_scope, "Cajas Fisicas"), _suma_num(anterior_cm_scope, "Cajas Fisicas"))
            delta_fact_cost = _delta_pct(_suma_num(actual_cm_scope, "Facturacion Neta"), _suma_num(anterior_cm_scope, "Facturacion Neta"))
            delta_cm_abs = cm_a - cm_p

            divisor()
            titulo_panel(
                "Puente de Contribución Marginal",
                "Reconciliación exacta: CM anterior + variación de Facturación − variación de cada costo = CM actual. No atribuye causalidad precio/volumen/mix.",
            )
            st.plotly_chart(fig_bridge_variacion_cm(actual_cm_scope, anterior_cm_scope), width="stretch", theme=None, config=CONFIG_CHART, key="costos_bridge_cm")

            divisor()
            titulo_panel("Qué explicó el cambio", "Impacto aritmético de cada componente sobre la variación de CM. Rojo = presión; verde = alivio.")
            c1, c2 = st.columns([1.25, 1])
            with c1:
                st.plotly_chart(fig_impacto_costos(comp_costos), width="stretch", theme=None, config=CONFIG_CHART, key="costos_impactos")
            with c2:
                presiones = comp_costos.sort_values("Impacto_CM")
                mayor_presion = presiones.iloc[0] if not presiones.empty else None
                mayor_alivio = presiones.iloc[-1] if not presiones.empty else None
                tarjeta_insight(
                    "Resultado del período",
                    f"La CM {'aumentó' if delta_cm_abs >= 0 else 'cayó'} {fmt_pesos(abs(delta_cm_abs))}. Facturación costeada: {_texto_delta(delta_fact_cost) or 'sin base comparable'}; volumen: {_texto_delta(delta_vol) or 'sin base comparable'}.",
                    "ok" if delta_cm_abs >= 0 else "bad",
                )
                st.write("")
                if mayor_presion is not None:
                    tarjeta_insight(
                        "Mayor presión de costo",
                        f"{mayor_presion['Concepto']} tuvo un impacto de {fmt_pesos(mayor_presion['Impacto_CM'])} sobre la variación de CM. Su costo cambió {fmt_pesos(mayor_presion['Variacion_Costo'])}.",
                        "bad" if mayor_presion["Impacto_CM"] < 0 else "ok",
                    )
                st.write("")
                if mayor_alivio is not None:
                    tarjeta_insight(
                        "Mayor alivio de costo",
                        f"{mayor_alivio['Concepto']} aportó {fmt_pesos(mayor_alivio['Impacto_CM'])} a la variación de CM.",
                        "ok" if mayor_alivio["Impacto_CM"] > 0 else "warn",
                    )
                st.write("")
                if delta_vol is not None and delta_vol > 0 and cmpct_a < cmpct_p:
                    tarjeta_insight(
                        "Volumen ↑, margen % ↓",
                        f"El volumen creció {fmt_n(delta_vol, 1)}%, pero la CM % cayó {fmt_n(cmpct_p - cmpct_a, 1)} pp. Conviene revisar mix, precio neto y costos unitarios.",
                        "warn",
                    )

            divisor()
            a, b = st.columns(2)
            with a:
                titulo_panel("Costo por Caja", "Comparación de eficiencia unitaria en los componentes más materiales.")
                st.plotly_chart(fig_costos_unitarios(comp_costos), width="stretch", theme=None, config=CONFIG_CHART, key="costos_unitarios")
            with b:
                titulo_panel("Mix de costos sobre facturación", "Permite separar el efecto de escala del deterioro/mejora relativa de cada costo.")
                st.plotly_chart(fig_mix_costos(comp_costos), width="stretch", theme=None, config=CONFIG_CHART, key="costos_mix_facturacion")

            divisor()
            titulo_panel("Detalle comparativo", "Tabla auditable de todos los componentes y sus variaciones.")
            detalle_comp = comp_costos[[
                "Concepto", "Anterior", "Actual", "Variacion_Costo", "Impacto_CM",
                "Anterior_Caja", "Actual_Caja", "Var_Caja_%", "Anterior_%Fact", "Actual_%Fact", "Var_pp"
            ]].copy()
            st.dataframe(
                detalle_comp.style.format({
                    "Anterior": fmt_pesos, "Actual": fmt_pesos, "Variacion_Costo": fmt_pesos, "Impacto_CM": fmt_pesos,
                    "Anterior_Caja": lambda v: fmt_pesos(v, 2), "Actual_Caja": lambda v: fmt_pesos(v, 2),
                    "Var_Caja_%": lambda v: f"{fmt_n(v, 1)}%", "Anterior_%Fact": lambda v: f"{fmt_n(v, 2)}%",
                    "Actual_%Fact": lambda v: f"{fmt_n(v, 2)}%", "Var_pp": lambda v: f"{fmt_n(v, 2)} pp",
                }, na_rep="—"),
                width="stretch", hide_index=True,
            )
            boton_descarga(detalle_comp, "comparacion_costos.csv", "⬇️ Descargar comparación de costos")

            # Alerta de comparabilidad de cobertura.
            if abs(cobertura_a - cobertura_p) >= 1.0:
                st.warning(
                    f"La cobertura de costeo cambió {fmt_n(cobertura_a - cobertura_p, 1)} pp entre períodos. "
                    "La reconciliación matemática sigue siendo correcta sobre las filas costeadas, pero parte de la variación puede reflejar cambios de cobertura."
                )
        else:
            st.info(
                "No existe una ventana anterior completa con los filtros actuales. Podés cambiar a **Mes vs mes anterior** para habilitar el puente de variación."
            )

        divisor()
        titulo_panel("Tendencia de eficiencia", "Costo total por caja y CM por caja a lo largo del tiempo para el alcance de Canal/Locación actual.")
        # Para dar contexto temporal, usamos todos los meses disponibles conservando Canal y Locación.
        contexto = _aplicar_filtros_dimension(venta_cm, locaciones_sel, canales_sel)
        contexto_cm = contexto[contexto["CM_calculada"]].copy()
        st.plotly_chart(fig_tendencia_eficiencia(contexto_cm), width="stretch", theme=None, config=CONFIG_CHART, key="costos_tendencia_eficiencia")

    elif actual_scope is not None:
        st.info("No hay datos para el período y los filtros seleccionados.")

# --- Tab 4: Clientes --------------------------------------------------------
with tab_clientes:
    titulo_panel(
        "Rentabilidad por cliente",
        "Encontrá clientes que generan margen, clientes que destruyen valor y después bajá hasta producto y estructura de costos.",
    )
    if clientes.empty:
        st.info("No hay clientes con información para los filtros seleccionados.")
    else:
        positivos_cli = clientes[clientes["CM_pesos"] > 0]
        negativos_cli = clientes[clientes["CM_pesos"] < 0]
        cm_pos_total = positivos_cli["CM_pesos"].sum()
        top10_cm = positivos_cli.nlargest(10, "CM_pesos")["CM_pesos"].sum() if not positivos_cli.empty else 0
        conc10 = top10_cm / cm_pos_total * 100 if cm_pos_total else 0
        cobertura_cli = venta_cm_f["Facturacion Neta"].sum() / venta_f["Facturacion Neta"].sum() * 100 if venta_f["Facturacion Neta"].sum() else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Clientes activos", fmt_n(len(clientes)))
        k2.metric("Clientes con CM negativa", fmt_n(len(negativos_cli)))
        k3.metric("Top 10 / CM positiva", f"{fmt_n(conc10, 1)}%", help="Concentración de la CM positiva en los 10 clientes que más aportan.")
        k4.metric("Cobertura de costeo", f"{fmt_n(cobertura_cli, 1)}%")

        divisor()
        titulo_panel("Mapa de clientes", "Volumen en X, CM % en Y y tamaño por facturación. La visual prioriza los clientes de mayor facturación cuando hay más de 1.200 puntos.")
        fig_cli, n_cli_mapa = fig_matriz_clientes(clientes)
        st.plotly_chart(fig_cli, width="stretch", theme=None, config=CONFIG_CHART, key="clientes_matriz")
        if n_cli_mapa > 1200:
            st.caption(f"La matriz muestra los 1.200 clientes de mayor facturación de {fmt_n(n_cli_mapa)} clientes con datos válidos. Los KPIs y tablas usan el universo completo.")

        divisor()
        ca, cb = st.columns(2)
        with ca:
            titulo_panel("Clientes que más CM generan")
            st.plotly_chart(fig_ranking_clientes_cmg(clientes, mejores=True), width="stretch", theme=None, config=CONFIG_CHART, key="clientes_top_cmg")
        with cb:
            titulo_panel("Clientes con menor CM")
            if (clientes["CM_pesos"] < 0).any():
                st.plotly_chart(fig_ranking_clientes_cmg(clientes[clientes["CM_pesos"] < 0], mejores=False), width="stretch", theme=None, config=CONFIG_CHART, key="clientes_peores_cmg")
            else:
                st.success("No hay clientes con CM negativa para los filtros actuales.")

        divisor()
        titulo_panel("Analizar un cliente", "Buscá por código o nombre. El detalle respeta los filtros globales de período, canal y locación.")
        opciones_cli = {}
        for _, r in clientes.sort_values("Facturacion_Neta", ascending=False).iterrows():
            etiqueta = f"{fmt_entero(r['Cliente'])} - {r['Nom.Cliente']} | {r['Canal']} | {r['Locación']}"
            opciones_cli[etiqueta] = (r["Cliente"], r["Nom.Cliente"], r["Canal"], r["Locación"])
        etiqueta_cli = st.selectbox("Cliente", options=list(opciones_cli.keys()), key="cliente_detalle")
        cli_cod, cli_nom, cli_canal, cli_loc = opciones_cli[etiqueta_cli]
        mask_all = (
            venta_f["Cliente"].eq(cli_cod) & venta_f["Nom.Cliente"].eq(cli_nom) &
            venta_f["Canal"].eq(cli_canal) & venta_f["Locación"].eq(cli_loc)
        )
        mask_cm = (
            venta_cm_f["Cliente"].eq(cli_cod) & venta_cm_f["Nom.Cliente"].eq(cli_nom) &
            venta_cm_f["Canal"].eq(cli_canal) & venta_cm_f["Locación"].eq(cli_loc)
        )
        cli_all, cli_cm = venta_f[mask_all], venta_cm_f[mask_cm]
        fact, cajas, cm, cmpct, cmcaja, cob = _metricas_scope(cli_all, cli_cm)
        a1, a2, a3, a4, a5, a6 = st.columns(6)
        a1.metric("Facturación", fmt_pesos(fact))
        a2.metric("CM", fmt_pesos(cm))
        a3.metric("CM %", f"{fmt_n(cmpct, 1)}%")
        a4.metric("Cajas", fmt_n(cajas))
        a5.metric("CM/Caja", fmt_pesos(cmcaja, 2))
        a6.metric("Cobertura", f"{fmt_n(cob, 1)}%")

        t1, t2 = st.columns([1.15, .85])
        with t1:
            titulo_panel("Evolución del cliente")
            tendencia = _tendencia_scope(cli_all, cli_cm)
            if tendencia.empty:
                st.info("Sin serie mensual disponible.")
            else:
                st.plotly_chart(fig_tendencia_mensual(tendencia), width="stretch", theme=None, config=CONFIG_CHART, key="clientes_detalle_tendencia")
        with t2:
            titulo_panel("Estructura de costos")
            if cli_cm.empty:
                st.info("El cliente no tiene filas costeadas en la selección.")
            else:
                st.plotly_chart(fig_costos_scope(cli_cm), width="stretch", theme=None, config=CONFIG_CHART, key="clientes_detalle_costos")

        titulo_panel("Mix de productos del cliente")
        prod_cli = resumen_productos(cli_cm)
        if prod_cli.empty:
            st.info("No hay productos costeados para este cliente.")
        else:
            st.plotly_chart(fig_mix_productos(prod_cli), width="stretch", theme=None, config=CONFIG_CHART, key="clientes_detalle_mix")
        with st.expander("Ver tabla completa de clientes"):
            st.dataframe(_tabla_entidad_estilo(clientes), width="stretch", hide_index=True, height=520)
            boton_descarga(clientes, "rentabilidad_clientes.csv", "⬇️ Descargar clientes")

# --- Tab 5: Canales ---------------------------------------------------------
with tab_canales:
    titulo_panel("Gestión por canal", "Compará rentabilidad, cobertura, volumen y concentración; después abrí un canal hasta cliente, producto y costo.")
    if canales_detalle.empty:
        st.info("No hay canales para los filtros seleccionados.")
    else:
        st.plotly_chart(fig_barras_cm(canales_detalle, "Canal", top_n=20), width="stretch", theme=None, config=CONFIG_CHART, key="canales_cm")
        st.dataframe(_tabla_entidad_estilo(canales_detalle), width="stretch", hide_index=True)

        divisor()
        opciones_canal = canales_detalle.sort_values("Facturacion_Neta", ascending=False)["Canal"].astype(str).tolist()
        canal_sel_mod = st.selectbox("Abrir canal", options=opciones_canal, key="canal_modulo")
        canal_all = venta_f[venta_f["Canal"].astype(str).eq(canal_sel_mod)]
        canal_cm = venta_cm_f[venta_cm_f["Canal"].astype(str).eq(canal_sel_mod)]
        fact, cajas, cm, cmpct, cmcaja, cob = _metricas_scope(canal_all, canal_cm)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Facturación", fmt_pesos(fact)); c2.metric("CM", fmt_pesos(cm)); c3.metric("CM %", f"{fmt_n(cmpct,1)}%")
        c4.metric("Cajas", fmt_n(cajas)); c5.metric("Clientes", fmt_n(canal_all["Cliente"].nunique())); c6.metric("SKU", fmt_n(canal_all["Cod. Venta"].nunique()))

        ca, cb = st.columns(2)
        with ca:
            titulo_panel("Clientes dentro del canal")
            cli_canal = resumen_clientes_integral(canal_all, canal_cm)
            st.plotly_chart(fig_ranking_clientes_cmg(cli_canal, mejores=True), width="stretch", theme=None, config=CONFIG_CHART, key="canales_detalle_clientes")
        with cb:
            titulo_panel("Productos dentro del canal")
            prod_canal = resumen_productos(canal_cm)
            if prod_canal.empty: st.info("Sin productos costeados.")
            else: st.plotly_chart(fig_mix_productos(prod_canal), width="stretch", theme=None, config=CONFIG_CHART, key="canales_detalle_mix")

        ca, cb = st.columns(2)
        with ca:
            titulo_panel("Evolución mensual")
            t = _tendencia_scope(canal_all, canal_cm)
            if not t.empty: st.plotly_chart(fig_tendencia_mensual(t), width="stretch", theme=None, config=CONFIG_CHART, key="canales_detalle_tendencia")
        with cb:
            titulo_panel("Estructura de costos")
            if not canal_cm.empty: st.plotly_chart(fig_costos_scope(canal_cm), width="stretch", theme=None, config=CONFIG_CHART, key="canales_detalle_costos")
        boton_descarga(canales_detalle, "rentabilidad_canales.csv", "⬇️ Descargar canales")

# --- Tab 6: Locaciones ------------------------------------------------------
with tab_locaciones:
    titulo_panel("Gestión por locación", "Compará operaciones y bajá desde una locación hasta sus clientes, productos y componentes de costo.")
    if locaciones_detalle.empty:
        st.info("No hay locaciones para los filtros seleccionados.")
    else:
        st.plotly_chart(fig_barras_cm(locaciones_detalle, "Locación", top_n=20), width="stretch", theme=None, config=CONFIG_CHART, key="locaciones_cm")
        st.dataframe(_tabla_entidad_estilo(locaciones_detalle), width="stretch", hide_index=True)

        divisor()
        opciones_loc = locaciones_detalle.sort_values("Facturacion_Neta", ascending=False)["Locación"].astype(str).tolist()
        loc_sel_mod = st.selectbox("Abrir locación", options=opciones_loc, key="locacion_modulo")
        loc_all = venta_f[venta_f["Locación"].astype(str).eq(loc_sel_mod)]
        loc_cm = venta_cm_f[venta_cm_f["Locación"].astype(str).eq(loc_sel_mod)]
        fact, cajas, cm, cmpct, cmcaja, cob = _metricas_scope(loc_all, loc_cm)
        l1, l2, l3, l4, l5, l6 = st.columns(6)
        l1.metric("Facturación", fmt_pesos(fact)); l2.metric("CM", fmt_pesos(cm)); l3.metric("CM %", f"{fmt_n(cmpct,1)}%")
        l4.metric("Cajas", fmt_n(cajas)); l5.metric("Clientes", fmt_n(loc_all["Cliente"].nunique())); l6.metric("SKU", fmt_n(loc_all["Cod. Venta"].nunique()))

        la, lb = st.columns(2)
        with la:
            titulo_panel("Clientes de la locación")
            cli_loc = resumen_clientes_integral(loc_all, loc_cm)
            st.plotly_chart(fig_ranking_clientes_cmg(cli_loc, mejores=True), width="stretch", theme=None, config=CONFIG_CHART, key="locaciones_detalle_clientes")
        with lb:
            titulo_panel("Productos de la locación")
            prod_loc = resumen_productos(loc_cm)
            if prod_loc.empty: st.info("Sin productos costeados.")
            else: st.plotly_chart(fig_mix_productos(prod_loc), width="stretch", theme=None, config=CONFIG_CHART, key="locaciones_detalle_mix")

        la, lb = st.columns(2)
        with la:
            titulo_panel("Evolución mensual")
            t = _tendencia_scope(loc_all, loc_cm)
            if not t.empty: st.plotly_chart(fig_tendencia_mensual(t), width="stretch", theme=None, config=CONFIG_CHART, key="locaciones_detalle_tendencia")
        with lb:
            titulo_panel("Estructura de costos")
            if not loc_cm.empty: st.plotly_chart(fig_costos_scope(loc_cm), width="stretch", theme=None, config=CONFIG_CHART, key="locaciones_detalle_costos")
        boton_descarga(locaciones_detalle, "rentabilidad_locaciones.csv", "⬇️ Descargar locaciones")

# --- Tab 7: Explorador jerárquico -----------------------------------------
with tab_explorador:
    titulo_panel("Explorador de rentabilidad", "Drill-down guiado: Empresa → Canal → Cliente → Producto → Costos. Siempre parte de los filtros globales.")
    exp_all = venta_f.copy()
    canal_opts = ["Todos los canales"] + sorted(exp_all["Canal"].dropna().astype(str).unique().tolist())
    exp_canal = st.selectbox("1 · Canal", canal_opts, key="exp_canal")
    if exp_canal != "Todos los canales":
        exp_all = exp_all[exp_all["Canal"].astype(str).eq(exp_canal)]

    clientes_exp = exp_all[["Cliente", "Nom.Cliente", "Canal", "Locación"]].drop_duplicates().copy()
    cliente_opts = {"Todos los clientes": None}
    for _, r in clientes_exp.sort_values(["Nom.Cliente", "Cliente"]).iterrows():
        lab = f"{fmt_entero(r['Cliente'])} - {r['Nom.Cliente']} | {r['Locación']}"
        cliente_opts[lab] = (r["Cliente"], r["Nom.Cliente"], r["Canal"], r["Locación"])
    exp_cliente_lab = st.selectbox("2 · Cliente", list(cliente_opts.keys()), key="exp_cliente")
    if cliente_opts[exp_cliente_lab] is not None:
        ecod, enom, ecan, eloc = cliente_opts[exp_cliente_lab]
        exp_all = exp_all[
            exp_all["Cliente"].eq(ecod) & exp_all["Nom.Cliente"].eq(enom) &
            exp_all["Canal"].eq(ecan) & exp_all["Locación"].eq(eloc)
        ]

    productos_exp = exp_all[["Cod. Venta", "Descripción del material"]].drop_duplicates().sort_values("Cod. Venta")
    prod_opts = {"Todos los productos": None}
    for _, r in productos_exp.iterrows():
        prod_opts[f"{fmt_entero(r['Cod. Venta'])} - {r['Descripción del material']}"] = r["Cod. Venta"]
    exp_prod_lab = st.selectbox("3 · Producto", list(prod_opts.keys()), key="exp_producto")
    if prod_opts[exp_prod_lab] is not None:
        exp_all = exp_all[exp_all["Cod. Venta"].eq(prod_opts[exp_prod_lab])]

    exp_cm = exp_all[exp_all["CM_calculada"]].copy()
    bread = ["Empresa"]
    if exp_canal != "Todos los canales": bread.append(exp_canal)
    if exp_cliente_lab != "Todos los clientes": bread.append(exp_cliente_lab.split(" | ")[0])
    if exp_prod_lab != "Todos los productos": bread.append(exp_prod_lab)
    st.markdown(f'<div class="cmg-breadcrumb"><strong>Ruta:</strong> {" &nbsp;→&nbsp; ".join(bread)}</div>', unsafe_allow_html=True)

    fact, cajas, cm, cmpct, cmcaja, cob = _metricas_scope(exp_all, exp_cm)
    e1, e2, e3, e4, e5, e6 = st.columns(6)
    e1.metric("Facturación", fmt_pesos(fact)); e2.metric("CM", fmt_pesos(cm)); e3.metric("CM %", f"{fmt_n(cmpct,1)}%")
    e4.metric("Cajas", fmt_n(cajas)); e5.metric("CM/Caja", fmt_pesos(cmcaja,2)); e6.metric("Cobertura", f"{fmt_n(cob,1)}%")

    exa, exb = st.columns([1.05, .95])
    with exa:
        titulo_panel("Evolución de la selección")
        t = _tendencia_scope(exp_all, exp_cm)
        if t.empty: st.info("No hay datos para esta selección.")
        else: st.plotly_chart(fig_tendencia_mensual(t), width="stretch", theme=None, config=CONFIG_CHART, key="explorador_tendencia")
    with exb:
        titulo_panel("4 · Componentes de costo")
        if exp_cm.empty: st.info("No hay CM calculada para esta selección.")
        else: st.plotly_chart(fig_costos_scope(exp_cm, top_n=15), width="stretch", theme=None, config=CONFIG_CHART, key="explorador_costos")

    if not exp_cm.empty:
        titulo_panel("Cascada consolidada", "La misma lógica financiera del motor de CM, agregada para la selección actual.")
        casc = exp_cm[COLUMNAS_CASCADA].sum()
        filas = [{"Concepto": "Facturación Neta", "Monto": casc["Facturacion Neta"]}]
        for c in COLUMNAS_CASCADA[1:-1]:
            filas.append({"Concepto": f"(–) {c}", "Monto": -casc[c]})
        filas.append({"Concepto": "= Contribución Marginal ($)", "Monto": casc["CM ($)"]})
        df_exp_casc = pd.DataFrame(filas)
        st.plotly_chart(fig_cascada(df_exp_casc), width="stretch", theme=None, config=CONFIG_CHART, key="explorador_cascada")

        with st.expander("Ver detalle de la selección"):
            cols_exp = [c for c in ["Mes", "Cliente", "Nom.Cliente", "Canal", "Locación", "Cod. Venta", "Descripción del material", "Cajas Fisicas", "Facturacion Neta", "Costo Total", "CM ($)", "CM (%)"] if c in exp_cm.columns]
            st.dataframe(exp_cm[cols_exp], width="stretch", hide_index=True, height=450)
            boton_descarga(exp_cm[cols_exp], "explorador_cmg.csv", "⬇️ Descargar selección")

# --- Tab 8: Detalle por artículo -------------------------------------------
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
                st.plotly_chart(fig_cascada(df_cascada), width="stretch", theme=None, config=CONFIG_CHART, key="articulo_cascada")
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
            por_cliente["CM_%"] = porcentaje_seguro(
                por_cliente["CM_pesos"], por_cliente["Facturacion_Neta"], 1
            )
        por_cliente = por_cliente.sort_values("Facturacion_Neta", ascending=False)

        columna_top = "CM_pesos" if calculable else "Facturacion_Neta"
        etiqueta_top = "Contribución Marginal" if calculable else "Facturación Neta"
        st.caption(f"Top {min(10, len(por_cliente))} clientes por {etiqueta_top}")
        if por_cliente.empty:
            st.info("No hay ventas de este artículo para los filtros seleccionados.")
        else:
            st.plotly_chart(
                fig_top_clientes(por_cliente, columna_top, titulo_eje_x=etiqueta_top + " ($)"),
                width="stretch", theme=None, config=CONFIG_CHART, key="articulo_top_clientes",
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

# --- Tab 9: Calidad de datos -------------------------------------------------
with tab_calidad:
    titulo_panel("Calidad y cobertura de los datos", "Controles visibles para saber qué tan confiable es el análisis antes de tomar decisiones.")

    filas_total = len(venta_cm)
    filas_costeadas = int(venta_cm["CM_calculada"].sum())
    fact_total_dq = venta_cm["Facturacion Neta"].sum()
    fact_costeada_dq = venta_cm.loc[venta_cm["CM_calculada"], "Facturacion Neta"].sum()
    cobertura_filas = filas_costeadas / filas_total * 100 if filas_total else 0
    cobertura_fact = fact_costeada_dq / fact_total_dq * 100 if fact_total_dq else 0

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Filas de venta", fmt_n(filas_total))
    q2.metric("Filas con CM", f"{fmt_n(cobertura_filas, 1)}%")
    q3.metric("Facturación con CM", f"{fmt_n(cobertura_fact, 1)}%")
    q4.metric("Meses cargados", fmt_n(venta_cm["Mes"].nunique()))

    controles = []
    controles.append(("Artículo sin maestro/tipo", int(venta_cm["Tipo de Prod."].isna().sum()), "Filas de venta cuyo artículo no encuentra Tipo de Prod. en Maestro."))
    controles.append(("Tipo sin regla de costeo", int((~venta_cm["CM_calculada"]).sum()), "Filas cuyo Tipo de Prod. todavía no es P/R."))
    controles.append(("Cliente vacío", int(venta_cm["Cliente"].isna().sum()), "Registros sin código de cliente."))
    controles.append(("Canal vacío", int(venta_cm["Canal"].isna().sum()), "Registros sin canal comercial."))
    controles.append(("Locación vacía", int(venta_cm["Locación"].isna().sum()), "Registros sin locación."))
    if "Descripción del material" in venta_cm.columns:
        controles.append(("Descripción de artículo vacía", int(venta_cm["Descripción del material"].isna().sum()), "Filas sin descripción de material."))

    # Claves maestras que sí deberían ser únicas antes de un merge.
    duplicados_maestro = int(maestro.duplicated(subset=["Cod. Venta"], keep=False).sum()) if "Cod. Venta" in maestro.columns else 0
    controles.append(("Duplicados en Maestro", duplicados_maestro, "Filas involucradas en códigos de artículo repetidos en Maestro."))
    if {"Cod. Venta", "Mes"}.issubset(mo.columns):
        controles.append(("Duplicados en MO", int(mo.duplicated(subset=["Cod. Venta", "Mes"], keep=False).sum()), "Filas involucradas en claves Cod. Venta + Mes repetidas."))
    if {"Locación", "Mes"}.issubset(dxl.columns):
        controles.append(("Duplicados en DatosxLocacion", int(dxl.duplicated(subset=["Locación", "Mes"], keep=False).sum()), "Filas involucradas en claves Locación + Mes repetidas."))
    if {"Cod. Venta", "Mes"}.issubset(fletest0.columns):
        controles.append(("Duplicados en FletesT0", int(fletest0.duplicated(subset=["Cod. Venta", "Mes"], keep=False).sum()), "Filas involucradas en claves Cod. Venta + Mes repetidas."))

    df_calidad = pd.DataFrame(controles, columns=["Control", "Registros", "Qué significa"])
    df_calidad["Estado"] = df_calidad["Registros"].map(lambda x: "✅ OK" if x == 0 else "⚠️ Revisar")
    st.dataframe(df_calidad[["Estado", "Control", "Registros", "Qué significa"]], width="stretch", hide_index=True)

    if (df_calidad["Registros"] > 0).any():
        st.warning("Los controles marcados no implican necesariamente un error de negocio, pero deben revisarse antes de usar el dato para decisiones sensibles.")
    else:
        st.success("No se detectaron incidencias en los controles básicos de calidad.")

    with st.expander("Ver artículos sin regla de costeo"):
        sin_costeo = venta_cm.loc[~venta_cm["CM_calculada"], [c for c in ["Cod. Venta", "Descripción del material", "Tipo de Prod.", "Facturacion Neta", "Cajas Fisicas"] if c in venta_cm.columns]]
        if sin_costeo.empty:
            st.success("Todos los registros tienen regla de costeo.")
        else:
            resumen_sc = sin_costeo.groupby([c for c in ["Cod. Venta", "Descripción del material", "Tipo de Prod."] if c in sin_costeo.columns], dropna=False, as_index=False).agg(
                Facturacion_Neta=("Facturacion Neta", "sum"), Cajas_Fisicas=("Cajas Fisicas", "sum")
            )
            st.dataframe(resumen_sc, width="stretch", hide_index=True)

# --- Tab 10: Datos crudos ----------------------------------------------------
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
