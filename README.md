# Ticket Distribution

Aplicación web para distribuir tickets de soporte entre un equipo, a partir de un
Excel ya filtrado exportado del sistema de tickets (sin acceso directo a su API).

La UI está construida con **SAPUI5** (OpenUI5 desde CDN, tema Horizon) en un único
`index.html` — no requiere instalación ni build; se abre directamente en el navegador.

## Funcionalidades

- **Carga de Excel** filtrado; en cargas sucesivas de la misma sesión detecta solo
  los tickets nuevos (por `Ticket ID`) y genera **asignaciones parciales**.
- **Distribución automática** según un *skill matrix* (0–5 por colega) combinado con
  la carga del día de cada persona:
  - Score = habilidad (65%) + capacidad/carga disponible (35%).
  - Si nadie tiene el expertise suficiente, el ticket queda **sin asignar** y se
    proponen los candidatos más adecuados.
- **Gestión del equipo:** añadir/quitar colegas, marcar quién **no trabaja** ese día,
  y ajustar el **porcentaje de capacidad** individual del día.
- **Skill matrix** en 3 dimensiones extraídas de los tickets: Tipo de Ticket,
  System Role y Service Area.
- **Reasignación manual** de cualquier ticket.
- **Generación de correo** de asignación con plantilla y variables, seleccionando por
  carga (parcial) o por la sesión completa; abre Outlook vía `mailto:` o copia el cuerpo.
- Persistencia del equipo y la configuración de correo en `localStorage`.

## Uso

1. Abre `index.html` en el navegador (requiere conexión a internet la primera vez para
   cargar SAPUI5 y la librería de lectura de Excel desde CDN).
2. En **Equipo**, añade a tus colegas y ajusta capacidad / disponibilidad del día.
3. En **Skills**, valora 0–5 el conocimiento de cada colega por categoría.
4. En **Distribución**, carga el Excel; revisa y reasigna si hace falta.
5. En **Email**, genera y abre el correo de asignación.

## Columnas esperadas del Excel

`Ticket ID`, `Ticket Type`, `Priority`, `Status`, `Queue Status`, `Waiting Reason`,
`Subject`, `Processor`, `Processing Queue`, `System Role`, `Service Area`,
`Customer Name`, `Reported At`, `Metric`, `Metric Due At`, `Cycle Due At`.

## Roadmap

- Reestructuración a arquitectura de **microservicios** (backend FastAPI + API gateway
  + frontend UI5 con build + `docker-compose`).
