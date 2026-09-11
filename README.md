AppCMG V2 — Fase 3: Costos y Variaciones
=========================================

Base: V2 Fase 2 estable con keys únicos en todos los gráficos Plotly.
No se modificó la lógica financiera de calculo_cmg.py.

Novedades principales
---------------------
1. Nueva pestaña "📉 Costos & Variaciones".
2. Dos modos de comparación:
   - Período filtrado vs período anterior de igual longitud.
   - Mes vs mes anterior.
3. KPIs comparativos: Facturación costeada, CM, CM %, Costo/Caja y cobertura.
4. Estructura de costos actual en $ / Caja / % de Facturación.
5. Puente exacto de CM:
   CM anterior + ΔFacturación - ΔCostos = CM actual.
   Importante: es una reconciliación aritmética, NO una atribución causal precio/volumen/mix.
6. Ranking de componentes que presionaron o liberaron CM.
7. Comparación de costo por caja por componente.
8. Comparación del mix de costos como % de Facturación.
9. Hallazgos automáticos sobre presión/alivio de costos y divergencia volumen-margen.
10. Tabla auditable y CSV de comparación de costos.
11. Tendencia histórica de Costo/Caja y CM/Caja.
12. Se mantiene la protección contra IDs duplicados: todos los st.plotly_chart tienen key único.

Validaciones realizadas con el Excel base actual
-------------------------------------------------
- 82.922 filas de VENTA procesadas.
- 2026-07 vs 2026-08 usados como prueba comparativa.
- La reconciliación del puente cerró contra CM actual con diferencia numérica < 0,000001.
- Todos los gráficos nuevos fueron construidos correctamente con los datos reales.
- app.py, data_loader.py y calculo_cmg.py compilan sin errores.
- 34 gráficos Plotly revisados: 0 sin key y 0 keys duplicados.

Archivos para GitHub
--------------------
app.py
data_loader.py
calculo_cmg.py
requirements.txt
.gitignore
.streamlit/config.toml

No subir carpetas __pycache__ ni archivos .pyc.
