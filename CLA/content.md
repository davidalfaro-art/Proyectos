# 🔵 SECCIÓN SUPERIOR — FLUJO AS-IS

## Consulta 1: Flujo As-Is — Paso a Paso Secuencial

| Paso | Etapa | Descripción | Sistemas Involucrados |
|------|-------|-------------|----------------------|
| 1 | **ETAPA 1 — Identificación y Validación del Afiliado** | Se verifica RUT, estado de afiliación, vigencia, datos personales, contrato y remuneración. Se consulta si existe oferta pre-aprobada (Base Aprobados). Si el afiliado no es elegible → rechazo. Si es elegible → avanza a Etapa 2. | BFF, Base Aprobados, MenuAndes, Siebel |
| 2 | **ETAPA 2 — Pre-Evaluación (Scoring)** | Se simula el monto máximo pre-aprobado. Se generan 3 alternativas de crédito mediante **triple simulación** (3 llamadas SOAP a FlexCube por cada preevaluación). Se ejecuta el scoring contra el motor FICO. | BLAZE, FICO, MenuAndes, Base Aprobados, FlexCube |
| 3 | **ETAPA 3 — Evaluación de Crédito** | Se presenta al cliente 3 alternativas. El motor ejecuta Knockout + ProcesaSolicitud + Avales (16+ servicios secuenciales). **Punto de decisión: ¿Aprobación automática?** → **Sí**: Aprobado, avanza a Selección de Oferta. → **No (Presencial)**: Derivación a revisión manual (Llave 1/5, Comité) gestionada por ejecutivo. → **No (Digital/TAPP)**: **Rechazo automático** — TAPP no tiene revisión manual excepto fraude. | FICO, FlexCube, Siebel (orquestación vía Servicio 147), MenuAndes, Experian, Registro Civil, Sinacofi |
| 4 | **Selección de Oferta** | El cliente elige una alternativa: monto final, plazo/cuotas y forma de desembolso. Si acepta → avanza. Si no acepta → fin del proceso. | — |
| 5 | **ETAPA 4 — Generación del Set Documental** | Se genera: solicitud de crédito, mutuo, pólizas, condiciones, pagaré, mandato (según monto). | FlexCube, BI Publisher |
| 6 | **ETAPA 5 — Firma del Cliente y Custodia** | Firma digital o presencial. Mandato remoto en algunos flujos. Almacenamiento de documentos. | WebCenter Content, eSign |
| 7 | **ETAPA 6 — Control Documental** | Confirmación de documentación vigente, legibilidad, firma correcta, checklist completo. Si el set no está completo/válido → Observación/Reproceso (retrocede a firma). | WebCenter Content |
| 8 | **ETAPA 7 — Formalización y Desembolso** | Se crea/activa el crédito, se envía al proceso financiero y se desembolsa según método seleccionado. | FlexCube, SAP |

---

## Consulta 2: Principales Problemas del Flujo As-Is

### Motor FICO como Punto Central de Falla
- **Degradación recurrente**: Patrón de caída martes/jueves/domingo ~13:27 UTC, con MTTR de 21 min y ~2,250 evaluaciones perdidas/semana (FG-01)
- **Colapso a baja concurrencia**: El motor se congela a 15-17 usuarios simultáneos con solo 14% de ocupación del executor (FG-28/FG-10)
- **134,446 errores genéricos** registrados como "Error Motor FICO" sin desagregación por causa raíz (FG-03)

### Duplicidad de Invocaciones
- **Doble invocación sin reutilización**: La preevaluación (Etapa 2) y la evaluación formal (Etapa 3) ejecutan el mismo recorrido completo contra FICO sin compartir ningún dato. Ambas entregan el mismo valor — la evaluación formal no agrega valor diferencial (FG-20, FG-38)
- **Flujos internos 100% duplicados**: Knockout y ProcesaSolicitud son idénticos: 13 grupos, mismos sub-flujos, mismos servicios (FG-11)
- **Triple simulación**: Cada preevaluación genera 3 llamadas SOAP a FlexCube para obtener opciones de cuota → multiplica probabilidad de falla (FG-18)

### Datos Null y Knockouts por Desincronización
- **12,493 knockouts** entre Oct 2025–Feb 2026 por desincronización de datos entre MenuAndes, FlexCube y Siebel
- ~10% corresponde a errores del servicio EAI-005/FlexCube; la causa del 90% restante no está desagregada
- **BigQuery síncrono**: Agrega 4.3s de latencia al camino crítico y es punto único de falla

### Canal Digital Limitado
- **277,407 solicitudes/mes** rechazadas automáticamente porque TAPP no permite derivación humana (FG-19, FG-31)
- **TAPP_NOR genera 4.4x más carga pero solo 1.4x más ventas** que TAPP_APB (459,820 vs 105,477 preevaluaciones)
- **Conversión TAPP_NOR: 3.6%** vs TAPP_APB: 11%
- **Sin retomabilidad entre canales**: Si un cliente abandona TAPP y va a sucursal, reinicia desde cero (FG-36)
- **Sin métricas de abandono digital** ni funnel de conversión (FG-24)

### Secuencialidad y Latencia
- **16+ servicios de avales se ejecutan secuencialmente** sin dependencia entre sí — tiempo total = suma de todas las latencias (FG-13)
- **Tokens OAG/ApiGee obtenidos secuencialmente** con lógica duplicada, agregando 100-500ms por ejecución (FG-14)
- **Pirámide de timeouts invertida**: Canal 40s / Intermedio 20s / Servicio 10s (FG-05)

### Resiliencia Inexistente
- **Sin circuit breakers**: 1 servicio falla → 13 caen simultáneamente (FG-05)
- **Elasticsearch saturado** con circuit breaker de APM abierto por 5 meses (FG-05)
- **Apache Ignite**: Genera falsos positivos que terminan nodos sanos → cascadas de 214,141 errores 5XX (FG-02)
- **Frontend inyecta solicitudes sin restricción** cuando el backend falla (FG-32)

### Gobernanza y Operaciones
- **Sin ownership E2E** del flujo de crédito desde noviembre 2024 (FG-18)
- **Sin CMDB**: 62% de componentes sin documentación técnica (FG-28)
- **0 de 7 proveedores con SLA formalizado** — FICO concentra 73.7% de incidentes
- **Sin pruebas de carga reales** — nunca se probó el flujo completo (FG-22)
- **5 personas clave** concentran todo el conocimiento sin runbooks ni transferencia
- **Madurez TOGAF: 1.21/5** — dimensiones críticas: proveedores, catálogo, infraestructura, observabilidad, seguridad

### Otros Problemas
- **Baja de Base Aprobados**: Solo funciona mediante job diario en Control-M → riesgo de duplicidad de créditos (FG-25)
- **FlexCube no cierra contable sábados/domingos** → crédito aprobado viernes queda en estado intermedio hasta lunes (FG-26)
- **Servicio 147 (anti-patrón)**: Orquestador en Siebel que bloquea un hilo completo por solicitud, catalogado como inmodificable
- **Reprocesos documentales**: Documentación observada obliga retrocesos de Etapa 6 a Etapa 5 (FG-34)
- **Cadena de obsolescencia circular**: Nashorn → Forms 10g → Oracle 12 → MenuAndes → bloquea modernización completa (FG-30)

---

# 🟢 TO-BE 1 — OPCIÓN 1: CONVIVENCIA UNIFICADA
**Bajo esfuerzo / Alto impacto / Creación de piezas nuevas de soporte**
*Horizonte 1: Estabilización Crítica (≤3 meses)*

## Consulta 3: Flujo To-Be 1 — Paso a Paso

**Principio rector**: No se modifica el flujo funcional ni se reemplazan componentes. Se estabiliza la plataforma actual, se crean piezas nuevas de soporte (alertas, métricas, gobierno) y se habilita visibilidad. Las 7 etapas del As-Is se mantienen, pero se intervienen los componentes subyacentes:

| Paso | Intervención | Iniciativa | Opción | Pieza Nueva / Cambio |
|------|-------------|------------|--------|---------------------|
| 1 | **Estabilizar Apache Ignite** | INI-03 | Opción 1 | Ajustar failureDetectionTimeout, incrementar thread pools (pub/svc/sys ≥16), configurar backup ≥1, habilitar monitoreo de nodos/memoria/hit-miss ratio. **Elimina causa raíz T6 confirmada** |
| 2 | **Estabilizar infraestructura** | INI-15 | Opción 1 | Desactivar agente APM fantasma (elimina 309K conexiones/hora = 80% errores gateway). Balancear OSB (de 82.8% vs 44.3% a equitativo). Ajustar Survivor space OSB ≥256MB. Depurar tráfico nodo DPC. Corregir memory leak Cassandra. Incrementar Oracle DB de 8GB a ≥32GB. Rotación automática de logs |
| 3 | **Alertas automatizadas + protocolo contingencia** | INI-10 | Opción 1 | **Pieza nueva**: Alertas automáticas en Grafana/Elasticsearch (ya existentes) que reduzcan MTTD de 45 min a ≤5 min. Corregir health check que reporta "success" ante 504 reales. Restaurar APM (5 meses inactivo). Monitoreo Kafka consumer. Protocolo documentado de contingencia (3 escenarios). GC logs + thread dumps habilitados |
| 4 | **Instrumentar funnel digital** | INI-05 | Opción 1 | **Pieza nueva**: Instrumentación sin cambiar el flujo — captura de métricas en cada transición E1→E2→...→E7. Segmentación por canal (TAPP_APB, TAPP_NOR, Presencial). Medición de abandono digital. Cálculo de costo por evaluación. Dashboard en Grafana (ARI-10 ya habilitó acceso) |
| 5 | **Rate limiting + protección frontend** | INI-06 | Opción 1 | **Pieza nueva (N-04)**: Rate limiting por RUT en preevaluación + evaluación. Detección de degradación en BFF con deshabilitación proactiva. Coordinación marketing-plataforma antes de campañas push. Persistencia de estado ante interrupción |
| 6 | **Migración completa a Blaze v7, apagado v4** | INI-02 | Opción 1 | Completar paridad de reglas v4→v7 con validación funcional de Riesgo. Apagar v4 para crédito → eliminar Nashorn. **Fin del doble licenciamiento** (ahorro en costos). Homologar FICO OKE con producción |
| 7 | **Establecer Owner E2E + gobierno** | INI-12 | *(transversal)* | **Pieza nueva**: Owner E2E con autoridad transversal — primera iniciativa a ejecutar (≤30 días). Matriz RACI por componente. CAB fortalecido con fast track. Cadencias formalizadas (daily/semanal/quincenal). Gestión formal de deuda técnica. **Habilitador #1 de todo lo demás** |

## Consulta 4: Beneficios, Cambios y Estimaciones — To-Be 1

### (a) Beneficios
- **Evaluaciones perdidas/semana**: de ~2,250 → **<500**
- **MTTD**: de ~45 min → **≤5 min** (alertas automatizadas)
- **Conversión E2E**: de 5.0% → **5.5%**
- **80% de errores gateway eliminados** (agente APM fantasma desactivado: -309,078 conexiones/hora)
- **Causa raíz T6 eliminada** (Ignite estabilizado) → fin de cascadas de 214,141 errores 5XX
- **Motor único Blaze v7** → -2,076 excepciones Nashorn + fin doble licenciamiento
- **Primer owner E2E designado** (quiebre del patrón de 7 años sin resolución de fondo)
- **Primeras métricas de funnel digital** disponibles para el negocio
- **Plataforma protegida ante picos de campañas** (rate limiting)
- **Madurez TOGAF**: de 1.21 → **1.8/5**

### (b) Principales Cambios respecto al As-Is
| Aspecto | As-Is | To-Be 1 (Opción 1) |
|---------|-------|---------------------|
| Monitoreo | Sin alertas, health check reporta success ante 504 reales | Alertas automatizadas, MTTD ≤5 min |
| Motor de reglas | Blaze v4 + v7 + Nashorn (doble licenciamiento) | Motor único Blaze v7, Nashorn eliminado |
| Governance | Sin owner E2E desde nov 2024, sin CMDB, sin RACI | Owner designado, RACI por componente, CAB con fast track |
| Observabilidad | Sin funnel, sin métricas de abandono digital | Dashboard con funnel por canal en Grafana |
| Infraestructura | Agente APM fantasma, OSB desbalanceado, logs sin rotación | Limpieza completa, balanceo equitativo, rotación automática |
| Protección frontend | BFF inyecta sin restricción durante degradación | Rate limiting por RUT (N-04) + backpressure |
| Bus de integración | OSB 11g sin circuit breakers, sin resiliencia | **OSB 11g se mantiene** (sin cambio — se reemplaza en To-Be 2) |
| Apache Ignite | Mata nodos sanos por falsos positivos | Estabilizado: failureDetection ajustado, pools incrementados |

### (c) Estimaciones de Tiempo y Costo
| Parámetro | Estimación |
|-----------|------------|
| **Plazo** | **≤3 meses** (Semanas 1-12) |
| **Iniciativas** | INI-02, INI-03, INI-05, INI-06, INI-10, INI-12, INI-15 |
| **Esfuerzo predominante** | Bajo (INI-03, INI-10, INI-12, INI-15) a Medio (INI-05, INI-06) a Alto (INI-02) |
| **Naturaleza** | Configuración, instrumentación, governance y validación de paridad v4→v7 — sin reemplazo del bus de integración |
| **ARIs baseline** | 19 ARIs ya ejecutadas + 5 ARIs P1 (hacer ya) + 20 ARIs P2 |
| **Costo licenciamiento** | **$0** — Todo es configuración (Grafana/Elasticsearch ya existen), decisión organizacional (owner E2E), y al apagar v4 se **ahorra** el costo de una licencia |
| **Costo principal** | Horas-equipo interno + ventanas de mantenimiento + horas vendor FICO para validación paridad v7 |

---

# 🟡 TO-BE 2 — OPCIÓN 2: REEMPLAZAR BUS (APACHE CAMEL)
**Esfuerzo medio / Cambio de piezas existentes**
*Horizonte 2: Transformación del Proceso (3-6 meses)*

## Consulta 5: Flujo To-Be 2 — Paso a Paso

**Principio rector**: Se introduce **Apache Camel** como reemplazo del bus de integración OSB 11g, habilitando circuit breakers nativos, resiliencia, métricas y trazas. Se modifica sustancialmente el flujo funcional: consolidación del motor, derivación digital, caché transversal. El flujo pasa de 7 a 10 etapas.

**Migración OSB → Camel (estrategia gradual, coexistencia durante transición):**

| Fase | Qué migra | Plazo |
|------|-----------|-------|
| Fase 1 | Ruta de evaluación FICO (flujo principal) | Mes 1-2 |
| Fase 2 | Rutas servicios EAI (005, 105, 080, etc.) | Mes 2-3 |
| Fase 3 | Rutas servicios externos (Experian, Sinacofi) | Mes 3-4 |
| Fase 4 | Apagar OSB 11g (todo corre en Camel) | Mes 5-6 |

### Flujo To-Be 2 — Etapas

| Paso | Etapa TO-BE | Descripción de Mejora | Iniciativa(s) | Rol de Camel |
|------|-------------|----------------------|---------------|-------------|
| 1 | **ETAPA 1 — Entrada Multicanal Unificada** | Digital (TAPP), Presencial (Siebel), SVP → alimentan el mismo flujo. Persistencia de estado desde ingreso (Redis). Rate limiting por RUT activo. ID de canal para trazabilidad. | INI-04, INI-06 | Camel normaliza requests de todos los canales |
| 2 | **ETAPA 2 — Validación de Datos y Documentos (anticipada)** | Validación automática con contratos formales (JSON Schema/XSD). **Validación documental anticipada**: completitud y legibilidad se verifican **antes** de la evaluación. Dato incompleto → solicitud "pendiente" (no descartada). | INI-09 | — |
| 3 | **ETAPA 3 — Pre-filtro Inteligente (NUEVA)** | Filtros livianos previos al motor — reglas regulatorias (CMF/SERNAC) ejecutadas sin invocar FICO. Segmentación: campaña (40 reglas) vs normal (120 reglas). Resultado: avanza a evaluación o derivación con contexto (no rechazo automático). | INI-01 | — |
| 4 | **ETAPA 4 — Evaluación de Crédito (flujo único)** | Knockout + ProcesaSolicitud **fusionados en flujo único** con caché transversal compartida (Redis, N-02). **Avales en paralelo** (16+ servicios vía Camel multicast) → reducción 60-75% tiempo. Caché por RUT para Experian y servicios EAI. Gestor de tokens centralizado (N-03) con TTL — implementado como componente nativo de Camel. Evaluación única (sin doble invocación). | INI-01, INI-08 | **Camel orquesta**: multicast para avales paralelos, circuit breaker por integración (Resilience4j), caché y tokens como componentes nativos |
| 5 | **ETAPA 5 — Decisión y Derivación (rediseñada)** | Motor retorna: **Aprobado / Derivar (Llave 1/5) / Rechazado**. Canal digital (cambio clave): "Derivar" → cola de derivación digital (Kafka, N-12) con SLA definido. "Rechazado" → razón contextualizada + opción sucursal con solicitud retomable. **Baja online de Base Aprobados**: microservicio en tiempo real (N-08). | INI-04 | — |
| 6 | **ETAPA 6 — Selección de Oferta** | 3 alternativas como hoy. Estado persistido en Redis: interrupción → retoma donde quedó. | INI-04 | — |
| 7 | **ETAPA 7 — Generación del Set Documental** | Generación automatizada con datos ya validados en Etapa 2. | — | — |
| 8 | **ETAPA 8 — Firma y Custodia** | Reproceso de firma solo por error formal (datos ya validados). | — | — |
| 9 | **ETAPA 9 — Control Documental** | Reducción significativa de observaciones por validación anticipada. | — | — |
| 10 | **ETAPA 10 — Formalización y Desembolso** | Sincronización FlexCube condicionada al término de pagos (sin competencia por ventana). BigQuery eliminado del camino crítico → caché local Redis (N-07). | INI-09 | — |

**Componentes nuevos habilitados por Camel:**
- **Apache Camel** (open source, $0): Reemplaza OSB 11g como bus de integración con circuit breakers nativos (Resilience4j), retry con backoff, métricas (Micrometer → Grafana), trazas (OpenTelemetry → Jaeger), soporte SOAP+REST+Kafka
- **N-02 Caché transversal** (Redis): Implementada como componente nativo Camel — caché compartida por RUT entre flujos
- **N-03 Gestor de tokens** (Camel): Token único OAG + ApiGee con TTL
- **N-05 Store de estado** (Redis): Persistencia de solicitud para retomabilidad
- **N-07 Caché scoring** (Redis): Variables BigQuery precalculadas localmente
- **N-08 Baja Base Aprobados** (microservicio): Baja en tiempo real al aprobar
- **N-12 Cola de derivación** (Kafka): Cola para derivación digital con SLA

## Consulta 6: Beneficios, Cambios y Estimaciones — To-Be 2

### (a) Beneficios
- **Motor opera con flujo único**: -60/70% invocaciones
- **Avales en paralelo vía Camel multicast**: -60/75% tiempo de evaluación
- **OSB 11g reemplazado por Apache Camel**: Circuit breakers en las 24 integraciones (de 0 a 24), cascada eliminada, métricas y trazas nativas
- **Canal digital con derivación habilitada**: 277,407 solicitudes/mes recuperables comercialmente
- **Retomabilidad entre canales** operativa (Redis)
- **BigQuery eliminado del camino crítico**: -4,312ms de latencia
- **12,493 knockouts reducidos** (dependencias batch corregidas en Control-M)
- **3,694 errores residuales eliminados** (Mambu + 3 DUMMY removidos)
- **35,324 errores EAI reducidos significativamente** (caché por RUT)
- Evaluaciones perdidas/semana: **<100**
- MTTD: **≤2 min**
- Conversión E2E: de 5.5% → **≥7%**
- Conversión TAPP_NOR: de 4.0% → **≥6%**
- Derivaciones digitales gestionadas: de 0% → **≥40%**

### (b) Principales Cambios respecto al As-Is
| Aspecto | As-Is | To-Be 2 (Opción 2: Camel) |
|---------|-------|---------------------------|
| Bus de integración | **OSB 11g** (sin circuit breakers, sin resiliencia, timeout 50.9s) | **Apache Camel** (Resilience4j, Micrometer, OpenTelemetry, SOAP+REST+Kafka) |
| Circuit breakers | 0 en toda la cadena | 24 (1 por integración) |
| Evaluación | Doble invocación sin reutilización | Evaluación única con flujo consolidado |
| Flujos internos FICO | Knockout + ProcesaSolicitud duplicados al 100% | Flujo único con caché compartida |
| Avales | 16+ servicios secuenciales vía OSB | **Ejecución paralela vía Camel multicast** (60-75% menos tiempo) |
| Caché | No existe en ninguna integración | **Redis como componente nativo Camel** — caché por RUT |
| Tokens | Secuencial con lógica duplicada (+100-500ms) | **Gestor centralizado en Camel** con TTL |
| Canal digital | Binario: aprobado o rechazo | Aprobado / Derivar a analista / Rechazo con contexto |
| Retomabilidad | Inexistente (reinicio desde cero) | Persistencia de estado en Redis + handoff con contexto |
| Validación documental | Posterior (Etapas 5-6) con retrocesos | Anticipada en Etapa 2 |
| Baja Base Aprobados | Job diario Control-M | Microservicio en tiempo real |
| BigQuery | Síncrono en camino crítico (4,312ms) | Caché local Redis precalculada |
| Servicios DUMMY | Mambu + 3 EAI activos (3,694 errores) | Eliminados |

### (c) Estimaciones de Tiempo y Costo
| Parámetro | Estimación |
|-----------|------------|
| **Plazo** | **3-6 meses** (Meses 4-6, sobre la base del To-Be 1 completado) |
| **Iniciativas** | INI-01, INI-04, INI-07, INI-08, INI-09 |
| **Esfuerzo** | Alto (INI-01, INI-04) a Medio (INI-07, INI-08, INI-09) |
| **Naturaleza** | Reemplazo gradual OSB→Camel (coexistencia), refactorización de flujos internos FICO, desarrollo de componentes nuevos (N-02 a N-12), corrección de cadena batch |
| **Costo licenciamiento** | **$0** — Apache Camel es open source (Apache License 2.0). Redis open source. Control-M ya existe. Todo es desarrollo interno |
| **Costo principal** | Horas vendor FICO/Ventiv (refactorización motor), desarrollo Java interno (rutas Camel), horas equipo Riesgo (validación), conocimiento Enterprise Integration Patterns |
| **Dependencias críticas** | INI-03 (Ignite estable) → INI-01 (motor). INI-07 (Camel/resiliencia) → INI-04 (derivación digital). INI-02 (v7) ya completada en To-Be 1 |

---

# 🔴 TO-BE 3 — OPCIÓN 3: TOGAF COMPLETO + CAMEL CONSOLIDADO
**Esfuerzo alto / Largo plazo / Cambio de piezas y organizacional**
*Horizonte 3: Escalabilidad y Modernización (>6 meses)*

## Consulta 7: Flujo To-Be 3 — Paso a Paso

**Principio rector**: Se mantiene el flujo de 10 etapas del To-Be 2 y se le aplican dos capas transformacionales:

1. **Apache Camel consolidado**: OSB 11g formalmente apagado (Fase 4 de migración completada). Camel opera como único bus. Se ejecuta el plan de modernización sobre esa base.
2. **TOGAF completo**: Marco de gobierno de arquitectura empresarial aplicado integralmente para resolver los problemas organizacionales evidenciados — madurez de 1.21/5 a 3.0/5. Incluye parametrización de reglas por negocio, trazabilidad E2E, SLAs con proveedores, runbooks/DRP, y modelo de gobierno maduro.

### Intervenciones To-Be 3

| Paso | Intervención | Iniciativa | Opción | Impacto en el Flujo |
|------|-------------|------------|--------|---------------------|
| 1 | **Apagar OSB 11g formalmente** | INI-16 (Fase 4) | Camel + TOGAF | OSB descomisionado. **Todo corre en Camel**. Elimina componente obsoleto del ecosistema. Fin de la cadena de dependencia OSB 11g |
| 2 | **Migrar MenuAndes a Oracle APEX** | INI-16 (Fase 1) | TOGAF | Forms 10g eliminado → MenuAndes con frontend moderno (APEX) + APIs REST. Desbloquea modernización de Oracle DB. Reduce dependencia estructural |
| 3 | **Upgrade Oracle 12 → 19c/21c** | INI-16 (Fase 2) | TOGAF | Parches de seguridad activos, CVEs mitigados. Fin del riesgo de operar sin soporte. Desbloqueado por Fase 1 (ya sin Forms) |
| 4 | **Evaluar upgrade/reemplazo WebLogic 10.3.6** | INI-16 (Fase 3) | TOGAF | WebLogic fuera de soporte → evaluación de upgrade a versión soportada o reemplazo por contenedores (ya tienen GKE) |
| 5 | **Evaluar Siebel CX Cloud** | INI-16 (Fase 5) | TOGAF | Evaluación de migración de Siebel on-premise a Siebel CX Cloud (Oracle Cloud). Modernización del CRM sin cambio funcional |
| 6 | **Capa de parametrización de reglas (N-11)** | INI-17 | TOGAF | **Cambio organizacional clave**: Riesgo y Comercial ajustan reglas blandas (umbrales, segmentación, campañas) **sin pase a producción TI** → tiempo de cambio de semanas a **horas**. Reglas duras (CMF/SERNAC) fijas en código. Versionamiento, auditoría y rollback. Dashboard de reglas activas con impacto estimado |
| 7 | **Trazabilidad distribuida E2E + CMDB + Dashboards** | INI-11 | TOGAF | OpenTelemetry + Jaeger para tracing distribuido. CMDB con 100+ componentes documentados (de 62% sin info a 100%). Catálogo de servicios/API formalizado. 5 dashboards operativos. 134,446 errores genéricos desagregados por causa real. ID de correlación por solicitud |
| 8 | **SLAs con proveedores estratégicos** | INI-13 | TOGAF | SLAs formalizados con métricas, penalidades y escalamiento para 7 proveedores (FICO/Ventiv, Oracle, Sonda, Experian, Sinacofi, eSign, Oracle CCS). Soporte 24/7 fines de semana con FICO. Evaluación de relación directa con fabricante vs intermediario (Ventiv) |
| 9 | **Runbooks + transferencia conocimiento + DRP** | INI-14 | TOGAF | 6 runbooks (FICO, **Camel**, FlexCube, Kafka, Siebel, MenuAndes). Plan formación cruzada para 5 personas clave. DRP con flujo crédito: RTO ≤4h, RPO ≤1h. Gestión cambios ITIL. Simulacros trimestrales |
| 10 | **Registro formal de deuda técnica** | INI-16 | TOGAF | Gestión continua con priorización trimestral. Cada ítem: descripción, impacto, costo, owner, fecha target. Fin de acumulación invisible de 7 años |

### ¿Por qué TOGAF es necesario aquí?

Los problemas organizacionales evidenciados en el diagnóstico PwC son **causa raíz** de que las fallas técnicas se repitan durante 7 años sin resolución:

| Problema Organizacional | Evidencia | Qué resuelve TOGAF |
|------------------------|-----------|---------------------|
| Sin owner E2E desde nov 2024 | FG-18 | Modelo de gobierno con roles y autoridad definida |
| Madurez 1.21/5 | Evaluación TOGAF 44 preguntas | Framework completo para llevar a 3.0/5 |
| 62% componentes sin documentación | FG-28 | CMDB + catálogo de servicios obligatorio |
| 0/7 proveedores con SLA | FG-35-39 | Gestión de proveedores como dimensión TOGAF |
| 5 personas clave sin backup | FG-18 | Runbooks + DRP + transferencia como requisito |
| 7 años de patrones sin resolución | Diagnóstico PwC | Ciclo de mejora continua formalizado |
| Cambio de reglas toma semanas | FG-33 | Separación de capas: negocio parametriza, TI evoluciona |

## Consulta 8: Beneficios, Cambios y Estimaciones — To-Be 3

### (a) Beneficios
- **Cadena de obsolescencia rota**: Forms 10g → APEX, Oracle 12 → 19c, OSB 11g apagado (Camel), WebLogic evaluado
- **Negocio ajusta reglas sin TI**: Tiempo de cambio de **semanas → horas**
- **120 reglas fuera de campaña + 40 en campaña** separadas en blandas (parametrizables) y duras (fijas por regulación)
- **CMDB 100% operativa**: 100+ componentes documentados
- **Trazabilidad E2E completa**: OpenTelemetry + Jaeger + ID correlación
- **7 proveedores con SLA formalizado** (de 0 a 7)
- **DRP completado** con RTO ≤4h, RPO ≤1h para flujo de crédito
- **5 personas clave con backup** + 6 runbooks operativos
- **Camel como único bus**: OSB 11g descomisionado formalmente
- Evaluaciones perdidas/semana: **<50**
- MTTD: **≤1 min**
- Conversión E2E: **≥8%**
- Conversión TAPP_NOR: **≥7%**
- Derivaciones digitales: **≥60%**
- **Madurez TOGAF: 3.0/5** (de 1.21/5)
- Tiempo cambio reglas: **Horas** (de semanas)
- Ecosistema preparado para **escalabilidad horizontal y evolución multicloud**

### (b) Principales Cambios respecto al As-Is
| Aspecto | As-Is | To-Be 3 (TOGAF + Camel) |
|---------|-------|-------------------------|
| Marco de gobierno | Inexistente (TOGAF 1.21/5) | **TOGAF completo (3.0/5)** con ciclo de mejora continua |
| Bus de integración | OSB 11g | **OSB apagado formalmente. Camel como único bus** |
| MenuAndes | Forms 10g (sin soporte) | **Oracle APEX** + APIs REST |
| Oracle DB | 12c (sin soporte) | **19c/21c** con parches activos |
| WebLogic | 10.3.6 (sin soporte) | Evaluado para upgrade o reemplazo por contenedores |
| Siebel | On-premise | Evaluación de **Siebel CX Cloud** completada |
| Cambio de reglas | Pase a producción TI → semanas | **Parametrización autónoma por negocio → horas** |
| Proveedores | 0/7 con SLA | **7/7 con SLA**, métricas, penalidades, escalamiento |
| Documentación | 62% sin info técnica | **CMDB 100%** + catálogo servicios + diccionario datos |
| Personas | 5 personas sin backup, sin runbooks | **5 con backup + 6 runbooks + DRP + simulacros** |
| Trazabilidad | Sin correlación E2E | **OpenTelemetry + Jaeger + 5 dashboards + ID correlación** |
| Deuda técnica | 7 años sin registro | **Registro formal con priorización trimestral** |
| Escalabilidad | Vertical, limitada | **Horizontal, preparada para multicloud** |

### (c) Estimaciones de Tiempo y Costo
| Parámetro | Estimación |
|-----------|------------|
| **Plazo** | **>6 meses** (Meses 7-12+, sobre la base de To-Be 1 + To-Be 2) |
| **Iniciativas** | INI-11, INI-13, INI-14, INI-16 (5 fases), INI-17 |
| **Esfuerzo** | **Alto** para todas |
| **Naturaleza** | Modernización full-stack, aplicación de TOGAF como framework de gobierno, cambio organizacional (autonomía negocio sobre reglas), negociación contractual, migración de componentes legacy |
| **Costo licenciamiento por fase** | Fase 1 (Forms→APEX): **$0** (incluido en licencia Oracle DB). Fase 2 (Oracle 12→19c): **$** (licencia Oracle ya existe, costo de upgrade). Fase 3 (WebLogic): **$ a evaluar**. Fase 4 (Apagar OSB): **$0** (ya reemplazado por Camel). Fase 5 (Siebel CX Cloud): **$$** (suscripción OCI). INI-17 (Parametrización): **$0** (desarrollo interno o config vendor; posible módulo FICO adicional) |
| **Dependencias críticas** | INI-02 (v7, ya completado en To-Be 1) → INI-17. INI-07 (Camel, ya completado en To-Be 2) → INI-16 Fase 4. INI-12 (gobierno) → INI-13, INI-14, INI-16 |
| **Riesgos principales** | **INI-16**: Cadena de dependencias entre fases — si Fase 1 se atrasa, todo se atrasa. Migración Forms→APEX puede descubrir funcionalidades no documentadas. Oracle puede cambiar modelo licenciamiento. **INI-17**: Separar reglas blandas de duras no siempre tiene límite claro. Requiere participación activa vendor FICO |

---

# 📊 RESUMEN COMPARATIVO — 3 OPCIONES

| Métrica | As-Is | To-Be 1 (Opción 1) | To-Be 2 (Opción 2) | To-Be 3 (Opción 3) |
|---------|-------|---------------------|---------------------|---------------------|
| **Nombre** | Estado actual | Convivencia Unificada | Reemplazar Bus (Camel) | TOGAF Completo |
| **Foco** | — | Estabilizar sin cambiar piezas | Cambiar piezas clave | Cambio organizacional + modernización |
| **Horizonte** | — | ≤3 meses | 3-6 meses | >6 meses |
| **Bus integración** | OSB 11g | OSB 11g (se mantiene) | **Camel** (migración gradual) | **Camel** (OSB apagado) |
| **Marco gobierno** | Inexistente | Owner E2E + RACI | Owner consolidado | **TOGAF 3.0/5** |
| Eval. perdidas/sem | ~2,250 | <500 | <100 | <50 |
| MTTD | ~45 min | ≤5 min | ≤2 min | ≤1 min |
| Conversión E2E | 5.0% | 5.5% | ≥7% | ≥8% |
| Conversión TAPP_NOR | 3.6% | 4.0% | ≥6% | ≥7% |
| Derivaciones digital | 0% | 0% | ≥40% | ≥60% |
| Circuit breakers | 0 | 0 | **24** (Camel) | 24 |
| CMDB | 0 | 0 | 0 | **100+** |
| Proveedores con SLA | 0 | 0 | 0 | **7** |
| Madurez TOGAF | 1.21/5 | 1.8/5 | 2.5/5 | **3.0/5** |
| Cambio reglas | Semanas | Semanas | Días | **Horas** |
| Licenciamiento FICO | v4 + v7 | Solo v7 | Solo v7 | Solo v7 |
| MenuAndes | Forms 10g | Forms 10g | Forms 10g | **APEX** |
| Oracle DB | 12c | 12c | 12c | **19c/21c** |
| Costo licencia | — | $0 | $0 | $ a $$ por fase |
| # Iniciativas | — | 7 | 5 | 5 (multi-fase) |
