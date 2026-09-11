"""
data_loader.py
================
Carga y limpieza de las fuentes de AppCMG.

Diseño preparado para DOS escenarios sin cambiar el resto de la app:

1) Archivo integral (actual):
   Un único .xlsx con las 7 hojas originales.

2) Múltiples archivos (futuro):
   Las mismas fuentes pueden estar repartidas entre varios .xlsx, o incluso
   repetirse en varios archivos (por ejemplo, un archivo por mes). El loader
   identifica cada dataset, normaliza su estructura, concatena las partes y
   valida que las tablas maestras/costos no generen cruces ambiguos.

La API pública se mantiene igual:
    datos = cargar_todo(archivo)
    datos = cargar_todo([archivo_1, archivo_2, ...])

Por lo tanto, calculo_cmg.py no necesita saber cuántos archivos originaron
los datos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib

import pandas as pd


# ---------------------------------------------------------------------------
# Esquema lógico de AppCMG
# ---------------------------------------------------------------------------
# "sheet" es el nombre canónico actual. "firma" permite reconocer la fuente
# por sus columnas aunque en el futuro venga en una hoja con otro nombre.
DATASET_SPECS = {
    "venta": {
        "sheet": "VENTA",
        "header": 1,
        "firma": {"Fe.Liquidación", "Material", "Suma de Facturación Neta"},
    },
    "maestro": {
        "sheet": "Maestro Artículos",
        "header": 2,
        "firma": {"Cod. Venta", "Tipo de Prod.", "PACKS x PALLETS"},
    },
    "receta": {
        "sheet": "Receta",
        "header": 0,
        "firma": {"Mes", "Cod. Venta", "Costo Estándar ($)", "Costo Compra ($)"},
    },
    "mo": {
        "sheet": "MO",
        "header": 1,
        "firma": {"Mes", "Cod. Venta", "Mano de Obra Directa"},
    },
    "datosxlocacion": {
        "sheet": "DatosxLocacion",
        "header": 2,
        "firma": {"Mes", "Locación", "Mano de Obra Warehouse"},
    },
    "fletest0": {
        "sheet": "FletesT0",
        "header": 1,
        "firma": {"Mes", "Cod. Venta", "Flete T0 (Prod. Comprado)"},
    },
    "exhibicion": {
        "sheet": "Exhibición",
        "header": 2,
        "firma": {"Mes", "Locación", "Canal", "Material", "Exhibición ($)"},
    },
}

REQUIRED_SHEETS = [spec["sheet"] for spec in DATASET_SPECS.values()]

# Tablas donde una clave repetida con valores distintos volvería ambiguo un
# merge y podría duplicar ventas/costos silenciosamente.
CLAVES_UNICAS = {
    "maestro": ["Cod. Venta"],
    "receta": ["Cod. Venta", "Mes", "Código Insumo"],
    "mo": ["Cod. Venta", "Mes"],
    "datosxlocacion": ["Locación", "Mes"],
    "fletest0": ["Cod. Venta", "Mes"],
    "exhibicion": ["Mes", "Locación", "Canal", "Material"],
}


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Saca filas 100% vacías (separadores) y reinicia el índice."""
    return df.dropna(how="all").reset_index(drop=True)


def _mes(serie: pd.Series) -> pd.Series:
    """Normaliza una columna de fecha al primer día del mes (nivel mensual)."""
    return pd.to_datetime(serie).values.astype("datetime64[M]")


def _normalizar_fuentes(fuentes: Any) -> list[Any]:
    """Acepta una fuente única o una lista/tupla de fuentes Excel."""
    if isinstance(fuentes, (list, tuple)):
        salida = list(fuentes)
    else:
        salida = [fuentes]

    salida = [f for f in salida if f is not None]
    if not salida:
        raise ValueError("No se recibió ningún archivo Excel para procesar.")
    return salida


def _nombre_fuente(fuente: Any, indice: int) -> str:
    """Nombre amigable para mensajes de validación."""
    nombre = getattr(fuente, "name", None)
    if nombre:
        return str(nombre)
    if isinstance(fuente, (str, Path)):
        return Path(fuente).name
    return f"archivo_{indice + 1}.xlsx"


def _rebobinar(fuente: Any) -> None:
    """Streamlit UploadedFile/BytesIO pueden haber sido leídos previamente."""
    if hasattr(fuente, "seek"):
        try:
            fuente.seek(0)
        except (OSError, ValueError):
            pass


def _huella_fuente(fuente: Any) -> str | None:
    """SHA-256 para impedir que el mismo archivo se cargue dos veces por error."""
    try:
        if isinstance(fuente, (str, Path)):
            return hashlib.sha256(Path(fuente).read_bytes()).hexdigest()
        if hasattr(fuente, "getvalue"):
            return hashlib.sha256(fuente.getvalue()).hexdigest()
        if hasattr(fuente, "read") and hasattr(fuente, "seek"):
            pos = fuente.tell() if hasattr(fuente, "tell") else 0
            fuente.seek(0)
            contenido = fuente.read()
            fuente.seek(pos)
            return hashlib.sha256(contenido).hexdigest()
    except (OSError, ValueError, TypeError):
        return None
    return None


def _detectar_dataset_y_header(
    xls: pd.ExcelFile,
    sheet_name: str,
    max_filas: int = 6,
) -> tuple[str, int] | None:
    """Reconoce una fuente por las columnas de su encabezado.

    Esto permite que mañana un archivo se llame, por ejemplo, VENTAS_AGOSTO.xlsx
    y su hoja interna sea "Hoja1": si contiene las columnas esperadas, AppCMG
    igualmente puede identificarla.
    """
    raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=max_filas)

    for fila_idx in range(len(raw)):
        valores = {
            str(v).strip()
            for v in raw.iloc[fila_idx].tolist()
            if pd.notna(v) and str(v).strip()
        }
        candidatos = [
            nombre
            for nombre, spec in DATASET_SPECS.items()
            if spec["firma"].issubset(valores)
        ]
        if len(candidatos) == 1:
            return candidatos[0], fila_idx
        if len(candidatos) > 1:
            raise ValueError(
                f"La hoja '{sheet_name}' coincide con más de una estructura AppCMG: {candidatos}."
            )
    return None


# ---------------------------------------------------------------------------
# Loaders por dataset
# ---------------------------------------------------------------------------
def cargar_venta(xls: pd.ExcelFile, sheet_name="VENTA", header=1) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
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
    df["Cod. Venta"] = pd.to_numeric(df["Cod. Venta"], errors="raise").astype(int)
    df["Transportista"] = df["Transportista"].fillna("Sin transportista")
    return df


def cargar_maestro_articulos(
    xls: pd.ExcelFile, sheet_name="Maestro Artículos", header=2
) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
    df = _clean(df)
    df["Cod. Venta"] = pd.to_numeric(df["Cod. Venta"], errors="raise").astype(int)
    return df


def cargar_receta(xls: pd.ExcelFile, sheet_name="Receta", header=0) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    df["Cod. Venta"] = pd.to_numeric(df["Cod. Venta"], errors="raise").astype(int)
    return df


def cargar_mo(xls: pd.ExcelFile, sheet_name="MO", header=1) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    df["Cod. Venta"] = pd.to_numeric(df["Cod. Venta"], errors="raise").astype(int)
    return df


def cargar_datosxlocacion(
    xls: pd.ExcelFile, sheet_name="DatosxLocacion", header=2
) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    return df


def cargar_fletest0(xls: pd.ExcelFile, sheet_name="FletesT0", header=1) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    df["Cod. Venta"] = pd.to_numeric(df["Cod. Venta"], errors="raise").astype(int)
    return df


def cargar_exhibicion(
    xls: pd.ExcelFile, sheet_name="Exhibición", header=2
) -> pd.DataFrame:
    df = pd.read_excel(xls, sheet_name=sheet_name, header=header)
    df = _clean(df)
    df["Mes"] = _mes(df["Mes"])
    if "Material" in df.columns:
        df["Material"] = pd.to_numeric(df["Material"], errors="coerce").astype("Int64")
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


def _validar_clave_unica(nombre: str, df: pd.DataFrame) -> None:
    """Evita que una tabla de lookup/costos duplique filas al cruzarse con VENTA."""
    claves = CLAVES_UNICAS.get(nombre)
    if not claves or any(c not in df.columns for c in claves):
        return

    duplicados = df.duplicated(claves, keep=False)
    if duplicados.any():
        muestra = df.loc[duplicados, claves].drop_duplicates().head(5)
        detalle = "; ".join(
            ", ".join(f"{c}={row[c]}" for c in claves)
            for _, row in muestra.iterrows()
        )
        raise ValueError(
            f"La fuente '{DATASET_SPECS[nombre]['sheet']}' contiene claves repetidas "
            f"con información diferente. Esto haría ambiguo el cálculo. Ejemplos: {detalle}."
        )


def _combinar_partes(nombre: str, partes: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatena un mismo dataset proveniente de uno o varios archivos."""
    if not partes:
        raise ValueError(f"No hay datos para el dataset '{nombre}'.")

    if len(partes) == 1:
        df = partes[0].reset_index(drop=True)
    else:
        df = pd.concat(partes, ignore_index=True, sort=False)

    # En tablas de referencia/costos, archivos mensuales pueden repetir exactamente
    # las mismas filas. Quitarlas evita dobles costos. VENTA NO se deduplica porque
    # dos filas idénticas pueden representar operaciones legítimas distintas.
    if nombre != "venta":
        df = df.drop_duplicates().reset_index(drop=True)

    _validar_clave_unica(nombre, df)
    return df


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def cargar_todo(path_o_buffer_o_lista) -> dict[str, pd.DataFrame]:
    """Carga AppCMG desde uno o múltiples Excel.

    Acepta:
        cargar_todo("AppCMG.xlsx")
        cargar_todo(uploaded_file)
        cargar_todo([uploaded_file_1, uploaded_file_2, ...])

    Las siete fuentes pueden vivir todas en un mismo archivo o repartidas entre
    varios. Primero se buscan los nombres de hoja canónicos; para hojas con otro
    nombre se intenta reconocer el dataset por la firma de sus columnas.
    """
    fuentes = _normalizar_fuentes(path_o_buffer_o_lista)
    partes: dict[str, list[pd.DataFrame]] = {nombre: [] for nombre in DATASET_SPECS}
    origenes: dict[str, list[str]] = {nombre: [] for nombre in DATASET_SPECS}
    huellas_vistas: dict[str, str] = {}

    for idx, fuente in enumerate(fuentes):
        _rebobinar(fuente)
        nombre_archivo = _nombre_fuente(fuente, idx)

        huella = _huella_fuente(fuente)
        if huella and huella in huellas_vistas:
            raise ValueError(
                f"El archivo '{nombre_archivo}' es idéntico a '{huellas_vistas[huella]}'. "
                "Se detuvo la carga para evitar duplicar ventas y resultados."
            )
        if huella:
            huellas_vistas[huella] = nombre_archivo
        _rebobinar(fuente)

        try:
            xls = pd.ExcelFile(fuente)
        except Exception as exc:
            raise ValueError(f"No se pudo abrir '{nombre_archivo}' como Excel: {exc}") from exc

        datasets_ya_detectados: set[str] = set()

        # 1) Camino rápido y 100% compatible con el archivo actual.
        for nombre, spec in DATASET_SPECS.items():
            if spec["sheet"] in xls.sheet_names:
                partes[nombre].append(
                    LOADERS[nombre](xls, sheet_name=spec["sheet"], header=spec["header"])
                )
                origenes[nombre].append(f"{nombre_archivo} / {spec['sheet']}")
                datasets_ya_detectados.add(nombre)

        # 2) Futuro: hojas con nombres distintos. Se reconocen por columnas.
        hojas_canonicas = {spec["sheet"] for spec in DATASET_SPECS.values()}
        for sheet_name in xls.sheet_names:
            if sheet_name in hojas_canonicas:
                continue

            detectado = _detectar_dataset_y_header(xls, sheet_name)
            if detectado is None:
                continue  # hoja auxiliar/no AppCMG: se ignora

            nombre, header = detectado
            if nombre in datasets_ya_detectados:
                # Si el mismo libro contiene la hoja canónica y además una hoja
                # auxiliar con estructura similar, priorizamos la canónica.
                continue

            partes[nombre].append(
                LOADERS[nombre](xls, sheet_name=sheet_name, header=header)
            )
            origenes[nombre].append(f"{nombre_archivo} / {sheet_name}")
            datasets_ya_detectados.add(nombre)

    faltantes = [
        DATASET_SPECS[nombre]["sheet"]
        for nombre, dfs in partes.items()
        if not dfs
    ]
    if faltantes:
        raise ValueError(
            "No se encontraron todas las fuentes necesarias de AppCMG. "
            f"Faltan: {faltantes}. Pueden estar en un solo Excel o repartidas "
            "entre varios archivos."
        )

    return {
        nombre: _combinar_partes(nombre, dfs)
        for nombre, dfs in partes.items()
    }


if __name__ == "__main__":
    import sys

    paths = sys.argv[1:] or ["AppCMG.xlsx"]
    datos = cargar_todo(paths)
    for nombre, df in datos.items():
        print(f"{nombre:16s} -> {df.shape[0]:6d} filas x {df.shape[1]:2d} columnas")
