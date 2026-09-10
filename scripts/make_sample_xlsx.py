"""Genera un Excel de prueba con las columnas reales del sistema de tickets.

Uso:
    py scripts/make_sample_xlsx.py [salida.xlsx] [--rows N] [--start ID]

Genera N tickets (por defecto 8) con IDs consecutivos a partir de --start
(por defecto 1178650000). Cambia --start entre corridas para simular una
"segunda carga" con tickets nuevos y probar la asignación parcial.
"""

import argparse
import random

from openpyxl import Workbook

COLUMNS = [
    "Ticket ID", "Ticket Type", "Priority", "Status", "Queue Status",
    "Waiting Reason", "Subject", "Processor", "Processing Queue", "System Role",
    "Service Area", "Customer Name", "Reported At", "Metric", "Metric Due At",
    "Cycle Due At",
]

TICKET_TYPES = ["Customer Service Request", "Incident", "Change Request", "Problem"]
PRIORITIES = ["1 - Very High", "2 - High", "3 - Normal", "4 - Low"]
SYSTEM_ROLES = ["HEC_ABAP", "HEC_HANA", "HEC_JAVA", "HEC_OS"]
SERVICE_AREAS = ["Managed Cloud Delivery", "Technical Operations", "Database Ops"]
CUSTOMERS = ["DEUTZ Aktiengesellschaft", "Contoso AG", "Globex SE", "Initech GmbH"]
SUBJECTS = [
    "L2 - Level 2 DB Support for all Databases",
    "System not reachable after maintenance",
    "Request to increase memory allocation",
    "Backup job failed overnight",
    "Performance degradation on production",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", nargs="?", default="sample_tickets.xlsx")
    ap.add_argument("--rows", type=int, default=8)
    ap.add_argument("--start", type=int, default=1178650000)
    args = ap.parse_args()

    wb = Workbook()
    ws = wb.active
    ws.title = "Tickets"
    ws.append(COLUMNS)

    for i in range(args.rows):
        tid = args.start + i
        ws.append([
            str(tid),
            random.choice(TICKET_TYPES),
            random.choice(PRIORITIES),
            "Waiting",
            "Waiting",
            "Requester Action",
            random.choice(SUBJECTS),
            "Avi Sharan",
            "CT_RDY_07 September 2026",
            random.choice(SYSTEM_ROLES),
            random.choice(SERVICE_AREAS),
            random.choice(CUSTOMERS),
            "06.08 2026 04:35",
            "Action Plan Time",
            "06.09 2026 23:55",
            "07.09 2026 00:00",
        ])

    wb.save(args.output)
    print(f"Generado {args.output} con {args.rows} tickets (IDs {args.start}..{args.start + args.rows - 1})")


if __name__ == "__main__":
    main()
