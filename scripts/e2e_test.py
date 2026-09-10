"""Prueba end-to-end del backend (se ejecuta dentro del contenedor).

Ejercita: login, crear sesión, alta de equipo, carga de Excel + asignación,
definición de skills, segunda carga (parcial), reasignación y preview de correo.
"""

import sys
import requests

BASE = "http://localhost:8000"


def main() -> None:
    s = requests.Session()

    # 1) Login
    r = s.post(f"{BASE}/auth/login", json={"email": "admin@empresa.com", "password": "change-me-admin"})
    r.raise_for_status()
    token = r.json()["access_token"]
    s.headers["Authorization"] = f"Bearer {token}"
    print("1) Login OK — usuario:", r.json()["user"]["username"])

    # 2) Crear sesión
    sid = s.post(f"{BASE}/sessions", json={}).json()["id"]
    print("2) Sesión creada id =", sid)

    # 3) Equipo
    ids = []
    for name in ["Ana García", "Luis Pérez", "María Ruiz"]:
        m = s.post(f"{BASE}/team", json={"name": name, "base_cap": 100}).json()
        ids.append(m["id"])
    print("3) Equipo:", ids)

    # 4) Primera carga
    with open("/tmp/sample1.xlsx", "rb") as f:
        r = s.post(f"{BASE}/sessions/{sid}/loads", files={"file": ("sample1.xlsx", f)})
    r.raise_for_status()
    b1 = r.json()
    print(f"4) Carga #{b1['batch_num']}: {b1['new_count']} nuevos, "
          f"asignados={sum(1 for a in b1['assignments'] if a['assignee_id'])}")

    # 5) Skills: dar expertise a los colegas en las categorías detectadas
    dims = s.get(f"{BASE}/skills/dimensions").json()
    for dim, cats in dims.items():
        for i, cat in enumerate(cats):
            # reparte niveles altos entre los colegas
            s.put(f"{BASE}/skills", json={
                "member_id": ids[i % len(ids)], "dimension": dim, "category": cat, "level": 5
            })
    print("5) Skills fijados para dimensiones:", {k: len(v) for k, v in dims.items()})

    # 6) Segunda carga (parcial — solo tickets nuevos)
    with open("/tmp/sample2.xlsx", "rb") as f:
        r = s.post(f"{BASE}/sessions/{sid}/loads", files={"file": ("sample2.xlsx", f)})
    r.raise_for_status()
    b2 = r.json()
    print(f"6) Carga #{b2['batch_num']}: {b2['new_count']} nuevos (parcial)")

    # Reintentar la MISMA carga → debe dar 409 (sin nuevos)
    with open("/tmp/sample2.xlsx", "rb") as f:
        r = s.post(f"{BASE}/sessions/{sid}/loads", files={"file": ("sample2.xlsx", f)})
    print(f"   Recarga del mismo archivo → HTTP {r.status_code} (se espera 409)")

    # 7) Total de asignaciones
    alla = s.get(f"{BASE}/sessions/{sid}/assignments").json()
    print(f"7) Total asignaciones en la sesión: {len(alla)}")

    # 8) Reasignar la primera
    first = alla[0]
    r = s.patch(f"{BASE}/assignments/{first['id']}", json={"assignee_member_id": ids[0]})
    r.raise_for_status()
    print(f"8) Reasignada {first['ticket']['ticket_id']} → {r.json()['assignee_name']}")

    # 9) Preview de correo (sesión completa)
    body = s.get(f"{BASE}/email/preview/{sid}?batch=all").json()["body"]
    print("9) Preview de correo (primeras líneas):")
    print("   " + "\n   ".join(body.splitlines()[:8]))

    print("\n✅ END-TO-END OK")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print("❌ HTTPError:", e, e.response.text if e.response else "")
        sys.exit(1)
