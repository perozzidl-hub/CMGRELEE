"""
calculo_cmg.py
================
Motor de cálculo de Contribución Marginal, fila por fila de VENTA.

Cascada (confirmada por Damian, 04/09; concentrado R y apertura de MO
corregidas 04/09):

    Facturación Neta
    (-) Costo de Producto          P: suma de Costo Estándar (Receta) x Cajas Físicas
                                    R: Costo Compra ($) x Cajas Físicas
                                    (+ Desperdicio PT en ambos casos, ya viene por línea)
    (-) Costo Concentrado          P: Incidencia x Facturación Neta x (1 + Desperdicio Concentrado)
                                    R: (Facturación Neta x Incidencia)
                                       - (Costo Compra x Cajas Físicas x Incidencia de Reventa)
                                       [Incidencia de Reventa se aplica sobre el costo de COMPRA,
                                        no sobre facturación; ver ejemplo de Damian más abajo]
    (-) Mano de Obra Directa       solo P; MO, $/unidad x Cajas Físicas
    (-) Mano de Obra Indirecta     solo P; MO, $/unidad x Cajas Físicas
    (-) Electricidad y Gas         solo P; MO, $/unidad x Cajas Físicas
    (-) Repuestos y Lubricación    solo P; MO, $/unidad x Cajas Físicas
    (-) Flete T0                   solo R; $/unidad x Cajas Físicas
    (-) MO Warehouse               DatosxLocacion, $/unidad x Cajas Físicas
    (-) Tasa Seg. e Higiene        DatosxLocacion, % x Facturación Neta
    (-) Imp. Créditos/Débitos      DatosxLocacion, % x Facturación Neta
    (-) Flete T1 (interdeposito)   Flete T1 / (PACKS x PALLETS x pallets_por_camion),
                                    $/unidad resultante x Cajas Físicas
    (-) Comisiones x Bulto         DatosxLocacion, $/unidad x Cajas Físicas
    (-) Comisiones de Ventas       DatosxLocacion, $/unidad x Cajas Físicas
    (-) Impuesto Ingresos Brutos   Maestro Artículos, % x Facturación Neta
    (-) Costo Flete Reparto        ya viene resuelto en VENTA ("Suma de Costo Flete"), tal cual
    = Contribución Marginal ($ y %)

Ejemplo de Damian para el Concentrado R (verificado exacto en test_calculo_cmg):
    Compra 100 u. a $10 (costo compra $1.000), vende a $15 (Facturación Neta $1.500)
    Incidencia 20% (sobre Facturación Neta), Incidencia de Reventa 5% (sobre la compra)
    Concentrado = 1.500*20% - 1.000*5% = $300 - $50 = $250

Solo se calcula para Tipo de Prod. P y R (Damian, 04/09: "por ahora ninguna
[regla], solo nos enfocamos en P y R"). Las filas de otros tipos (C, x)
quedan con CM_calculada=False y las columnas de costo/CM en NaN.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

PALLETS_POR_CAMION = 24  # supuesto de negocio (Damian, 04/09): pallets que entran en un camión lleno
TIPOS_COSTEADOS = ("P", "R")

COLUMNAS_CASCADA = [
    "Facturacion Neta",
    "Costo Producto",
    "Costo Concentrado",
    "Costo Mano de Obra Directa",
    "Costo Mano de Obra Indirecta",
    "Costo Electricidad y Gas",
    "Costo Repuestos y Lubricación",
    "Costo Flete T0",
    "Costo MO Warehouse",
    "Costo Seguridad e Higiene",
    "Costo Créditos/Débitos",
    "Costo Flete T1",
    "Costo Comisiones Bulto",
    "Costo Comisiones Ventas",
    "Costo Ingresos Brutos",
    "Costo Flete Reparto",
    "CM ($)",
]


def _agregar_receta(receta: pd.DataFrame) -> pd.DataFrame:
    """Componentes de Receta por Cod.Venta+Mes, SIN combinar todavía.

    Se dejan por separado porque el costo de compra "puro" (sin Desperdicio
    PT) hace falta aparte para la fórmula de Concentrado en artículos R.
    """
    agg = receta.groupby(["Cod. Venta", "Mes"], as_index=False).agg(
        costo_estandar=("Costo Estándar ($)", "sum"),
        costo_compra=("Costo Compra ($)", "sum"),
        desperdicio_pt=("Desperdicio PT ($)", "sum"),
    )
    return agg


def _agregar_mo(mo: pd.DataFrame) -> pd.DataFrame:
    """Las 4 columnas de MO, tal cual, para mantenerlas abiertas por concepto."""
    return mo[
        [
            "Cod. Venta",
            "Mes",
            "Mano de Obra Directa",
            "Mano de Obra Indirecta",
            "Electricidad / Gas",
            "Repuestos y Lubricación",
        ]
    ].copy()


def calcular_cmg(datos: dict, pallets_por_camion: int = PALLETS_POR_CAMION) -> pd.DataFrame:
    """Devuelve VENTA enriquecida con cada componente de costo y la CM ($ y %) por fila."""
    venta = datos["venta"].copy()
    maestro = datos["maestro"]
    receta_agg = _agregar_receta(datos["receta"])
    mo_agg = _agregar_mo(datos["mo"])
    fletest0 = datos["fletest0"][["Cod. Venta", "Mes", "Flete T0 (Prod. Comprado)"]]
    dxl = datos["datosxlocacion"]

    df = venta.merge(
        maestro[
            [
                "Cod. Venta",
                "Tipo de Prod.",
                "PACKS x PALLETS",
                "Incidencia",
                "Incidencia de Reventa",
                "Desperdicio Concentrado",
                "Impuesto a los Ingresos Brutos",
            ]
        ],
        on="Cod. Venta",
        how="left",
    )
    df = df.merge(receta_agg, on=["Cod. Venta", "Mes"], how="left")
    df = df.merge(mo_agg, on=["Cod. Venta", "Mes"], how="left")
    df = df.merge(fletest0, on=["Cod. Venta", "Mes"], how="left")
    df = df.merge(dxl, on=["Locación", "Mes"], how="left")

    cm_calculable = df["Tipo de Prod."].isin(TIPOS_COSTEADOS)
    es_p = df["Tipo de Prod."] == "P"

    cf = df["Cajas Fisicas"]
    fn = df["Facturacion Neta"]

    # --- Costo de Producto: Costo Estándar (P) o Costo Compra (R), + Desperdicio PT en ambos ---
    costo_estandar = df["costo_estandar"].fillna(0)
    costo_compra = df["costo_compra"].fillna(0)
    desperdicio_pt = df["desperdicio_pt"].fillna(0)
    costo_producto = (costo_estandar + costo_compra + desperdicio_pt) * cf

    # --- Costo Concentrado: fórmula distinta para P y para R ---
    incidencia = df["Incidencia"].fillna(0)
    incidencia_reventa = df["Incidencia de Reventa"].fillna(0)
    desperdicio_conc = df["Desperdicio Concentrado"].fillna(0)
    costo_compra_total = costo_compra * cf  # "precio de compra unitario x cantidad vendida", sin Desperdicio PT

    costo_concentrado_p = incidencia * fn * (1 + desperdicio_conc)
    costo_concentrado_r = incidencia * fn - costo_compra_total * incidencia_reventa
    costo_concentrado = pd.Series(
        np.where(es_p, costo_concentrado_p, costo_concentrado_r), index=df.index
    )

    # --- Mano de Obra, abierta por concepto (solo aplica a P; fillna(0) en R) ---
    costo_mo_directa = df["Mano de Obra Directa"].fillna(0) * cf
    costo_mo_indirecta = df["Mano de Obra Indirecta"].fillna(0) * cf
    costo_electricidad_gas = df["Electricidad / Gas"].fillna(0) * cf
    costo_repuestos_lub = df["Repuestos y Lubricación"].fillna(0) * cf

    # --- Flete T0 (solo aplica a R) ---
    costo_flete_t0 = df["Flete T0 (Prod. Comprado)"].fillna(0) * cf

    # --- Costos por locación ---
    costo_mo_wh = df["Mano de Obra Warehouse"].fillna(0) * cf
    costo_seg_hig = df["Tasa Seguridad e Higiene ($)"].fillna(0) * fn
    costo_cred_deb = df["Impuestos a los Créditos/Débitos"].fillna(0) * fn

    capacidad_camion = df["PACKS x PALLETS"] * pallets_por_camion
    flete_t1_unit = (
        (df["Flete T1 (Interdeposito)"] / capacidad_camion)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )
    costo_flete_t1 = flete_t1_unit * cf

    costo_com_bulto = df["Comisiones x Bulto de Fletes"].fillna(0) * cf
    costo_com_ventas = df["Comisiones de Ventas ( en Fisicos)"].fillna(0) * cf

    # --- Impuesto a los Ingresos Brutos ---
    costo_ib = df["Impuesto a los Ingresos Brutos"].fillna(0) * fn

    # --- Flete de reparto: ya viene resuelto en VENTA ---
    costo_flete_reparto = df["Costo Flete Reparto"].fillna(0)

    costo_total = (
        costo_producto
        + costo_concentrado
        + costo_mo_directa
        + costo_mo_indirecta
        + costo_electricidad_gas
        + costo_repuestos_lub
        + costo_flete_t0
        + costo_mo_wh
        + costo_seg_hig
        + costo_cred_deb
        + costo_flete_t1
        + costo_com_bulto
        + costo_com_ventas
        + costo_ib
        + costo_flete_reparto
    )

    df["Costo Producto"] = costo_producto.where(cm_calculable)
    df["Costo Concentrado"] = costo_concentrado.where(cm_calculable)
    df["Costo Mano de Obra Directa"] = costo_mo_directa.where(cm_calculable)
    df["Costo Mano de Obra Indirecta"] = costo_mo_indirecta.where(cm_calculable)
    df["Costo Electricidad y Gas"] = costo_electricidad_gas.where(cm_calculable)
    df["Costo Repuestos y Lubricación"] = costo_repuestos_lub.where(cm_calculable)
    df["Costo Flete T0"] = costo_flete_t0.where(cm_calculable)
    df["Costo MO Warehouse"] = costo_mo_wh.where(cm_calculable)
    df["Costo Seguridad e Higiene"] = costo_seg_hig.where(cm_calculable)
    df["Costo Créditos/Débitos"] = costo_cred_deb.where(cm_calculable)
    df["Costo Flete T1"] = costo_flete_t1.where(cm_calculable)
    df["Costo Comisiones Bulto"] = costo_com_bulto.where(cm_calculable)
    df["Costo Comisiones Ventas"] = costo_com_ventas.where(cm_calculable)
    df["Costo Ingresos Brutos"] = costo_ib.where(cm_calculable)
    df["Costo Flete Reparto"] = costo_flete_reparto.where(cm_calculable)
    df["Costo Total"] = costo_total.where(cm_calculable)
    df["CM ($)"] = (fn - costo_total).where(cm_calculable)
    df["CM (%)"] = (df["CM ($)"] / fn).replace([np.inf, -np.inf], np.nan)
    df["CM_calculada"] = cm_calculable

    return df.drop(columns=["costo_estandar", "costo_compra", "desperdicio_pt"])


if __name__ == "__main__":
    import sys
    from data_loader import cargar_todo

    path = sys.argv[1] if len(sys.argv) > 1 else "AppCMG.xlsx"
    datos = cargar_todo(path)
    resultado = calcular_cmg(datos)
    print(f"{len(resultado):,} filas procesadas.")
    print(f"Sin costeo (tipo != P/R): {(~resultado['CM_calculada']).sum():,} filas")
    print()
    print(
        resultado.groupby("Tipo de Prod.", dropna=False).agg(
            Facturacion_Neta=("Facturacion Neta", "sum"),
            CM_pesos=("CM ($)", "sum"),
        )
    )
