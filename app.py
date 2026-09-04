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

st.set_page_config(page_title="AppCMG - Contribución Marginal al detalle", layout="wide")


# ----------------------------------------------------------------------
# Carga de datos + cálculo de CM
# ----------------------------------------------------------------------
@st.cache_data(show_spinner="Leyendo y limpiando el archivo...")
def cargar(archivo) -> dict[str, pd.DataFrame]:
    return cargar_todo(archivo)


@st.cache_data(show_spinner="Calculando Contribución Marginal...")
def calcular(_datos: dict, pallets_por_camion: int) -> pd.DataFrame:
    return calcular_cmg(_datos, pallets_por_camion=pallets_por_camion)


st.title("🥤 AppCMG — Contribución Marginal al detalle")

archivo = st.sidebar.file_uploader("Subí el archivo AppCMG.xlsx", type=["xlsx"])

if archivo is None:
    st.info(
        "⬅️ Subí el archivo Excel (las 7 hojas: VENTA, Maestro Artículos, "
        "Receta, MO, DatosxLocacion, FletesT0, Exhibición) desde la barra lateral "
        "para empezar."
    )
    st.stop()

datos = cargar(archivo)

st.sidebar.header("Supuestos")
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
st.success(f"Archivo cargado: {len(venta_cm):,} filas de venta.")
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
    g["CM_%"] = (g["CM_pesos"] / g["Facturacion_Neta"] * 100).round(1)
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
    c1.metric("Facturación Neta", f"$ {fact_total:,.0f}")
    c2.metric("Contribución Marginal", f"$ {cm_total:,.0f}")
    cm_pct = cm_total / venta_cm_f["Facturacion Neta"].sum() * 100 if len(venta_cm_f) else 0
    c3.metric("CM % (ponderado)", f"{cm_pct:,.1f}%")
    c4.metric("Clientes distintos", f"{venta_f['Cliente'].nunique():,}")

    st.subheader("Facturación Neta y Contribución Marginal por mes")
    por_mes = venta_f.groupby("Mes", as_index=False)["Facturacion Neta"].sum()
    por_mes["Contribución Marginal"] = venta_cm_f.groupby("Mes")["CM ($)"].sum().values
    por_mes["Mes"] = por_mes["Mes"].dt.strftime("%Y-%m")
    st.bar_chart(por_mes.set_index("Mes"))

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Por Canal")
        st.dataframe(resumen_cm(venta_cm_f, "Canal"), use_container_width=True, hide_index=True)
    with col_b:
        st.subheader("Por Locación")
        st.dataframe(resumen_cm(venta_cm_f, "Locación"), use_container_width=True, hide_index=True)

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

    st.markdown(f"### Artículo {cod} — Tipo de producto: `{tipo_prod}`")
    if not calculable:
        st.warning(
            f"Tipo de producto '{tipo_prod}' todavía no tiene regla de costeo "
            "(solo P y R están definidos) — se muestra la venta, sin CM."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Facturación Neta", f"$ {v_art['Facturacion Neta'].sum():,.0f}")
    c2.metric("Cajas Físicas", f"{v_art['Cajas Fisicas'].sum():,.0f}")
    if calculable:
        cm_art = v_art["CM ($)"].sum()
        cm_pct_art = cm_art / v_art["Facturacion Neta"].sum() * 100
        c3.metric("Contribución Marginal", f"$ {cm_art:,.0f}")
        c4.metric("CM %", f"{cm_pct_art:,.1f}%")
    else:
        c3.metric("Contribución Marginal", "—")
        c4.metric("CM %", "—")

    if calculable:
        st.markdown("#### Cascada de Contribución Marginal (agregada para este artículo)")
        cascada = v_art[COLUMNAS_CASCADA].sum()
        filas_cascada = [{"Concepto": "Facturación Neta", "Monto": cascada["Facturacion Neta"]}]
        for c in COLUMNAS_CASCADA[1:-1]:
            filas_cascada.append({"Concepto": f"(–) {c}", "Monto": -cascada[c]})
        filas_cascada.append({"Concepto": "= Contribución Marginal ($)", "Monto": cascada["CM ($)"]})
        df_cascada = pd.DataFrame(filas_cascada)
        st.dataframe(
            df_cascada.style.format({"Monto": "$ {:,.0f}"}),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Detalle por Cliente")
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
    st.dataframe(por_cliente, use_container_width=True, hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Resumen por Locación")
        st.dataframe(
            resumen_cm(v_art, "Locación") if calculable
            else v_art.groupby("Locación", as_index=False)["Facturacion Neta"].sum(),
            use_container_width=True, hide_index=True,
        )
    with col_b:
        st.markdown("#### Resumen por Canal")
        st.dataframe(
            resumen_cm(v_art, "Canal") if calculable
            else v_art.groupby("Canal", as_index=False)["Facturacion Neta"].sum(),
            use_container_width=True, hide_index=True,
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
                use_container_width=True, hide_index=True,
            )
            st.caption("Flete T0 (ir a buscar el producto), hoja FletesT0:")
            st.dataframe(fletest0[fletest0["Cod. Venta"] == cod], use_container_width=True, hide_index=True)

        st.caption("Datos por Locación aplicables (hoja DatosxLocacion):")
        st.dataframe(
            dxl[dxl["Locación"].isin(v_art["Locación"].unique())],
            use_container_width=True, hide_index=True,
        )

# --- Tab 3: Datos crudos ----------------------------------------------------
with tab_crudo:
    opciones_hojas = {**datos, "venta (con CM calculada)": venta_cm}
    hoja = st.selectbox("Elegí una hoja", options=list(opciones_hojas.keys()))
    st.dataframe(opciones_hojas[hoja], use_container_width=True)
    st.caption(f"{opciones_hojas[hoja].shape[0]:,} filas x {opciones_hojas[hoja].shape[1]} columnas")
