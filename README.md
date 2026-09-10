# Ticket Distribution

Aplicación web para distribuir tickets de soporte entre un equipo, a partir de un
Excel ya filtrado exportado del sistema de tickets (sin acceso directo a su API).

El estado es **compartido por todo el equipo** (base de datos central) y se
**sincroniza en vivo**: si alguien reasigna un ticket, actualiza skills o carga un
nuevo Excel, el cambio se refleja al instante para los demás vía WebSocket.

## Arquitectura

Monolito modular + base de datos, orquestado con **Podman** (o Docker):

```
┌─────────────┐  WebSocket /ws (push en vivo)  ┌──────────────────┐
│  UI5 (web)  │◄──────────────────────────────►│  FastAPI backend │──► PostgreSQL
│  :8080      │  REST (login, excel, CRUD)     │  :8000           │
└─────────────┘───────────────────────────────►└──────────────────┘
```

- **`1_backend/backend`** — un solo servicio FastAPI (auth JWT + argon2, SQLAlchemy
  async, PostgreSQL, WebSocket). Módulos internos: `api/` (routers), `services/`
  (lógica), `db/` (ORM).
- **`1_frontend/ui`** — app SAPUI5 en TypeScript (UI5 Tooling + `ui5-tooling-transpile`),
  servida por nginx.
- **`0_prototype/index.html`** — prototipo original monolítico (referencia de la lógica).

## Requisitos

- Podman (o Docker) con Compose. `podman compose version` debe funcionar.
- Para desarrollo del frontend sin contenedor: Node 20+.
- Para el script de datos de prueba: Python 3.12+ con `openpyxl` (`py -m pip install openpyxl`).

## Puesta en marcha (Podman)

```bash
cp .env.example .env          # edita secretos: JWT_SECRET_KEY, ADMIN_PASSWORD, POSTGRES_PASSWORD
podman compose up --build     # levanta postgres + backend + ui
```

- Frontend: http://localhost:8080
- API + Swagger: http://localhost:8000/docs
- Login inicial: `ADMIN_EMAIL` / `ADMIN_PASSWORD` del `.env` (por defecto
  `admin@empresa.com` / `change-me-admin`).

> El backend crea las tablas y siembra el usuario admin automáticamente al arrancar.

### Desarrollo del frontend por separado (hot reload)

```bash
cd 1_frontend/ui
npm install
npm start          # http://localhost:8080 con recarga en vivo
```

El backend puede correr en contenedor o local (`cd 1_backend/backend && py -m uvicorn main:app --reload`).
La URL del backend se define en un único lugar: `1_frontend/ui/webapp/util/Config.ts`.

## Flujo de uso

1. **Equipo** → añade colegas, marca quién trabaja hoy y ajusta su capacidad (%).
2. **Skills** → valora 0–5 el conocimiento de cada colega por categoría (las categorías
   aparecen tras cargar el primer Excel).
3. **Distribución** → carga el Excel; el sistema asigna los tickets nuevos. Cargas
   posteriores en la misma sesión solo procesan tickets nuevos (asignación parcial).
   Reasigna manualmente con el botón ✎.
4. **Email** → genera el cuerpo del correo (por carga o sesión completa) y ábrelo en
   Outlook.

### Motor de asignación

`score = habilidad·0.65 + carga_disponible·0.35`, donde la habilidad pondera
Tipo de Ticket (0.30), System Role (0.35) y Service Area (0.35). Si nadie tiene
expertise suficiente, el ticket queda sin asignar con los 3 candidatos más adecuados.

## Datos de prueba

```bash
py scripts/make_sample_xlsx.py sample1.xlsx --rows 8 --start 1178650000
py scripts/make_sample_xlsx.py sample2.xlsx --rows 5 --start 1178650100  # "segunda carga"
```

## Columnas esperadas del Excel

`Ticket ID`, `Ticket Type`, `Priority`, `Status`, `Queue Status`, `Waiting Reason`,
`Subject`, `Processor`, `Processing Queue`, `System Role`, `Service Area`,
`Customer Name`, `Reported At`, `Metric`, `Metric Due At`, `Cycle Due At`.

## Producción (futuro)

Correr el mismo `podman compose` en un host central y exponerlo con **Cloudflare
Tunnel** (descomenta el servicio `cloudflared` en `docker-compose.yml` y define
`CLOUDFLARE_TUNNEL_TOKEN`). Migrar la DB a un Postgres gestionado solo requiere
cambiar `DATABASE_URL`.
