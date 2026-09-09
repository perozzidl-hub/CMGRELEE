"""
app.py — AppCMG: Explorador de Contribución Marginal al detalle
==================================================================
Streamlit app para navegar al máximo nivel de detalle la venta (clientes,
locaciones, canales) y la Contribución Marginal calculada para cada
artículo, cliente, locación y canal.

Ejecutar con:
    streamlit run app.py
"""
import pandas as pd
import streamlit as st

from data_loader import cargar_todo
from calculo_cmg import calcular_cmg, COLUMNAS_CASCADA, PALLETS_POR_CAMION


# ----------------------------------------------------------------------
# Configuración visual — capa de presentación únicamente
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="AppCMG | Contribución Marginal",
    page_icon="🥤",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        /* ---------- Sistema visual ---------- */
        :root {
            --coke-red: #F40009;
            --coke-red-dark: #C90008;
            --navy: #1A2B4C;
            --blue: #2A5C8E;
            --ink: #233044;
            --muted: #6B778C;
            --bg: #F4F6F9;
            --card: #FFFFFF;
            --border: #E4E9F0;
            --success: #1E8E5A;
            --warning: #D97706;
            --radius: 12px;
            --shadow: 0 3px 14px rgba(26, 43, 76, 0.07);
        }

        .stApp {
            background: var(--bg);
        }

        /* ---------- Ancho y navegación ---------- */
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1500px;
        }

        /* ---------- Header principal ---------- */
        .app-header {
            background: linear-gradient(135deg, var(--navy) 0%, #203F68 65%, var(--blue) 100%);
            border-radius: 16px;
            padding: 22px 28px 20px;
            margin-bottom: 18px;
            box-shadow: 0 7px 24px rgba(26, 43, 76, 0.14);
            position: relative;
            overflow: hidden;
        }

        .app-header::after {
            content: "";
            position: absolute;
            width: 220px;
            height: 220px;
            border-radius: 50%;
            right: -70px;
            top: -100px;
            background: rgba(244, 0, 9, 0.18);
        }

        .app-kicker {
            color: #D7E4F2;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }

        .app-title {
            color: #FFFFFF;
            font-size: 2rem;
            line-height: 1.1;
            font-weight: 800;
            margin: 0;
        }

        .app-subtitle {
            color: #DCE7F4;
            margin-top: 7px;
            font-size: 0.95rem;
        }

        .brand-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-top: 15px;
            padding: 6px 11px;
            border-radius: 999px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.16);
            color: #FFFFFF;
            font-size: 0.78rem;
            font-weight: 700;
        }

        .brand-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--coke-red);
            box-shadow: 0 0 0 4px rgba(244,0,9,0.16);
        }

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid var(--border);
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 1.15rem;
        }

        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: var(--navy);
            font-weight: 800;
        }

        .sidebar-section {
            padding: 10px 0 6px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 10px;
        }

        .sidebar-label {
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        /* ---------- Tabs ---------- */
        button[data-baseweb="tab"] {
            font-weight: 750 !important;
            color: #65748B !important;
            padding-top: 10px !important;
            padding-bottom: 11px !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--navy) !important;
        }

        div[data-baseweb="tab-highlight"] {
            background-color: var(--coke-red) !important;
            height: 3px !important;
            border-radius: 999px !important;
        }

        /* ---------- KPI cards ---------- */
        div[data-testid="stMetric"] {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 15px 17px 14px;
            box-shadow: var(--shadow);
            min-height: 118px;
        }

        div[data-testid="stMetricLabel"] {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 800;
        }

        div[data-testid="stMetricValue"] {
            color: var(--navy);
            font-size: 1.62rem;
            font-weight: 850;
            letter-spacing: -0.02em;
        }

        div[data-testid="stMetricDelta"] {
            color: var(--success);
        }

        /* ---------- Contenedores y títulos ---------- */
        h2, h3, h4 {
            color: var(--navy);
        }

        h3 {
            margin-top: 0.65rem !important;
        }

        .section-label {
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 850;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            margin: 3px 0 5px;
        }

        .section-title {
            color: var(--navy);
            font-size: 1.05rem;
            font-weight: 800;
            margin: 0 0 12px;
        }

        .info-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 15px 17px;
            box-shadow: var(--shadow);
        }

        .insight-card {
            background: linear-gradient(180deg, #FFFFFF 0%, #FBFCFE 100%);
            border-left: 4px solid var(--coke-red);
            border-top: 1px solid var(--border);
            border-right: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 15px;
            margin: 6px 0 10px;
            color: var(--ink);
            font-size: 0.88rem;
        }

        /* ---------- Alertas ---------- */
        div[data-testid="stAlert"] {
            border-radius: 10px;
            border: 1px solid var(--border);
        }

        /* ---------- Tablas ---------- */
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        /* ---------- Inputs ---------- */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div {
            border-radius: 9px;
        }

        /* ---------- Responsive ---------- */
        @media (max-width: 900px) {
            .app-title {
                font-size: 1.45rem;
            }
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------
# Componentes puramente presentacionales
# ----------------------------------------------------------------------
def render_header():
    """Header corporativo; no contiene lógica de negocio."""
    st.markdown(
        """
        <div class="app-header">
            <div class="app-kicker">Management Dashboard · Control de gestión</div>
            <div class="app-title">🥤 AppCMG</div>
            <div class="app-subtitle">
                Explorador de Contribución Marginal al detalle
            </div>
            <div class="brand-chip">
                <span class="brand-dot"></span>
                Entorno corporativo · paleta inspirada en Coca‑Cola
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(eyebrow: str, title: str):
    st.markdown(
        f"""
        <div class="section-label">{eyebrow}</div>
        <div class="section-title">{title}</div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_label(text: str):
    st.markdown(
        f'<div class="section-label" style="margin-bottom:4px;">{text}</div>',
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# Carga de datos + cálculo de CM
# ----------------------------------------------------------------------
@st.cache_data(show_spinner="Leyendo y limpiando el archivo...")
def cargar(archivo) -> dict[str, pd.DataFrame]:
    return cargar_todo(archivo)


@st.cache_data(show_spinner="Calculando Contribución Marginal...")
def calcular(_datos: dict, pallets_por_camion: int) -> pd.DataFrame:
    return calcular_cmg(_datos, pallets_por_camion=pallets_por_camion)


render_header()

archivo = st.sidebar.file_uploader("Subí el archivo AppCMG.xlsx", type=["xlsx"])

if archivo is None:
    st.markdown(
        """
        <div class="info-card">
            <div class="section-label">Inicio</div>
            <h3 style="margin:0 0 6px;">Cargá el archivo para comenzar</h3>
            <div style="color:#6B778C;">
                El modelo espera las 7 hojas: VENTA, Maestro Artículos, Receta,
                MO, DatosxLocacion, FletesT0 y Exhibición.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Usá la barra lateral para cargar el Excel y activar el análisis.")
    st.stop()

datos = cargar(archivo)

st.sidebar.markdown('<div class="sidebar-label">Supuestos</div>', unsafe_allow_html=True)
pallets_por_camion = st.sidebar.number_input(
    "Pallets por camión (Flete T1)", min_value=1, value=PALLETS_POR_CAMION, step=1
)

venta_cm = calcular(datos, pallets_por_camion)
maestro = datos["maestro"]
receta = datos["receta"]
mo = datos["mo"]
dxl = datos["datosxlocacion"]
fletest0 = datos["fletest0"]

n_sin_costeo = (~venta_cm["CM_calculada"]).sum()

# Estado de carga más compacto y corporativo.
st.success(f"Archivo cargado correctamente · {len(venta_cm):,} filas de venta.")
if n_sin_costeo:
    tipos_sin_costeo = sorted(
        venta_cm.loc[~venta_cm["CM_calculada"], "Tipo de Prod."].dropna().unique()
    )
    st.warning(
        f"⚠️ {n_sin_costeo:,} filas son de artículos con Tipo de Prod. {tipos_sin_costeo} "
        "— todavía sin regla de costeo definida (solo P y R están cubiertos). "
        "Quedan afuera de los totales de Contribución Marginal de abajo."
    )

# ----------------------------------------------------------------------
# Filtros globales (barra lateral)
# ----------------------------------------------------------------------
st.sidebar.markdown('<div class="sidebar-label">Filtros globales</div>', unsafe_allow_html=True)

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
    g["CM_%"] = (g["CM_pesos"] / g["Facturacion_Neta"] * 100).round(1)
    return g.sort_values("CM_pesos", ascending=False)


# ----------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------
tab_resumen, tab_articulo, tab_crudo = st.tabs(
    ["📊 Resumen ejecutivo", "🔎 Detalle por artículo", "🗂️ Datos crudos"]
)

# --- Tab 1: Resumen general ------------------------------------------------
with tab_resumen:
    fact_total = venta_f["Facturacion Neta"].sum()
    cm_total = venta_cm_f["CM ($)"].sum()
    cm_pct = cm_total / venta_cm_f["Facturacion Neta"].sum() * 100 if len(venta_cm_f) else 0
    clientes_total = venta_f["Cliente"].nunique()

    render_section_header("Executive overview", "Indicadores principales")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Facturación Neta", f"$ {fact_total:,.0f}")
        st.caption("Venta neta dentro de los filtros activos.")
    with c2:
        st.metric("Contribución Marginal", f"$ {cm_total:,.0f}")
        st.caption("CM calculada para filas con costeo disponible.")
    with c3:
        st.metric("CM % (ponderado)", f"{cm_pct:,.1f}%")
        st.caption("CM sobre facturación de las filas costeadas.")
    with c4:
        st.metric("Clientes distintos", f"{clientes_total:,}")
        st.caption("Clientes únicos en el universo filtrado.")

    # Visualización temporal: barras separadas para comparación y línea de CM.
    render_section_header("Tendencia", "Facturación neta y Contribución Marginal por mes")
    por_mes = venta_f.groupby("Mes", as_index=False)["Facturacion Neta"].sum()
    por_mes["Contribución Marginal"] = venta_cm_f.groupby("Mes")["CM ($)"].sum().values
    por_mes["Mes"] = por_mes["Mes"].dt.strftime("%Y-%m")

    por_mes_largo = por_mes.melt(id_vars="Mes", var_name="Concepto", value_name="Monto")
    st.bar_chart(
        por_mes_largo,
        x="Mes",
        y="Monto",
        color="Concepto",
        stack=False,
        height=360,
    )

    st.caption(
        "Lectura sugerida: compará la evolución de la facturación con el nivel de CM "
        "para detectar meses de mayor presión o generación de valor."
    )

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        render_section_header("Mix comercial", "Contribución por canal")
        por_canal = resumen_cm(venta_cm_f, "Canal")
        st.bar_chart(
            por_canal.set_index("Canal")["CM_pesos"],
            height=300,
        )
        st.caption("Ranking de CM ($) por canal. La tabla debajo conserva el detalle.")

        st.dataframe(
            por_canal,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Facturacion_Neta": st.column_config.NumberColumn(
                    "Facturación Neta", format="$ %,.0f"
                ),
                "Cajas_Fisicas": st.column_config.NumberColumn(
                    "Cajas Físicas", format="%,.0f"
                ),
                "CM_pesos": st.column_config.NumberColumn(
                    "CM ($)", format="$ %,.0f"
                ),
                "CM_%": st.column_config.NumberColumn(
                    "CM %", format="%.1f%%"
                ),
            },
        )

    with col_b:
        render_section_header("Cobertura geográfica", "Contribución por locación")
        por_locacion = resumen_cm(venta_cm_f, "Locación")
        st.bar_chart(
            por_locacion.set_index("Locación")["CM_pesos"],
            height=300,
        )
        st.caption("Ranking de CM ($) por locación. Útil para detectar concentración.")

        st.dataframe(
            por_locacion,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Facturacion_Neta": st.column_config.NumberColumn(
                    "Facturación Neta", format="$ %,.0f"
                ),
                "Cajas_Fisicas": st.column_config.NumberColumn(
                    "Cajas Físicas", format="%,.0f"
                ),
                "CM_pesos": st.column_config.NumberColumn(
                    "CM ($)", format="$ %,.0f"
                ),
                "CM_%": st.column_config.NumberColumn(
                    "CM %", format="%.1f%%"
                ),
            },
        )

# --- Tab 2: Detalle por artículo -------------------------------------------
with tab_articulo:
    articulos_disp = (
        venta_f[["Cod. Venta", "Descripción del material"]]
        .drop_duplicates()
        .sort_values("Cod. Venta")
    )

    if articulos_disp.empty:
        st.warning("No hay artículos para los filtros seleccionados.")
        st.stop()

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

    render_section_header("Artículo seleccionado", f"Artículo {cod}")
    st.caption(
        f"Tipo de producto: {tipo_prod} · Selección actual: {elegido}"
    )

    if not calculable:
        st.warning(
            f"Tipo de producto '{tipo_prod}' todavía no tiene regla de costeo "
            "(solo P y R están definidos) — se muestra la venta, sin CM."
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Facturación Neta", f"$ {v_art['Facturacion Neta'].sum():,.0f}")
    with c2:
        st.metric("Cajas Físicas", f"{v_art['Cajas Fisicas'].sum():,.0f}")
    if calculable:
        cm_art = v_art["CM ($)"].sum()
        cm_pct_art = cm_art / v_art["Facturacion Neta"].sum() * 100
        with c3:
            st.metric("Contribución Marginal", f"$ {cm_art:,.0f}")
        with c4:
            st.metric("CM %", f"{cm_pct_art:,.1f}%")
    else:
        with c3:
            st.metric("Contribución Marginal", "—")
        with c4:
            st.metric("CM %", "—")

    if calculable:
        render_section_header(
            "Economía del producto",
            "Cascada de Contribución Marginal",
        )
        cascada = v_art[COLUMNAS_CASCADA].sum()
        filas_cascada = [{"Concepto": "Facturación Neta", "Monto": cascada["Facturacion Neta"]}]
        for c in COLUMNAS_CASCADA[1:-1]:
            filas_cascada.append({"Concepto": f"(–) {c}", "Monto": -cascada[c]})
        filas_cascada.append({"Concepto": "= Contribución Marginal ($)", "Monto": cascada["CM ($)"]})
        df_cascada = pd.DataFrame(filas_cascada)

        col_cascada, col_info = st.columns([1.5, 1], gap="large")
        with col_cascada:
            st.dataframe(
                df_cascada.style.format({"Monto": "$ {:,.0f}"}),
                use_container_width=True,
                hide_index=True,
            )
        with col_info:
            st.markdown(
                """
                <div class="insight-card">
                    <strong>Cómo leer la cascada</strong><br>
                    Partí de la Facturación Neta y observá cuánto valor consume cada
                    componente de costo hasta llegar a la Contribución Marginal.
                </div>
                """,
                unsafe_allow_html=True,
            )

    render_section_header("Rentabilidad y cobertura", "Detalle por cliente")
    cols_cliente = ["Cliente", "Nom.Cliente", "Canal", "Locación"]
    agg_cliente = dict(
        Cajas_Fisicas=("Cajas Fisicas", "sum"), Facturacion_Neta=("Facturacion Neta", "sum")
    )
    if calculable:
        agg_cliente["CM_pesos"] = ("CM ($)", "sum")
    por_cliente = v_art.groupby(cols_cliente, as_index=False).agg(**agg_cliente)
    if calculable:
        por_cliente["CM_%"] = (por_cliente["CM_pesos"] / por_cliente["Facturacion_Neta"] * 100).round(1)
    por_cliente = por_cliente.sort_values("Facturacion_Neta", ascending=False)

    st.dataframe(
        por_cliente,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Facturacion_Neta": st.column_config.NumberColumn(
                "Facturación Neta", format="$ %,.0f"
            ),
            "Cajas_Fisicas": st.column_config.NumberColumn(
                "Cajas Físicas", format="%,.0f"
            ),
            "CM_pesos": st.column_config.NumberColumn(
                "CM ($)", format="$ %,.0f"
            ),
            "CM_%": st.column_config.NumberColumn(
                "CM %", format="%.1f%%"
            ),
        },
    )

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        render_section_header("Cobertura", "Resumen por locación")
        loc_art = (
            resumen_cm(v_art, "Locación") if calculable
            else v_art.groupby("Locación", as_index=False)["Facturacion Neta"].sum()
        )
        if calculable:
            st.bar_chart(
                loc_art.set_index("Locación")["CM_pesos"],
                height=280,
            )
        st.dataframe(
            loc_art,
            use_container_width=True,
            hide_index=True,
        )

    with col_b:
        render_section_header("Mix comercial", "Resumen por canal")
        canal_art = (
            resumen_cm(v_art, "Canal") if calculable
            else v_art.groupby("Canal", as_index=False)["Facturacion Neta"].sum()
        )
        if calculable:
            st.bar_chart(
                canal_art.set_index("Canal")["CM_pesos"],
                height=280,
            )
        st.dataframe(
            canal_art,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    with st.expander("Ver los insumos de costo que alimentan este cálculo"):
        if tipo_prod == "P":
            st.caption("Artículo propio (P) → composición por insumos, hoja Receta:")
            st.dataframe(receta[receta["Cod. Venta"] == cod], use_container_width=True, hide_index=True)
            mo_art = mo[mo["Cod. Venta"] == cod]
            if not mo_art.empty:
                st.caption("Mano de Obra (hoja MO):")
                st.dataframe(mo_art, use_container_width=True, hide_index=True)
        elif tipo_prod == "R":
            st.caption("Artículo de reventa (R) → costo de compra, hoja Receta:")
            st.dataframe(
                receta[receta["Cod. Venta"] == cod][
                    ["Mes", "Costo Compra ($)", "Desperdicio PT (%)", "Desperdicio PT ($)"]
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Flete T0 (ir a buscar el producto), hoja FletesT0:")
            st.dataframe(fletest0[fletest0["Cod. Venta"] == cod], use_container_width=True, hide_index=True)

        st.caption("Datos por Locación aplicables (hoja DatosxLocacion):")
        st.dataframe(
            dxl[dxl["Locación"].isin(v_art["Locación"].unique())],
            use_container_width=True,
            hide_index=True,
        )

# --- Tab 3: Datos crudos ----------------------------------------------------
with tab_crudo:
    render_section_header("Modelo de datos", "Explorador de datos crudos")
    opciones_hojas = {**datos, "venta (con CM calculada)": venta_cm}
    hoja = st.selectbox("Elegí una hoja", options=list(opciones_hojas.keys()))
    st.dataframe(opciones_hojas[hoja], use_container_width=True)
    filas, columnas = opciones_hojas[hoja].shape
    st.caption(f"{filas:,} filas × {columnas:,} columnas")
