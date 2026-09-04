"""
calculo_cmg.py
================
Motor de cálculo de Contribución Marginal, fila por fila de VENTA.

Cascada (confirmada por Damian, 04/09):

    Facturación Neta
    (-) Costo de Producto        Receta: (Costo Estándar [P] o Costo Compra [R]) + Desperdicio PT,
                                  $/pack x Cajas Físicas
    (-) Costo Concentrado        Incidencia (si P) o Incidencia de Reventa (si R) x Facturación Neta,
                                  x (1 + Desperdicio Concentrado)
    (-) Mano de Obra             solo aplica a P; suma de las 4 columnas de MO, $/unidad x Cajas Físicas
    (-) Flete T0                 solo aplica a R; $/unidad x Cajas Físicas
    (-) MO Warehouse             DatosxLocacion, $/unidad x Cajas Físicas
    (-) Tasa Seg. e Higiene      DatosxLocacion, % x Facturación Neta
    (-) Imp. Créditos/Débitos    DatosxLocacion, % x Facturación Neta
    (-) Flete T1 (interdeposito) DatosxLocacion['Flete T1'] / (PACKS x PALLETS x pallets_por_camion),
                                  $/unidad resultante x Cajas Físicas
    (-) Comisiones x Bulto       DatosxLocacion, $/unidad x Cajas Físicas
    (-) Comisiones de Ventas     DatosxLocacion, $/unidad x Cajas Físicas
    (-) Impuesto Ingresos Brutos Maestro Artículos, % x Facturación Neta
    (-) Costo Flete Reparto      ya viene resuelto en VENTA ("Suma de Costo Flete"), se usa tal cual
    = Contribución Marginal ($ y %)

Solo se calcula para Tipo de Prod. P y R (decisión de Damian, 04/09: "por
ahora ninguna [regla], solo nos enfocamos en P y R"). Las filas de otros
tipos (C, x) quedan con CM_calculada=False y las columnas de costo/CM en
NaN — no se inventa una regla para ellas.
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
    "Costo Mano de Obra",
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
    """Costo de producto por Cod.Venta+Mes.

    Cubre P y R en la misma cuenta: para P, 'Costo Compra' es NaN->0 y se
    suman las N líneas de insumo (Costo Estándar); para R, 'Costo Estándar'
    es NaN->0 y hay una sola línea (Costo Compra). Desperdicio PT aplica
    en ambos casos y ya viene calculado por línea.
    """
    agg = receta.groupby(["Cod. Venta", "Mes"], as_index=False).agg(
        costo_estandar=("Costo Estándar ($)", "sum"),
        costo_compra=("Costo Compra ($)", "sum"),
        desperdicio_pt=("Desperdicio PT ($)", "sum"),
    )
    agg["costo_producto_unit"] = (
        agg["costo_estandar"] + agg["costo_compra"] + agg["desperdicio_pt"]
    )
    return agg[["Cod. Venta", "Mes", "costo_producto_unit"]]


def _agregar_mo(mo: pd.DataFrame) -> pd.DataFrame:
    agg = mo.copy()
    agg["mo_unit"] = (
        agg["Mano de Obra Directa"]
        + agg["Mano de Obra Indirecta"]
        + agg["Electricidad / Gas"]
        + agg["Repuestos y Lubricación"]
    )
    return agg[["Cod. Venta", "Mes", "mo_unit"]]


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

    costo_producto = df["costo_producto_unit"].fillna(0) * cf

    incidencia = np.where(es_p, df["Incidencia"], df["Incidencia de Reventa"])
    costo_concentrado = incidencia * fn * (1 + df["Desperdicio Concentrado"].fillna(0))

    costo_mo = df["mo_unit"].fillna(0) * cf
    costo_flete_t0 = df["Flete T0 (Prod. Comprado)"].fillna(0) * cf

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

    costo_ib = df["Impuesto a los Ingresos Brutos"].fillna(0) * fn

    costo_flete_reparto = df["Costo Flete Reparto"].fillna(0)

    costo_total = (
        costo_producto
        + costo_concentrado
        + costo_mo
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
    df["Costo Mano de Obra"] = costo_mo.where(cm_calculable)
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

    return df.drop(columns=["costo_producto_unit", "mo_unit"])


if __name__ == "__main__":
    import sys
    from data_loader import cargar_todo

    path = sys.argv[1] if len(sys.argv) > 1 else "AppCMG.xlsx"
    datos = cargar_todo(path)
    resultado = calcular_cmg(datos)
    print(f"{len(resultado):,} filas procesadas.")
    print(f"Sin costeo (tipo != P/R): {(~resultado['CM_calculada']).sum():,} filas")
    print()
    print(resultado.groupby("Tipo de Prod.", dropna=False).agg(
        Facturacion_Neta=("Facturacion Neta", "sum"),
        CM_pesos=("CM ($)", "sum"),
    ))
