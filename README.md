# AppCMG — Contribución Marginal al detalle

## Cómo correrla

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abre en el navegador. Desde la barra lateral subís el `AppCMG.xlsx`
(u otro archivo con la misma estructura de 7 hojas) y ya podés navegar.

## Estructura

- `data_loader.py` — carga y limpia las 7 hojas (encabezados corridos,
  filas separadoras vacías, tipos de dato).
- `calculo_cmg.py` — el motor: toma el dict de `data_loader` y devuelve
  VENTA enriquecida con cada componente de costo y la Contribución
  Marginal ($ y %) por fila. Corriendo `python calculo_cmg.py` solo
  (con el xlsx en la misma carpeta) tira un resumen por Tipo de Prod.,
  útil para chequear números rápido sin levantar la app.
- `app.py` — la app Streamlit, 3 tabs (Resumen general, Detalle por
  artículo con la cascada completa, y Datos crudos). No necesitó
  cambios en la corrección del 04/09 — lee la cascada de forma genérica
  desde `COLUMNAS_CASCADA`, así que cualquier ajuste a la fórmula en
  `calculo_cmg.py` se refleja solo.
- Pallets por camión (Flete T1) es ajustable desde la barra lateral —
  default 24.

## Fórmula de Contribución Marginal (corregida, 04/09)

```
Facturación Neta
(–) Costo de Producto         P: Costo Estándar (Receta) x Cajas Físicas
                               R: Costo Compra ($) x Cajas Físicas
                               (+ Desperdicio PT en ambos casos)
(–) Costo Concentrado         P: Incidencia x Facturación Neta x (1 + Desperdicio Concentrado)
                               R: (Facturación Neta x Incidencia)
                                  - (Costo Compra x Cajas Físicas x Incidencia de Reventa)
(–) Mano de Obra Directa      solo P; $/unidad x Cajas Físicas
(–) Mano de Obra Indirecta    solo P; $/unidad x Cajas Físicas
(–) Electricidad y Gas        solo P; $/unidad x Cajas Físicas
(–) Repuestos y Lubricación   solo P; $/unidad x Cajas Físicas
(–) Flete T0                  solo R; $/unidad x Cajas Físicas
(–) MO Warehouse              DatosxLocacion, $/unidad x Cajas Físicas
(–) Tasa Seg. e Higiene       DatosxLocacion, % x Facturación Neta
(–) Imp. Créditos/Débitos     DatosxLocacion, % x Facturación Neta
(–) Flete T1 (interdeposito)  Flete T1 / (PACKS x PALLETS x 24), $/unidad x Cajas Físicas
(–) Comisiones x Bulto        DatosxLocacion, $/unidad x Cajas Físicas
(–) Comisiones de Ventas      DatosxLocacion, $/unidad x Cajas Físicas
(–) Impuesto Ingresos Brutos  Maestro Artículos, % x Facturación Neta
(–) Costo Flete Reparto       ya viene resuelto en VENTA, se usa tal cual
= Contribución Marginal ($ y %)
```

Ejemplo de Damian para el Concentrado en R (verificado exacto en el motor):
compra 100 u. a $10 (costo compra $1.000), vende a $15 (Facturación Neta
$1.500), Incidencia 20% (sobre Facturación Neta), Incidencia de Reventa 5%
(sobre la compra) → Concentrado = 1.500×20% − 1.000×5% = **$250**.

La Mano de Obra ahora queda abierta por los 4 conceptos de la hoja MO
(antes iba sumada en una sola línea) — el total no cambia, solo la
apertura.

Solo se calcula para Tipo de Prod. **P y R**. Otros tipos (por ahora: C,
x) quedan con `CM_calculada=False`.

## Verificación

Cada componente se cruzó a mano contra el archivo real — fila P (con y
sin Flete T1), fila R, y el ejemplo numérico de Damian para el
Concentrado en R — coinciden centavo a centavo. El detalle quedó en el chat.

## Próximos pasos posibles

- Cargar el catálogo completo (237 artículos) cuando haya venta real de
  más SKUs, y confirmar la regla de costeo para los tipos C / x si en
  algún momento entran en alcance.
- Rankings (top clientes/artículos por CM, no solo por facturación).
- Exportar el detalle calculado a Excel/CSV directo desde la app.
