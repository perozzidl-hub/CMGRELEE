AppCMG V2 Fase 2 - Corrección StreamlitDuplicateElementId

Cambio aplicado:
- Se agregó un key único a cada st.plotly_chart de app.py.
- No se modificó data_loader.py.
- No se modificó calculo_cmg.py ni ninguna regla de Contribución Marginal.
- Se verificó que las 28 llamadas a st.plotly_chart tengan keys únicos.
- Se validó sintaxis de app.py, data_loader.py y calculo_cmg.py.

Motivo:
Streamlit 1.63.0 genera un ID automático a partir del tipo de elemento y sus parámetros.
En distintas pestañas había gráficos con exactamente los mismos datos/parámetros, por ejemplo
CM por Locación en Resumen y en el módulo Locaciones. Eso producía un ID duplicado.

Para GitHub:
Descomprimir y reemplazar los archivos manteniendo la estructura del repositorio.
