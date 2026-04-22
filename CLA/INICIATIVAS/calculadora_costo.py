#!/usr/bin/env python3
"""
Calculadora de Orden de Magnitud — CLA Onboarding Crédito
============================================================
Procesa un Excel con 2 hojas:

  HOJA 1 — "Actividades"
    Col A: INI (código de iniciativa, ej: "INI-01")
    Col B: Plazo por actividad (ej: "2-3 semanas")
    Col C: Equipo de trabajo (ej: "1 Desarrollador Backend (100%) | 1 QA/Tester (50%)")

    → El script calcula por cada fila:
      - Plazo (semanas)
      - FTEs equivalentes
      - Costo HH (UF)
      - Costo HH Al 45% (UF)
      - Costo HH (USD)

  HOJA 2 — "Orden de Magnitud"
    Col A: INI (código)
    Col B: Orden de Magnitud (vacío → el script lo completa)

    → El script:
      1. Suma HH (USD) por INI desde Hoja 1
      2. Agrega licencias, infra, herramientas, capacitación, contingencia
      3. Escribe el Orden de Magnitud en col B
      4. Agrega columnas de desglose (C en adelante)

Uso:
  1. pip install pandas openpyxl
  2. Preparar Excel con las 2 hojas
  3. python calculadora_costo.py
"""

import pandas as pd
import re
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

ARCHIVO_ENTRADA  = "actividades.xlsx"
HOJA_ACTIVIDADES = 0          # primera hoja (índice 0)
HOJA_ORDEN_MAG   = 1          # segunda hoja (índice 1)
ARCHIVO_SALIDA   = "resultado_orden_magnitud.xlsx"

# Índices de columnas en Hoja 1
COL_INI    = 0   # A
COL_PLAZO  = 1   # B
COL_EQUIPO = 2   # C

# Conversiones
UF_A_USD        = 44.84
SEMANAS_POR_MES = 4.33
MARKUP_FACTOR   = 2.34       # markup ~45% margen

# ═══════════════════════════════════════════════════════════════
# TARIFAS POR ROL (UF/mes)
# ═══════════════════════════════════════════════════════════════

TARIFAS_UF_MES = {
    "Analista Funcional":                168,
    "Arquitecto de Datos":               305,
    "Arquitecto de Soluciones":          349,
    "Compliance/Legal":                  247,
    "Consultor Salesforce":              287,
    "Coordinador Proveedor FICO/Ventiv": 202,
    "Coordinador Proveedor Sonda":       185,
    "DBA Oracle":                        263,
    "Desarrollador":                     202,
    "Desarrollador Backend":             214,
    "Desarrollador Frontend":            202,
    "Desarrolladores Backend":           214,
    "DevOps/SRE":                        263,
    "Especialista API Management":       263,
    "Especialista Change Management":    220,
    "Especialista Ciberseguridad":       305,
    "Especialista FICO/Blaze":           339,
    "Especialista Integración/Camel":    275,
    "Especialista Oracle/OCI":           296,
    "Especialista Oracle/WebLogic":      275,
    "Especialista Producto/Comercial":   185,
    "Especialista Riesgo":               247,
    "Especialista Siebel":               271,
    "Ingeniero Cloud GCP":               275,
    "Ingeniero Datos/Cache":             244,
    "Ingeniero ETL":                     232,
    "Ingeniero SRE/Observabilidad":      263,
    "Líder/PM de Iniciativa":            287,
    "PM/Scrum Master":                   247,
    "Product Owner / Líder Negocio":     259,
    "QA Lead":                           220,
    "QA/Tester":                         174,
    "UX/CX Designer":                    202,
    "Usuarios de Negocio para UAT":      113,
    "Abogado/Compliance":                247,
    "Analista Canales":                  185,
    "Analista de Producto":              185,
    "Analista Reclamos":                 168,
    "Data Analyst":                      244,
    "Data Analyst (líder)":              275,
    "Dev TAPP (flags)":                  214,
    "Gerentes":                          305,
    "Nota-taker":                        135,
    "Nota-taker/observador":             135,
    "Product Manager":                   259,
    "Product Manager (co-presentador)":  259,
    "Reclutador participantes":          135,
    "UX Designer":                       202,
    "UX Designer (líder)":               232,
    "UX Researcher":                     202,
    "UX Researcher (líder)":             232,
    "UX Researcher (presentador)":       202,
}
TARIFA_DEFAULT = 90


# ═══════════════════════════════════════════════════════════════
# COSTOS ADICIONALES POR INI (Licencias + Infra + Herram + Capac)
# ═══════════════════════════════════════════════════════════════
# pilar: "tecnico" → contingencia 15% | "gobierno"/"funcional" → 5%

COSTOS_ADICIONALES = {
    "INI-01": {"licencias": 0,       "infra": 8_000,   "herramientas": 0,      "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-02": {"licencias": 0,       "infra": 15_000,  "herramientas": 0,      "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-03": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-04": {"licencias": 0,       "infra": 10_000,  "herramientas": 5_000,  "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-05": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "funcional"},
    "INI-06": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "funcional"},
    "INI-07": {"licencias": 0,       "infra": 15_000,  "herramientas": 0,      "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-08": {"licencias": 0,       "infra": 8_000,   "herramientas": 0,      "capacitacion": 3_000,  "pilar": "funcional"},
    "INI-09": {"licencias": 0,       "infra": 25_000,  "herramientas": 10_000, "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-11": {"licencias": 0,       "infra": 10_000,  "herramientas": 5_000,  "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-12": {"licencias": 0,       "infra": 0,       "herramientas": 8_000,  "capacitacion": 5_000,  "pilar": "gobierno"},
    "INI-13": {"licencias": 0,       "infra": 20_000,  "herramientas": 5_000,  "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-14": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "funcional"},
    "INI-15": {"licencias": 0,       "infra": 10_000,  "herramientas": 0,      "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-16": {"licencias": 0,       "infra": 5_000,   "herramientas": 3_000,  "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-18": {"licencias": 0,       "infra": 15_000,  "herramientas": 0,      "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-20": {"licencias": 0,       "infra": 12_000,  "herramientas": 0,      "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-21": {"licencias": 0,       "infra": 15_000,  "herramientas": 0,      "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-22": {"licencias": 35_000,  "infra": 10_000,  "herramientas": 0,      "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-23": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-24": {"licencias": 0,       "infra": 20_000,  "herramientas": 0,      "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-25": {"licencias": 0,       "infra": 20_000,  "herramientas": 0,      "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-26": {"licencias": 0,       "infra": 10_000,  "herramientas": 0,      "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-27": {"licencias": 15_000,  "infra": 10_000,  "herramientas": 5_000,  "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-28": {"licencias": 10_000,  "infra": 10_000,  "herramientas": 10_000, "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-30": {"licencias": 0,       "infra": 0,       "herramientas": 5_000,  "capacitacion": 3_000,  "pilar": "gobierno"},
    "INI-31": {"licencias": 0,       "infra": 0,       "herramientas": 3_000,  "capacitacion": 2_000,  "pilar": "gobierno"},
    "INI-32": {"licencias": 0,       "infra": 40_000,  "herramientas": 0,      "capacitacion": 8_000,  "pilar": "tecnico"},
    "INI-33": {"licencias": 20_000,  "infra": 15_000,  "herramientas": 10_000, "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-34": {"licencias": 25_000,  "infra": 20_000,  "herramientas": 10_000, "capacitacion": 8_000,  "pilar": "tecnico"},
    "INI-35": {"licencias": 0,       "infra": 35_000,  "herramientas": 5_000,  "capacitacion": 8_000,  "pilar": "tecnico"},
    "INI-36": {"licencias": 0,       "infra": 10_000,  "herramientas": 5_000,  "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-37": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-38": {"licencias": 0,       "infra": 0,       "herramientas": 0,      "capacitacion": 0,      "pilar": "tecnico"},
    "INI-39": {"licencias": 0,       "infra": 10_000,  "herramientas": 5_000,  "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-40": {"licencias": 0,       "infra": 10_000,  "herramientas": 5_000,  "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-41": {"licencias": 5_000,   "infra": 0,       "herramientas": 5_000,  "capacitacion": 3_000,  "pilar": "tecnico"},
    "INI-42": {"licencias": 200_000, "infra": 0,       "herramientas": 15_000, "capacitacion": 20_000, "pilar": "tecnico"},
    "INI-43": {"licencias": 10_000,  "infra": 30_000,  "herramientas": 10_000, "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-44": {"licencias": 5_000,   "infra": 0,       "herramientas": 5_000,  "capacitacion": 8_000,  "pilar": "gobierno"},
    "INI-46": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "funcional"},
    "INI-47": {"licencias": 0,       "infra": 5_000,   "herramientas": 0,      "capacitacion": 2_000,  "pilar": "tecnico"},
    "INI-48": {"licencias": 0,       "infra": 20_000,  "herramientas": 5_000,  "capacitacion": 5_000,  "pilar": "tecnico"},
    "INI-49": {"licencias": 0,       "infra": 0,       "herramientas": 5_000,  "capacitacion": 3_000,  "pilar": "funcional"},
}


# ═══════════════════════════════════════════════════════════════
# FUNCIONES — CÁLCULO HH (sin cambios)
# ═══════════════════════════════════════════════════════════════

def plazo_a_semanas(texto):
    """Convierte '2-3 semanas' → 2.5 (promedio del rango)."""
    texto = str(texto).strip()
    m = re.match(r"(\d+)\s*-\s*(\d+)\s*semanas?", texto)
    if m:
        return round((int(m.group(1)) + int(m.group(2))) / 2, 1)
    m2 = re.match(r"(\d+)\s*semanas?", texto)
    if m2:
        return float(m2.group(1))
    return None


def parsear_equipo(texto):
    """Parsea '1 Dev Backend (100%) | 1 QA (50%)' → [(1,'Dev Backend',100), ...]"""
    recursos = []
    for parte in str(texto).split("|"):
        parte = parte.strip()
        m = re.match(r"(\d+)\s+(.+?)\s*\((\d+)%\)", parte)
        if m:
            recursos.append((int(m.group(1)), m.group(2).strip(), int(m.group(3))))
        else:
            m2 = re.match(r"(.+?)\s*\((\d+)%\)", parte)
            if m2:
                recursos.append((1, m2.group(1).strip(), int(m2.group(2))))
    return recursos


def calcular_ftes(texto_equipo):
    """FTEs = Σ cantidad × dedicación%."""
    return round(sum(c * (d / 100) for c, _, d in parsear_equipo(texto_equipo)), 2)


def calcular_costo_uf(texto_equipo, semanas):
    """Costo HH = Σ (cantidad × dedicación% × tarifa × semanas/4.33)."""
    if semanas is None:
        return None
    costo = 0.0
    for cant, rol, ded in parsear_equipo(texto_equipo):
        tarifa = TARIFAS_UF_MES.get(rol, TARIFA_DEFAULT)
        costo += cant * (ded / 100) * tarifa * (semanas / SEMANAS_POR_MES)
    return round(costo, 1)


# ═══════════════════════════════════════════════════════════════
# FUNCIONES — ORDEN DE MAGNITUD (nuevas)
# ═══════════════════════════════════════════════════════════════

def calcular_orden_magnitud_por_ini(hh_por_ini):
    """
    Recibe dict {INI: hh_usd_total} y retorna dict {INI: {desglose completo}}.
    Orden de Magnitud = HH + Licencias + Infra + Herramientas + Capacitación + Contingencia
    """
    resultado = {}
    for ini, hh_usd in hh_por_ini.items():
        ca = COSTOS_ADICIONALES.get(ini, {"licencias": 0, "infra": 0, "herramientas": 0, "capacitacion": 0, "pilar": "tecnico"})

        pilar = ca["pilar"]
        pct_cont = 0.05 if pilar in ("gobierno", "funcional") else 0.15
        contingencia = round(hh_usd * pct_cont, 2)

        lic   = ca["licencias"]
        infra = ca["infra"]
        herr  = ca["herramientas"]
        capac = ca["capacitacion"]

        orden_mag = hh_usd + lic + infra + herr + capac + contingencia

        resultado[ini] = {
            "hh_usd":        round(hh_usd, 2),
            "licencias":     lic,
            "infra":         infra,
            "herramientas":  herr,
            "capacitacion":  capac,
            "contingencia":  round(contingencia, 2),
            "orden_magnitud": round(orden_mag, 2),
            "pilar":         pilar,
            "pct_cont":      pct_cont,
        }
    return resultado


# ═══════════════════════════════════════════════════════════════
# EJECUCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  CALCULADORA ORDEN DE MAGNITUD — CLA Onboarding Crédito    ║")
    print("║  Hoja 1: Actividades (HH)  |  Hoja 2: Orden de Magnitud   ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # ──────────────────────────────────────────────────────────
    # PASO 1: Leer Hoja 1 (Actividades) y calcular HH
    # ──────────────────────────────────────────────────────────
    print(f"\n[1/4] Leyendo Hoja 1 de {ARCHIVO_ENTRADA}...")
    df_act = pd.read_excel(ARCHIVO_ENTRADA, sheet_name=HOJA_ACTIVIDADES)

    col_ini    = df_act.columns[COL_INI]
    col_plazo  = df_act.columns[COL_PLAZO]
    col_equipo = df_act.columns[COL_EQUIPO]

    print(f"      Col INI:    '{col_ini}' (col {COL_INI})")
    print(f"      Col Plazo:  '{col_plazo}' (col {COL_PLAZO})")
    print(f"      Col Equipo: '{col_equipo}' (col {COL_EQUIPO})")
    print(f"      Filas: {len(df_act)} actividades | INIs: {df_act[col_ini].nunique()}")

    df_act["Plazo (semanas)"]       = df_act[col_plazo].apply(plazo_a_semanas)
    df_act["FTEs equivalentes"]     = df_act[col_equipo].apply(calcular_ftes)
    df_act["Costo HH (UF)"]        = df_act.apply(
        lambda r: calcular_costo_uf(r[col_equipo], r["Plazo (semanas)"]), axis=1)
    df_act["Costo HH Al 45% (UF)"] = df_act["Costo HH (UF)"] * MARKUP_FACTOR
    df_act["Costo HH (USD)"]       = df_act["Costo HH Al 45% (UF)"] * UF_A_USD

    total_hh = df_act["Costo HH (USD)"].sum()
    print(f"      → Total HH: ${total_hh:,.0f} USD")

    # ──────────────────────────────────────────────────────────
    # PASO 2: Agrupar HH por INI
    # ──────────────────────────────────────────────────────────
    print(f"\n[2/4] Agrupando HH por INI...")
    hh_por_ini = df_act.groupby(col_ini)["Costo HH (USD)"].sum().to_dict()
    print(f"      → {len(hh_por_ini)} INIs procesadas")

    # ──────────────────────────────────────────────────────────
    # PASO 3: Calcular Orden de Magnitud por INI
    # ──────────────────────────────────────────────────────────
    print(f"\n[3/4] Calculando Orden de Magnitud por INI...")
    om_por_ini = calcular_orden_magnitud_por_ini(hh_por_ini)

    # Verificar INIs sin mapear
    sin_mapear = set(hh_por_ini.keys()) - set(COSTOS_ADICIONALES.keys())
    if sin_mapear:
        print(f"      ⚠️  INIs sin costos adicionales: {sorted(sin_mapear)}")
        print(f"         → Se les asigna: $0 adicional + contingencia 15%")
    else:
        print(f"      ✅ Todas las INIs mapeadas")

    total_om = sum(v["orden_magnitud"] for v in om_por_ini.values())
    print(f"      → Total Orden de Magnitud: ${total_om:,.0f} USD (factor {total_om/total_hh:.2f}x)")

    # ──────────────────────────────────────────────────────────
    # PASO 4: Leer Hoja 2 y completar Orden de Magnitud
    # ──────────────────────────────────────────────────────────
    print(f"\n[4/4] Escribiendo resultados...")

    # Leer Hoja 2
    df_om = pd.read_excel(ARCHIVO_ENTRADA, sheet_name=HOJA_ORDEN_MAG)
    col_ini_h2 = df_om.columns[0]  # A = INI

    # Construir columnas de desglose
    df_om["HH (USD)"]              = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("hh_usd", 0))
    df_om["Licencias (USD)"]       = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("licencias", 0))
    df_om["Infra Cloud (USD)"]     = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("infra", 0))
    df_om["Herramientas (USD)"]    = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("herramientas", 0))
    df_om["Capacitación (USD)"]    = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("capacitacion", 0))
    df_om["Contingencia (USD)"]    = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("contingencia", 0))
    df_om["Orden de Magnitud"]     = df_om[col_ini_h2].map(lambda x: om_por_ini.get(x, {}).get("orden_magnitud", 0))

    # ──────────────────────────────────────────────────────────
    # GUARDAR: Hoja 1 con HH calculado + Hoja 2 con OM completo
    # ──────────────────────────────────────────────────────────
    with pd.ExcelWriter(ARCHIVO_SALIDA, engine="openpyxl") as writer:
        df_act.to_excel(writer, sheet_name="Actividades", index=False)
        df_om.to_excel(writer, sheet_name="Orden de Magnitud", index=False)

    print(f"      📁 Guardado: {ARCHIVO_SALIDA}")
    print(f"         Hoja 'Actividades':       {len(df_act)} filas (actividades con HH)")
    print(f"         Hoja 'Orden de Magnitud': {len(df_om)} filas (INIs con desglose)")

    # ──────────────────────────────────────────────────────────
    # RESUMEN EN CONSOLA
    # ──────────────────────────────────────────────────────────
    print(f"\n{'═'*90}")
    print(f"  RESUMEN: ORDEN DE MAGNITUD POR INI")
    print(f"{'═'*90}")
    print(f"  {'INI':8s} │ {'HH (USD)':>12s} │ {'Licencias':>10s} │ {'Infra':>10s} │ {'Herram.':>10s} │ {'Capac.':>8s} │ {'Conting.':>10s} │ {'ORD. MAG.':>12s}")
    print(f"  {'─'*8}─┼─{'─'*12}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*8}─┼─{'─'*10}─┼─{'─'*12}")

    for ini in sorted(om_por_ini.keys()):
        v = om_por_ini[ini]
        print(f"  {ini:8s} │ ${v['hh_usd']:>10,.0f} │ ${v['licencias']:>8,d} │ ${v['infra']:>8,d} │ ${v['herramientas']:>8,d} │ ${v['capacitacion']:>6,d} │ ${v['contingencia']:>8,.0f} │ ${v['orden_magnitud']:>10,.0f}")

    # Totales
    t_hh   = sum(v["hh_usd"] for v in om_por_ini.values())
    t_lic  = sum(v["licencias"] for v in om_por_ini.values())
    t_inf  = sum(v["infra"] for v in om_por_ini.values())
    t_her  = sum(v["herramientas"] for v in om_por_ini.values())
    t_cap  = sum(v["capacitacion"] for v in om_por_ini.values())
    t_con  = sum(v["contingencia"] for v in om_por_ini.values())
    t_om   = sum(v["orden_magnitud"] for v in om_por_ini.values())

    print(f"  {'─'*8}─┼─{'─'*12}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*8}─┼─{'─'*10}─┼─{'─'*12}")
    print(f"  {'TOTAL':8s} │ ${t_hh:>10,.0f} │ ${t_lic:>8,d} │ ${t_inf:>8,d} │ ${t_her:>8,d} │ ${t_cap:>6,d} │ ${t_con:>8,.0f} │ ${t_om:>10,.0f}")

    print(f"\n  📊 Composición Orden de Magnitud:")
    print(f"     HH (Consultoría):     ${t_hh:>12,.0f}  ({t_hh/t_om*100:>5.1f}%)")
    print(f"     Licencias:            ${t_lic:>12,.0f}  ({t_lic/t_om*100:>5.1f}%)")
    print(f"     Infra Cloud:          ${t_inf:>12,.0f}  ({t_inf/t_om*100:>5.1f}%)")
    print(f"     Herramientas:         ${t_her:>12,.0f}  ({t_her/t_om*100:>5.1f}%)")
    print(f"     Capacitación:         ${t_cap:>12,.0f}  ({t_cap/t_om*100:>5.1f}%)")
    print(f"     Contingencia:         ${t_con:>12,.0f}  ({t_con/t_om*100:>5.1f}%)")
    print(f"     {'─'*50}")
    print(f"     ORDEN DE MAGNITUD:    ${t_om:>12,.0f}  (Factor: {t_om/t_hh:.2f}x sobre HH)")

    print(f"\n{'═'*90}")
    print(f"  ✅ PROCESO COMPLETADO")
    print(f"{'═'*90}")
