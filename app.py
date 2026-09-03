import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from src.data_processing import load_and_transform_data

st.set_page_config(page_title="Análisis Contribución Marginal", layout="wide")

st.title("📊 Análisis de Contribución Marginal a Máximo Detalle")

uploaded_file = st.sidebar.file_uploader("Cargar archivo Excel (AppCMG.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    df = load_and_transform_data(uploaded_file)

    # --- BARRA LATERAL: FILTROS DINÁMICOS ---
    st.sidebar.header("Filtros de Análisis")
    
    # Filtro Rango Fecha
    min_date = df['Fe.Liquidación'].min().date()
    max_date = df['Fe.Liquidación'].max().date()
    fecha_sel = st.sidebar.date_input("Rango de Fechas", [min_date, max_date])

    # Filtros Multiselect
    articulos = st.sidebar.multiselect("Artículo / Material", options=sorted(df['Descripción del material'].dropna().unique()))
    canales = st.sidebar.multiselect("Canal", options=sorted(df['Canal'].dropna().unique()))
    clientes = st.sidebar.multiselect("Cliente", options=sorted(df['Nom.Cliente'].dropna().unique()))
    locaciones = st.sidebar.multiselect("Locación", options=sorted(df['Locación'].dropna().unique()))

    # Aplicación de Filtros
    df_filtered = df.copy()
    if len(fecha_sel) == 2:
        df_filtered = df_filtered[(df_filtered['Fe.Liquidación'].dt.date >= fecha_sel[0]) & 
                                  (df_filtered['Fe.Liquidación'].dt.date <= fecha_sel[1])]
    if articulos:
        df_filtered = df_filtered[df_filtered['Descripción del material'].isin(articulos)]
    if canales:
        df_filtered = df_filtered[df_filtered['Canal'].isin(canales)]
    if clientes:
        df_filtered = df_filtered[df_filtered['Nom.Cliente'].isin(clientes)]
    if locaciones:
        df_filtered = df_filtered[df_filtered['Locación'].isin(locaciones)]

    # --- DASHBOARD PRINCIPAL ---
    # 1. KPIs Generales
    col1, col2, col3, col4, col5 = st.columns(5)
    cant_total = df_filtered['Cantidad_Fisica'].sum()
    fact_total = df_filtered['Facturacion_Neta'].sum()
    costo_tot = df_filtered['costo_total'].sum()
    cm_total = df_filtered['contribucion_marginal'].sum()
    cm_pct = (cm_total / fact_total * 100) if fact_total > 0 else 0

    col1.metric("Unidades Vendidas", f"{cant_total:,.0f}")
    col2.metric("Facturación Neta", f"${fact_total:,.2f}")
    col3.metric("Costo Total", f"${costo_tot:,.2f}")
    col4.metric("Contribución Marginal", f"${cm_total:,.2f}")
    col5.metric("% CM / Facturación", f"{cm_pct:.2f}%")

    st.markdown("---")

    # 2. Desglose Estructura de Costos vs Facturación
    st.subheader("💡 Apertura Detallada de Costos e Ingresos")
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        costos_dict = {
            'Materia Prima / Compra': df_filtered['costo_materia_prima'].sum(),
            'Desperdicio Operativo': df_filtered['costo_desp_operativo_total'].sum(),
            'Flete T0': df_filtered['costo_flete_t0_total'].sum(),
            'Mano de Obra Directa/Ind.': df_filtered['costo_mo_total'].sum(),
            'Warehouse / Depósito': df_filtered['costo_warehouse_total'].sum(),
            'Flete T1 (Interdepósito)': df_filtered['costo_flete_t1_total'].sum(),
            'Comisiones Fletes y Ventas': df_filtered['costo_comisiones_flete'].sum() + df_filtered['costo_comisiones_ventas'].sum(),
            'Impuestos (IIBB, TSH, Créd/Déb)': df_filtered['costo_impuestos_total'].sum()
        }
        df_costos_pie = pd.DataFrame(list(costos_dict.items()), columns=['Concepto', 'Monto'])
        fig_pie = px.pie(df_costos_pie, names='Concepto', values='Monto', title='Distribución del Costo Total', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        # Gráfico por Canal / Locación
        cm_por_canal = df_filtered.groupby('Canal').agg({'Facturacion_Neta': 'sum', 'contribucion_marginal': 'sum'}).reset_index()
        fig_bar = px.bar(cm_por_canal, x='Canal', y=['Facturacion_Neta', 'contribucion_marginal'], 
                         barmode='group', title='Facturación vs CM por Canal',
                         labels={'value': 'Monto ($)', 'variable': 'Métrica'})
        st.plotly_chart(fig_bar, use_container_width=True)

    # 3. Vista de Máxima Granularidad (Tabla Dinámica)
    st.subheader("🔍 Detalle Máximo Transaccional")
    
    cols_mostrar = [
        'Fe.Liquidación', 'Cod. Venta', 'Descripción del material', 'Nom.Cliente', 
        'Canal', 'Locación', 'Cantidad_Fisica', 'Facturacion_Neta', 
        'costo_materia_prima', 'costo_mo_total', 'costo_impuestos_total', 
        'costo_total', 'contribucion_marginal', 'cm_porcentual'
    ]
    st.dataframe(df_filtered[cols_mostrar].sort_values(by='Fe.Liquidación', ascending=False), use_container_width=True)

else:
    st.info("👋 Por favor, carga el archivo `AppCMG.xlsx` desde el menú lateral para iniciar el análisis.")
