"""
data_loader.py
================
Carga y limpieza de las 7 hojas del archivo AppCMG.xlsx.

Cada hoja del archivo real tiene sus propias particularidades (fila de
encabezado en distinta posición, filas separadoras vacías entre bloques
mensuales, etc.). Este módulo encapsula esa limpieza para que el resto de
la app trabaje siempre con DataFrames prolijos y con las claves de cruce
ya normalizadas.

Claves de cruce entre hojas:
    - Artículo:  VENTA['Cod. Venta'] == Maestro['Cod. Venta']
                 == Receta['Cod. Venta'] == MO['Cod. Venta']
                 == FletesT0['Cod. Venta']
    - Locación:  VENTA['Locación'] == DatosxLocacion['Locación']
    - Mes:       VENTA['Mes'] (derivado de 'Fe.Liquidación', truncado a
                 mes) == 'Mes' en Receta / MO / DatosxLocacion / FletesT0
                 / Exhibición (que ya vienen a nivel mensual)
"""
from __future__ import annotations
import pandas as pd

REQUIRED_SHEETS = [
    "VENTA",
    "Maestro Artículos",
    "Receta",
    "MO",
    "DatosxLocacion",
    "FletesT0",
    "Exhibición",
]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Saca filas 100% vacías (separadores) y reinicia el índice."""
    return df.dropna(how="all").reset_index(drop=True)


def _mes(serie: pd.Series) -> pd.Series:
    """Normaliza una columna de fecha al primer día del mes (nivel mensual)."""
    return pd.to_datetime(serie).values.astype("datetime64[M]")


def cargar_venta(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="VENTA", header=1)
    df = _clean(df)
    df["Fe.Liquidación"] = pd.to_datetime(df["Fe.Liquidación"])
    df["Mes"] = _mes(df["Fe.Liquidación"])
    df = df.rename(
        columns={
            "Material": "Cod. Venta",
            "Suma de SUMA_UC": "Unit Cases",
            "Suma de SUMA_CF": "Cajas Fisicas",
            "Suma de Facturación de Lista": "Facturacion Lista",
            "Suma de totalDesc": "Descuentos",
            "Suma de Facturación Neta": "Facturacion Neta",
            "Suma de Costo Flete": "Costo Flete Reparto",
        }
    )
    df["Cod. Venta"] = df["Cod. Venta"].astype(int)
    df["Transportista"] = df["Transportista"].fillna("Sin transportista")
    return df


def cargar_maestro_articulos(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="Maestro Artículos", header=2)
    df = _clean(df)
    df["Cod. Venta"] = df["Cod. Venta"].astype(int)
    return df


def cargar_receta(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="Receta", header=0)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    df["Cod. Venta"] = df["Cod. Venta"].astype(int)
    return df


def cargar_mo(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="MO", header=1)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    df["Cod. Venta"] = df["Cod. Venta"].astype(int)
    return df


def cargar_datosxlocacion(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="DatosxLocacion", header=2)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    return df


def cargar_fletest0(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="FletesT0", header=1)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    df["Cod. Venta"] = df["Cod. Venta"].astype(int)
    return df


def cargar_exhibicion(xls: pd.ExcelFile) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name="Exhibición", header=2)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    return df


LOADERS = {
    "venta": cargar_venta,
    "maestro": cargar_maestro_articulos,
    "receta": cargar_receta,
    "mo": cargar_mo,
    "datosxlocacion": cargar_datosxlocacion,
    "fletest0": cargar_fletest0,
    "exhibicion": cargar_exhibicion,
}


def cargar_todo(path_o_buffer) -> dict[str, pd.DataFrame]:
    """Carga y limpia las 7 hojas. Devuelve un dict {nombre: DataFrame}."""
    xls = pd.ExcelFile(path_o_buffer)
    faltantes = [s for s in REQUIRED_SHEETS if s not in xls.sheet_names]
    if faltantes:
        raise ValueError(f"Faltan hojas en el archivo: {faltantes}")
    return {nombre: fn(xls) for nombre, fn in LOADERS.items()}


if __name__ == "__main__":
    # Prueba rápida contra un archivo local, para validar que todo carga sin error.
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "AppCMG.xlsx"
    datos = cargar_todo(path)
    for nombre, df in datos.items():
        print(f"{nombre:16s} -> {df.shape[0]:6d} filas x {df.shape[1]:2d} columnas")
