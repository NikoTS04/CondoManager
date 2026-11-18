#!/usr/bin/env python3
"""Genera modelos BPMN 2.0 y sus PNG mediante bpmn-js y Chrome headless.

El modelado y la disposición se comparten entre los archivos editables y las
imágenes: las imágenes se renderizan directamente desde el XML BPMN generado.
Véanse los requisitos y comandos de reproducción en README.md.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

NAMESPACES = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "bioc": "http://bpmn.io/schema/bpmn/biocolor/1.0",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
for prefix, namespace in NAMESPACES.items():
    ET.register_namespace(prefix, namespace)


def element(parent, tag, **attributes):
    prefix, local = tag.split(":")
    return ET.SubElement(
        parent,
        f"{{{NAMESPACES[prefix]}}}{local}",
        {key: str(value) for key, value in attributes.items()},
    )


@dataclass
class Node:
    id: str
    kind: str
    name: str
    lane: int
    x: int
    y: int

    @property
    def size(self):
        if self.kind in ("startEvent", "endEvent"):
            return 38, 38
        if self.kind == "exclusiveGateway":
            return 54, 54
        return 190, 96

    @property
    def bounds(self):
        width, height = self.size
        return self.x - width // 2, self.y - height // 2, width, height

    def port(self, side):
        width, height = self.size
        return {
            "left": (self.x - width // 2, self.y),
            "right": (self.x + width // 2, self.y),
            "top": (self.x, self.y - height // 2),
            "bottom": (self.x, self.y + height // 2),
        }[side]


@dataclass
class Flow:
    source: str
    target: str
    name: str
    points: list[tuple[int, int]]
    label: tuple[int, int] | None


@dataclass
class Diagram:
    code: str
    filename: str
    title: str
    subtitle: str
    width: int
    lanes: list[tuple[str, int]]
    rules: list[str]
    source: str
    nodes: dict[str, Node] = field(default_factory=dict)
    flows: list[Flow] = field(default_factory=list)

    @property
    def height(self):
        return sum(height for _, height in self.lanes) + 48

    def n(self, id, kind, name, lane, x, y):
        if id in self.nodes:
            raise ValueError(f"Nodo duplicado: {id}")
        self.nodes[id] = Node(id, kind, name, lane, x, y)

    def f(self, source, target, name="", *, start="right", end="left", via=(), label=None):
        first = self.nodes[source].port(start)
        last = self.nodes[target].port(end)
        if via:
            points = [first, *via, last]
        elif first[0] == last[0] or first[1] == last[1]:
            points = [first, last]
        elif start in ("left", "right") and end in ("left", "right"):
            middle = (first[0] + last[0]) // 2
            points = [first, (middle, first[1]), (middle, last[1]), last]
        elif start in ("top", "bottom") and end in ("top", "bottom"):
            middle = (first[1] + last[1]) // 2
            points = [first, (first[0], middle), (last[0], middle), last]
        elif start in ("left", "right"):
            points = [first, (last[0], first[1]), last]
        else:
            points = [first, (first[0], last[1]), last]
        points = [point for index, point in enumerate(points) if not index or point != points[index - 1]]
        self.flows.append(Flow(source, target, name, points, label))

    def validate(self):
        incoming = {id: [] for id in self.nodes}
        outgoing = {id: [] for id in self.nodes}
        for flow in self.flows:
            incoming[flow.target].append(flow)
            outgoing[flow.source].append(flow)
            for (x1, y1), (x2, y2) in zip(flow.points, flow.points[1:]):
                if x1 != x2 and y1 != y2:
                    raise ValueError(f"Flujo no ortogonal: {flow.source} → {flow.target}")
                for node in self.nodes.values():
                    if node.id in (flow.source, flow.target):
                        continue
                    left, top, width, height = node.bounds
                    right, bottom = left + width, top + height
                    crosses = (
                        y1 == y2 and top < y1 < bottom
                        and max(x1, x2) > left and min(x1, x2) < right
                    ) or (
                        x1 == x2 and left < x1 < right
                        and max(y1, y2) > top and min(y1, y2) < bottom
                    )
                    if crosses:
                        raise ValueError(
                            f"{self.code}: {flow.source} → {flow.target} atraviesa {node.id}"
                        )
        for id, node in self.nodes.items():
            top = 24 + sum(height for _, height in self.lanes[:node.lane])
            bottom = top + self.lanes[node.lane][1]
            left, node_top, width, height = node.bounds
            if not (95 < left and left + width < self.width - 24):
                raise ValueError(f"Nodo fuera del pool: {id}")
            if not (top <= node_top and node_top + height <= bottom):
                raise ValueError(f"Nodo fuera de su carril: {id}")
            if node.kind == "startEvent":
                assert not incoming[id] and outgoing[id], id
            elif node.kind == "endEvent":
                assert incoming[id] and not outgoing[id], id
            else:
                assert incoming[id] and outgoing[id], id
            if node.kind == "exclusiveGateway" and len(outgoing[id]) > 1:
                assert all(flow.name for flow in outgoing[id]), id
        for reverse in (False, True):
            reached = {
                id for id, node in self.nodes.items()
                if node.kind == ("endEvent" if reverse else "startEvent")
            }
            pending = list(reached)
            while pending:
                id = pending.pop()
                for flow in incoming[id] if reverse else outgoing[id]:
                    next_id = flow.source if reverse else flow.target
                    if next_id not in reached:
                        reached.add(next_id)
                        pending.append(next_id)
            if reached != set(self.nodes):
                raise ValueError(f"Nodos sin recorrido completo: {set(self.nodes) - reached}")

    def xml(self):
        self.validate()
        prefix = self.code.replace("-", "_")

        def ref(id):
            return f"{prefix}_{id}"

        root = ET.Element(
            f"{{{NAMESPACES['bpmn']}}}definitions",
            id=ref("Definitions"),
            targetNamespace="https://condomanager.local/bpmn/jerson",
            exporter="CondoManager — diagramas de Jerson",
            exporterVersion="1.0",
        )
        process = element(root, "bpmn:process", id=ref("Process"), name=self.title,
                          isExecutable="false")
        element(process, "bpmn:documentation").text = (
            f"Responsable de la historia: Jerson. {self.subtitle}\n"
            + "\n".join(self.rules) + f"\nFuente: {self.source}"
        )
        lane_set = element(process, "bpmn:laneSet", id=ref("LaneSet"))
        for index, (name, _) in enumerate(self.lanes):
            lane = element(lane_set, "bpmn:lane", id=ref(f"Lane_{index}"), name=name)
            for node in self.nodes.values():
                if node.lane == index:
                    element(lane, "bpmn:flowNodeRef").text = ref(node.id)
        for node in self.nodes.values():
            attributes = {"id": ref(node.id), "name": node.name}
            outgoing = [flow for flow in self.flows if flow.source == node.id]
            if node.kind == "exclusiveGateway":
                incoming = [flow for flow in self.flows if flow.target == node.id]
                attributes["gatewayDirection"] = (
                    "Mixed" if len(incoming) > 1 and len(outgoing) > 1
                    else "Diverging" if len(outgoing) > 1 else "Converging"
                )
            xml_node = element(process, f"bpmn:{node.kind}", **attributes)
            for index, flow in enumerate(self.flows):
                if flow.target == node.id:
                    element(xml_node, "bpmn:incoming").text = ref(f"Flow_{index}")
            for index, flow in enumerate(self.flows):
                if flow.source == node.id:
                    element(xml_node, "bpmn:outgoing").text = ref(f"Flow_{index}")
        for index, flow in enumerate(self.flows):
            attributes = {"id": ref(f"Flow_{index}"), "sourceRef": ref(flow.source),
                          "targetRef": ref(flow.target)}
            if flow.name:
                attributes["name"] = flow.name
            xml_flow = element(process, "bpmn:sequenceFlow", **attributes)
            source = self.nodes[flow.source]
            if source.kind == "exclusiveGateway" and flow.name:
                condition = element(xml_flow, "bpmn:conditionExpression", language="text/plain")
                condition.set(f"{{{NAMESPACES['xsi']}}}type", "bpmn:tFormalExpression")
                condition.text = flow.name
        collaboration = element(root, "bpmn:collaboration", id=ref("Collaboration"))
        element(collaboration, "bpmn:participant", id=ref("Participant"),
                name=f"CondoManager · {self.code}", processRef=ref("Process"))
        diagram = element(root, "bpmndi:BPMNDiagram", id=ref("Diagram"), name=self.title)
        plane = element(diagram, "bpmndi:BPMNPlane", id=ref("Plane"),
                        bpmnElement=ref("Collaboration"))

        def shape(id, bounds, fill, stroke, horizontal=False):
            attributes = {"id": ref(f"{id}_di"), "bpmnElement": ref(id)}
            if horizontal:
                attributes["isHorizontal"] = "true"
            if id in self.nodes and self.nodes[id].kind == "exclusiveGateway":
                attributes["isMarkerVisible"] = "true"
            result = element(plane, "bpmndi:BPMNShape", **attributes)
            result.set(f"{{{NAMESPACES['bioc']}}}fill", fill)
            result.set(f"{{{NAMESPACES['bioc']}}}stroke", stroke)
            x, y, width, height = bounds
            element(result, "dc:Bounds", x=x, y=y, width=width, height=height)
            return result

        shape("Participant", (24, 24, self.width - 48, self.height - 48),
              "#ffffff", "#66788c", True)
        top = 24
        for index, (_, height) in enumerate(self.lanes):
            shape(f"Lane_{index}", (54, top, self.width - 78, height),
                  "#ffffff" if index % 2 == 0 else "#f7faff", "#a2b2c4", True)
            top += height
        colors = {
            "startEvent": ("#e9f8ee", "#24824b"),
            "endEvent": ("#fff0ed", "#ad443a"),
            "exclusiveGateway": ("#fff2ce", "#956600"),
            "userTask": ("#fff5db", "#8a681d"),
            "serviceTask": ("#eaf3ff", "#296293"),
        }
        for node in self.nodes.values():
            xml_shape = shape(node.id, node.bounds, *colors[node.kind])
            if node.kind in ("startEvent", "endEvent", "exclusiveGateway"):
                label = element(xml_shape, "bpmndi:BPMNLabel")
                label_y = node.y - 88 if node.kind == "exclusiveGateway" else node.y + 28
                element(label, "dc:Bounds", x=node.x - 76, y=label_y, width=152, height=52)
        for index, flow in enumerate(self.flows):
            edge = element(plane, "bpmndi:BPMNEdge", id=ref(f"Flow_{index}_di"),
                           bpmnElement=ref(f"Flow_{index}"))
            edge.set(f"{{{NAMESPACES['bioc']}}}stroke", "#475b70")
            for x, y in flow.points:
                element(edge, "di:waypoint", x=x, y=y)
            if flow.name:
                label = element(edge, "bpmndi:BPMNLabel")
                if flow.label:
                    center_x, y = flow.label
                    x = center_x - 60
                else:
                    x = (flow.points[0][0] + flow.points[1][0]) // 2 - 60
                    y = (flow.points[0][1] + flow.points[1][1]) // 2 - 30
                element(label, "dc:Bounds", x=x, y=y, width=120, height=40)
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def estructura():
    d = Diagram(
        "CON-3", "CON-3-edificios-departamentos",
        "Registrar edificios y departamentos",
        "PROC-05 · Sprint 1 · Registro manual e importación CSV con resultados por fila",
        2920, [("Administración", 360), ("Sistema CondoManager", 610)],
        [
            "Escritura: SuperAdmin o Junta del condominio. Edificio y número normalizado identifican una unidad; se utiliza UUID para operar.",
            "CSV: previsualizar no guarda datos. Confirmar revalida, crea filas válidas y reporta errores; los reintentos idénticos no duplican unidades.",
            "Coeficientes con Decimal y cuatro decimales. Persistencia y auditoría atómicas; un fallo inesperado revierte toda la solicitud.",
        ],
        "specs/02-domains/05-usuarios-rbac/estructura-inmobiliaria.md",
    )
    for args in [
        ("inicio", "startEvent", "Necesidad de registro", 0, 160, 150),
        ("solicitud", "userTask", "Seleccionar condominio y solicitar registro", 0, 350, 150),
        ("autorizar", "serviceTask", "Validar identidad, permisos y condominio activo", 1, 570, 490),
        ("permiso", "exclusiveGateway", "¿Acceso autorizado?", 1, 780, 490),
        ("rechazar", "serviceTask", "Rechazar solicitud y mostrar motivo", 1, 780, 760),
        ("sin_permiso", "endEvent", "Solicitud rechazada", 1, 980, 760),
        ("modalidad", "exclusiveGateway", "¿Modalidad de registro?", 0, 920, 250),
        ("manual", "userTask", "Ingresar edificio o departamento", 0, 1140, 150),
        ("validar", "serviceTask", "Validar datos, piso, coeficiente y duplicados", 1, 1390, 490),
        ("valido", "exclusiveGateway", "¿Datos válidos y únicos?", 1, 1620, 490),
        ("corregir", "userTask", "Corregir datos informados", 0, 1620, 150),
        ("guardar", "serviceTask", "Guardar registro y auditoría en una transacción", 1, 1850, 490),
        ("fin_manual", "endEvent", "Estructura registrada", 1, 2070, 490),
        ("csv", "userTask", "Seleccionar y cargar archivo CSV", 0, 1140, 320),
        ("previsualizar", "serviceTask", "Validar CSV y previsualizar resultados sin guardar", 1, 1390, 760),
        ("revisar", "userTask", "Revisar vista previa y errores por fila", 0, 2180, 320),
        ("confirmar", "exclusiveGateway", "¿Confirmar importación?", 0, 2400, 320),
        ("cancelar", "endEvent", "Importación cancelada", 0, 2630, 320),
        ("importar", "serviceTask", "Revalidar y guardar filas válidas con auditoría", 1, 2400, 760),
        ("reporte", "serviceTask", "Mostrar filas creadas, existentes y con error", 1, 2640, 760),
        ("fin_csv", "endEvent", "Importación procesada", 1, 2840, 760),
    ]:
        d.n(*args)
    d.f("inicio", "solicitud")
    d.f("solicitud", "autorizar", start="bottom", end="top")
    d.f("autorizar", "permiso")
    d.f("permiso", "rechazar", "No", start="bottom", end="top", label=(820, 610))
    d.f("rechazar", "sin_permiso")
    d.f("permiso", "modalidad", "Sí", start="top", end="left",
        via=((780, 250),), label=(820, 340))
    d.f("modalidad", "manual", "Manual", start="top", label=(990, 116))
    d.f("modalidad", "csv", "CSV", start="bottom", label=(990, 290))
    d.f("manual", "validar", end="top")
    d.f("validar", "valido")
    d.f("valido", "corregir", "No", start="top", end="bottom", label=(1660, 300))
    d.f("corregir", "manual", start="top", end="top", via=((1620, 70), (1140, 70)))
    d.f("valido", "guardar", "Sí", label=(1715, 456))
    d.f("guardar", "fin_manual")
    d.f("csv", "previsualizar", start="bottom", via=((1140, 760),))
    d.f("previsualizar", "revisar", end="bottom",
        via=((1510, 760), (1510, 910), (2180, 910)))
    d.f("revisar", "confirmar")
    d.f("confirmar", "cancelar", "No", label=(2480, 286))
    d.f("confirmar", "importar", "Sí", start="bottom", end="top", label=(2440, 520))
    d.f("importar", "reporte")
    d.f("reporte", "fin_csv")
    return d


def usuarios():
    d = Diagram(
        "CON-04", "CON-04-alta-habilitacion-usuarios", "Crear usuarios y habilitar su acceso",
        "PROC-05 · Sprint 2 · Alta administrativa, activación y autenticación persistente",
        2920, [("Administración", 200), ("Sistema CondoManager", 430),
               ("SuperAdmin", 180), ("Usuario", 200)],
        [
            "Alta: correo y documento únicos; contraseña inicial almacenada con hash. La cuenta nace INACTIVA con rol contextual RESIDENTE y sin vínculos.",
            "Solo SuperAdmin habilita o deshabilita la identidad. Cada cambio real de estado audita e invalida sesiones; reactivar exige nuevo login.",
            "Login verifica credenciales, cuenta activa y asignaciones vigentes. Si hay varios condominios, el usuario selecciona contexto antes de recibir el JWT.",
        ],
        "specs/02-domains/05-usuarios-rbac/alta-administrativa.md",
    )
    for args in [
        ("inicio", "startEvent", "Solicitud de alta", 0, 160, 125),
        ("formulario", "userTask", "Ingresar identidad y contraseña inicial", 0, 350, 125),
        ("validar", "serviceTask", "Validar actor, contexto, datos y unicidad", 1, 570, 330),
        ("valido", "exclusiveGateway", "¿Alta válida y autorizada?", 1, 790, 330),
        ("rechazar", "serviceTask", "Informar permiso insuficiente o datos inválidos", 1, 790, 550),
        ("sin_alta", "endEvent", "Alta no realizada", 1, 1010, 550),
        ("crear", "serviceTask", "Crear cuenta INACTIVA, hash, rol RESIDENTE y auditoría", 1, 1030, 330),
        ("revisar", "userTask", "Revisar cuenta y decidir su habilitación", 2, 1260, 745),
        ("habilitar", "exclusiveGateway", "¿Habilitar acceso?", 2, 1480, 745),
        ("inactiva", "endEvent", "Cuenta permanece inactiva", 2, 1690, 745),
        ("activar", "serviceTask", "Activar cuenta; guardar revisión y auditoría atómicas", 1, 1720, 330),
        ("login", "userTask", "Ingresar correo y contraseña para iniciar sesión", 3, 1950, 925),
        ("credenciales", "serviceTask", "Verificar credenciales, cuenta activa y roles vigentes", 1, 2170, 330),
        ("acceso", "exclusiveGateway", "¿Autenticación válida?", 1, 2390, 330),
        ("denegar", "serviceTask", "Denegar acceso con error de autenticación", 1, 2390, 550),
        ("sin_acceso", "endEvent", "Login rechazado", 1, 2610, 550),
        ("sesion", "serviceTask", "Resolver contexto y emitir JWT con perfil vigente", 1, 2640, 330),
        ("fin", "endEvent", "Acceso habilitado", 3, 2820, 925),
    ]:
        d.n(*args)
    d.f("inicio", "formulario")
    d.f("formulario", "validar", start="bottom", end="top")
    d.f("validar", "valido")
    d.f("valido", "rechazar", "No", start="bottom", end="top", label=(830, 425))
    d.f("rechazar", "sin_alta")
    d.f("valido", "crear", "Sí", label=(875, 296))
    d.f("crear", "revisar", start="bottom", end="top",
        via=((1030, 460), (1140, 460), (1140, 650), (1260, 650)))
    d.f("revisar", "habilitar")
    d.f("habilitar", "inactiva", "No", label=(1545, 710))
    d.f("habilitar", "activar", "Sí", start="top", end="left",
        via=((1480, 330),), label=(1520, 500))
    d.f("activar", "login", start="bottom", end="top",
        via=((1835, 378), (1835, 850), (1950, 850)))
    d.f("login", "credenciales", end="bottom", via=((2080, 925), (2080, 420), (2170, 420)))
    d.f("credenciales", "acceso")
    d.f("acceso", "denegar", "No", start="bottom", end="top", label=(2430, 425))
    d.f("denegar", "sin_acceso")
    d.f("acceso", "sesion", "Sí", label=(2475, 296))
    d.f("sesion", "fin", start="right", end="top", via=((2820, 330),))
    return d


def vinculos():
    d = Diagram(
        "CON-05", "CON-05-vinculos-usuarios-departamentos", "Vincular usuarios con departamentos",
        "PROC-05 · Sprint 2 · Alta, cambio, restauración y revocación de vínculos de tenencia",
        2840, [("Administración", 250), ("Sistema CondoManager", 640)],
        [
            "Relaciones: PROPIETARIO_TITULAR, COPROPIETARIO e INQUILINO. El primer vínculo activo debe ser titular; el último titular requiere reemplazo previo.",
            "Crear, cambiar o restaurar requiere rol vigente; altas y restauraciones requieren unidad activa. Revocar sigue permitido aunque el rol esté revocado.",
            "Cambio real: vínculo, revisión global y auditoría atómicos; tokens previos revocados. Repetir la misma operación conserva fila, revisión e historial.",
        ],
        "specs/02-domains/05-usuarios-rbac/vinculos-departamentos.md",
    )
    for args in [
        ("inicio", "startEvent", "Gestionar vínculo", 0, 160, 145),
        ("seleccionar", "userTask", "Seleccionar usuario, condominio y departamento", 0, 360, 145),
        ("solicitar", "userTask", "Elegir operación y relación de tenencia", 0, 590, 145),
        ("validar", "serviceTask", "Validar actor, contexto, usuario y departamento", 1, 820, 410),
        ("autorizado", "exclusiveGateway", "¿Solicitud autorizada y recursos existentes?", 1, 1040, 410),
        ("operacion", "exclusiveGateway", "¿Operación solicitada?", 1, 1260, 410),
        ("reglas_alta", "serviceTask", "Validar rol, actividad de unidad y reglas de titulares", 1, 1500, 410),
        ("reglas_baja", "serviceTask", "Comprobar vínculo y protección del último titular", 1, 1500, 620),
        ("reglas", "exclusiveGateway", "¿Cumple reglas de la operación?", 1, 1750, 410),
        ("cambio", "exclusiveGateway", "¿Existe cambio real?", 1, 1980, 410),
        ("guardar", "serviceTask", "Guardar vínculo, revisión y auditoría de forma atómica", 1, 2220, 410),
        ("sin_cambio", "serviceTask", "Devolver vínculo actual sin duplicar cambios", 1, 2220, 620),
        ("resultado", "userTask", "Revisar relación y estado del vínculo", 0, 2470, 145),
        ("fin", "endEvent", "Vínculo gestionado", 0, 2710, 145),
        ("error", "exclusiveGateway", "", 1, 1900, 780),
        ("rechazar", "serviceTask", "Informar motivo y conservar el vínculo anterior", 1, 2140, 780),
        ("rechazado", "endEvent", "Solicitud rechazada", 1, 2390, 780),
    ]:
        d.n(*args)
    d.f("inicio", "seleccionar")
    d.f("seleccionar", "solicitar")
    d.f("solicitar", "validar", start="bottom", end="top")
    d.f("validar", "autorizado")
    d.f("autorizado", "operacion", "Sí", label=(1110, 376))
    d.f("autorizado", "error", "No", start="bottom", end="left",
        via=((1040, 780),), label=(1080, 590))
    d.f("operacion", "reglas_alta", "Crear / cambiar / restaurar", label=(1350, 460))
    d.f("operacion", "reglas_baja", "Revocar", start="bottom",
        via=((1260, 620),), label=(1320, 520))
    d.f("reglas_alta", "reglas")
    d.f("reglas_baja", "reglas", end="bottom", via=((1750, 620),))
    d.f("reglas", "error", "No", start="bottom", end="top",
        via=((1820, 437), (1820, 720), (1900, 720)), label=(1860, 580))
    d.f("reglas", "cambio", "Sí", label=(1825, 376))
    d.f("cambio", "guardar", "Sí", label=(2050, 376))
    d.f("cambio", "sin_cambio", "No", start="bottom", label=(2020, 520))
    d.f("guardar", "resultado", start="top", via=((2220, 145),))
    d.f("sin_cambio", "resultado", end="bottom", via=((2470, 620),))
    d.f("resultado", "fin")
    d.f("error", "rechazar")
    d.f("rechazar", "rechazado")
    return d


def roles():
    d = Diagram(
        "CON-06", "CON-06-roles-permisos", "Administrar roles y permisos",
        "PROC-05 · Sprint 2 · Asignación, cambio, reactivación y revocación de roles contextuales",
        2940, [("Administración autorizada", 250), ("Sistema CondoManager", 580)],
        [
            "SuperAdmin gestiona ADMIN_JUNTA, AUDITOR y RESIDENTE. Junta solo gestiona Auditor/Residente de su condominio, también respecto del rol previo.",
            "Se rechaza modificar la propia asignación o una identidad SuperAdmin global. La concesión global de SuperAdmin se provisiona por CLI.",
            "Rol, revisión global y auditoría confirman juntos. El cambio revoca tokens anteriores; el nuevo login usa el rol vigente y conserva vínculos e historial.",
        ],
        "specs/02-domains/05-usuarios-rbac/roles-y-permisos.md",
    )
    for args in [
        ("inicio", "startEvent", "Gestionar permisos", 0, 160, 145),
        ("seleccionar", "userTask", "Seleccionar condominio y usuario destino", 0, 360, 145),
        ("solicitar", "userTask", "Elegir operación y rol contextual", 0, 590, 145),
        ("validar", "serviceTask", "Validar autoridad, usuario, contexto, rol y operación", 1, 820, 420),
        ("autorizado", "exclusiveGateway", "¿Solicitud permitida y válida?", 1, 1040, 420),
        ("rechazar", "serviceTask", "Rechazar e informar motivo sin modificar permisos", 1, 1040, 710),
        ("rechazado", "endEvent", "Solicitud rechazada", 1, 1270, 710),
        ("operacion", "exclusiveGateway", "¿Operación solicitada?", 1, 1280, 420),
        ("preparar", "serviceTask", "Preparar alta, cambio o reactivación de asignación", 1, 1520, 420),
        ("revocar", "serviceTask", "Preparar revocación lógica sin eliminar la asignación", 1, 1520, 640),
        ("unir", "exclusiveGateway", "", 1, 1770, 420),
        ("cambio", "exclusiveGateway", "¿Existe cambio real?", 1, 1990, 420),
        ("guardar", "serviceTask", "Guardar rol, revisión global y auditoría atómicos", 1, 2230, 420),
        ("sin_cambio", "serviceTask", "Devolver asignación vigente sin duplicar cambios", 1, 2230, 640),
        ("resultado", "userTask", "Revisar rol y estado de la asignación", 0, 2490, 145),
        ("fin", "endEvent", "Permisos gestionados", 0, 2760, 145),
    ]:
        d.n(*args)
    d.f("inicio", "seleccionar")
    d.f("seleccionar", "solicitar")
    d.f("solicitar", "validar", start="bottom", end="top")
    d.f("validar", "autorizado")
    d.f("autorizado", "rechazar", "No", start="bottom", end="top", label=(1080, 560))
    d.f("rechazar", "rechazado")
    d.f("autorizado", "operacion", "Sí", label=(1120, 386))
    d.f("operacion", "preparar", "Asignar / cambiar / restaurar", label=(1370, 470))
    d.f("operacion", "revocar", "Revocar", start="bottom",
        via=((1280, 640),), label=(1340, 540))
    d.f("preparar", "unir")
    d.f("revocar", "unir", end="bottom", via=((1770, 640),))
    d.f("unir", "cambio")
    d.f("cambio", "guardar", "Sí", label=(2070, 386))
    d.f("cambio", "sin_cambio", "No", start="bottom", label=(2030, 540))
    d.f("guardar", "resultado", start="top", via=((2230, 145),))
    d.f("sin_cambio", "resultado", end="bottom", via=((2490, 640),))
    d.f("resultado", "fin")
    return d


def areas():
    d = Diagram(
        "CON-39", "CON-39-catalogo-areas-comunes", "Administrar el catálogo de áreas comunes",
        "PROC-04 · Sprint 2 · Mantenimiento administrativo y consulta del catálogo por residentes",
        2920, [("Administración", 270), ("Sistema CondoManager", 600), ("Residente", 210)],
        [
            "Crear o modificar: nombre, descripción, aforo, horarios, costo decimal no negativo y estado; validar pertenencia al condominio autorizado.",
            "Desactivar impide nuevas reservas y conserva reservas previas e historial. Persistencia y auditoría confirman juntas; un fallo revierte la operación.",
            "La consulta se inicia de forma independiente: valida sesión y contexto y muestra las áreas activas con sus reglas de uso y reserva.",
        ],
        "docs/sprints/SPRINT-2.md#con-39--administrar-el-catálogo-de-áreas-comunes",
    )
    for args in [
        ("inicio", "startEvent", "Gestionar catálogo", 0, 160, 145),
        ("solicitar", "userTask", "Seleccionar condominio y solicitar mantenimiento", 0, 360, 145),
        ("autorizar", "serviceTask", "Validar sesión, rol administrativo y contexto", 1, 590, 430),
        ("permiso", "exclusiveGateway", "¿Acceso autorizado?", 1, 810, 430),
        ("denegar", "serviceTask", "Rechazar por falta de autorización", 1, 1030, 820),
        ("denegado", "endEvent", "Acceso denegado", 1, 1260, 820),
        ("operacion", "exclusiveGateway", "¿Operación solicitada?", 0, 1030, 145),
        ("formulario", "userTask", "Ingresar o corregir datos y reglas del área", 0, 1260, 125),
        ("validar", "serviceTask", "Validar aforo, horarios, costo y pertenencia del área", 1, 1490, 430),
        ("valido", "exclusiveGateway", "¿Datos válidos?", 1, 1720, 430),
        ("corregir", "userTask", "Revisar errores informados", 0, 1720, 125),
        ("guardar", "serviceTask", "Guardar área y auditoría en una transacción", 1, 1960, 430),
        ("seleccionar", "userTask", "Seleccionar área a desactivar", 0, 1260, 240),
        ("comprobar", "serviceTask", "Verificar existencia y pertenencia del área", 1, 1490, 660),
        ("existe", "exclusiveGateway", "¿Área del contexto existente?", 1, 1720, 660),
        ("error", "serviceTask", "Informar recurso inexistente sin modificar el catálogo", 1, 1720, 820),
        ("sin_cambio", "endEvent", "Catálogo sin cambios", 1, 1950, 820),
        ("desactivar", "serviceTask", "Desactivar área y auditar conservando el historial", 1, 1960, 660),
        ("unir", "exclusiveGateway", "", 1, 2200, 430),
        ("resultado", "userTask", "Revisar configuración y estado del área", 0, 2440, 145),
        ("fin", "endEvent", "Catálogo actualizado", 0, 2710, 145),
        ("consulta", "startEvent", "Consultar áreas", 2, 160, 995),
        ("abrir", "userTask", "Abrir catálogo de áreas comunes", 2, 360, 995),
        ("consultar", "serviceTask", "Validar sesión y consultar áreas activas del contexto", 1, 590, 660),
        ("mostrar", "userTask", "Consultar aforo, horarios, costo y reglas de uso", 2, 880, 995),
        ("consultado", "endEvent", "Catálogo consultado", 2, 1130, 995),
    ]:
        d.n(*args)
    d.f("inicio", "solicitar")
    d.f("solicitar", "autorizar", start="bottom", end="top")
    d.f("autorizar", "permiso")
    d.f("permiso", "denegar", "No", start="bottom", end="left",
        via=((810, 820),), label=(850, 730))
    d.f("denegar", "denegado")
    d.f("permiso", "operacion", "Sí", start="top", end="left",
        via=((810, 145),), label=(850, 260))
    d.f("operacion", "formulario", "Crear / modificar", label=(1110, 146))
    d.f("formulario", "validar", end="top")
    d.f("validar", "valido")
    d.f("valido", "corregir", "No", start="top", end="bottom", label=(1760, 270))
    d.f("corregir", "formulario", start="top", end="top",
        via=((1720, 55), (1260, 55)))
    d.f("valido", "guardar", "Sí", label=(1800, 396))
    d.f("guardar", "unir")
    d.f("operacion", "seleccionar", "Desactivar", start="bottom",
        via=((1030, 240),), label=(1105, 207))
    d.f("seleccionar", "comprobar", start="bottom", end="left",
        via=((1260, 660),))
    d.f("comprobar", "existe")
    d.f("existe", "error", "No", start="bottom", end="top", label=(1760, 732))
    d.f("error", "sin_cambio")
    d.f("existe", "desactivar", "Sí", label=(1800, 626))
    d.f("desactivar", "unir", end="bottom", via=((2200, 660),))
    d.f("unir", "resultado", start="top", via=((2200, 145),))
    d.f("resultado", "fin")
    d.f("consulta", "abrir")
    d.f("abrir", "consultar", start="top", end="bottom")
    d.f("consultar", "mostrar", start="right", end="left", via=((710, 660), (710, 995)))
    d.f("mostrar", "consultado")
    return d


def page(diagram, xml, viewer):
    rules = "".join(f"<li>{html.escape(rule)}</li>" for rule in diagram.rules)
    xml_json = json.dumps(xml, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{diagram.code}</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: white; color: #162d45;
  font-family: Arial, sans-serif; width: {diagram.width}px; }}
header {{ height: 122px; padding: 22px 34px; background: #142b43; color: white;
  border-bottom: 5px solid #31b5b1; }}
.kicker {{ color: #9bdedc; font-size: 13px; letter-spacing: 2px; font-weight: bold; }}
h1 {{ margin: 9px 0 7px; font-size: 30px; font-weight: 600; }}
.subtitle {{ font-size: 15px; color: #d0dce8; }}
.badge {{ float: right; border: 1px solid #668399; padding: 10px 16px;
  border-radius: 5px; color: #d9f4f3; font-size: 15px; margin-top: 8px; }}
#canvas {{ width: {diagram.width}px; height: {diagram.height}px; }}
.djs-container svg {{ background: white; }}
.bjs-powered-by {{ opacity: .65; }}
footer {{ height: 166px; padding: 14px 34px 10px; border-top: 1px solid #d2deea;
  background: #f3f7fb; }}
.legend {{ display: flex; gap: 30px; align-items: center; font-size: 14px; }}
.key {{ display: flex; align-items: center; gap: 9px; }}
.symbol {{ display: inline-block; width: 16px; height: 16px; border: 1.5px solid; }}
.start {{ border-color: #24824b; background: #e9f8ee; border-radius: 50%; }}
.end {{ border: 3px solid #ad443a; background: #fff0ed; border-radius: 50%; }}
.user {{ width: 23px; border-radius: 4px; background: #fff5db; border-color: #8a681d; }}
.service {{ width: 23px; border-radius: 4px; background: #eaf3ff; border-color: #296293; }}
.gateway {{ transform: rotate(45deg); background: #fff2ce; border-color: #956600; }}
ul {{ margin: 12px 0 8px; padding-left: 17px; font-size: 14px; line-height: 1.55; }}
.source {{ font-size: 12px; color: #526c83; }}
#error {{ color: #a00000; font-size: 24px; padding: 30px; }}
</style></head><body>
<header><span class="badge">BPMN 2.0 · Responsable: Jerson</span>
<div class="kicker">CONDOMANAGER / PROCESOS DE NEGOCIO</div>
<h1>{diagram.code} — {html.escape(diagram.title)}</h1>
<div class="subtitle">{html.escape(diagram.subtitle)}</div></header>
<main id="canvas"></main>
<footer><div class="legend">
<span class="key"><i class="symbol start"></i>Inicio</span>
<span class="key"><i class="symbol user"></i>Tarea de usuario</span>
<span class="key"><i class="symbol service"></i>Tarea de servicio</span>
<span class="key"><i class="symbol gateway"></i>Decisión exclusiva (X)</span>
<span class="key">→ Flujo de secuencia</span>
<span class="key"><i class="symbol end"></i>Fin</span></div>
<ul>{rules}</ul><div class="source">Fuente: {html.escape(diagram.source)}</div></footer>
<script src="{html.escape(viewer.as_uri(), quote=True)}"></script>
<script>
const viewer = new BpmnJS({{
  container: '#canvas',
  textRenderer: {{ defaultStyle: {{ fontFamily: 'Arial, sans-serif', fontSize: 16 }},
                  externalStyle: {{ fontFamily: 'Arial, sans-serif', fontSize: 15 }} }}
}});
(async () => {{
  try {{
    const result = await viewer.importXML({xml_json});
    viewer.get('canvas').viewbox({{ x: 0, y: 0, width: {diagram.width}, height: {diagram.height} }});
    await document.fonts.ready;
    document.body.dataset.bpmnStatus = 'ok';
    document.body.dataset.bpmnWarnings = String(result.warnings.length);
  }} catch (error) {{
    document.body.dataset.bpmnStatus = 'error';
    document.querySelector('#canvas').innerHTML = '<div id="error"></div>';
    document.querySelector('#error').textContent = String(error);
  }}
}})();
</script></body></html>"""


def render(diagram, xml, viewer, chrome, output):
    with tempfile.TemporaryDirectory(prefix="condomanager-bpmn-") as directory:
        temporary = Path(directory)
        document = temporary / "diagram.html"
        document.write_text(page(diagram, xml, viewer), encoding="utf-8")
        result = subprocess.run(
            [
                chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "--hide-scrollbars",
                "--allow-file-access-from-files", "--no-pdf-header-footer",
                f"--user-data-dir={temporary / 'profile'}", "--force-device-scale-factor=2",
                f"--window-size={diagram.width},{diagram.height + 288}",
                "--virtual-time-budget=5000", f"--screenshot={output}",
                "--dump-dom", document.as_uri(),
            ],
            capture_output=True, text=True, timeout=60, check=True,
        )
        if 'data-bpmn-status="ok"' not in result.stdout:
            raise RuntimeError(f"Error de importación BPMN en {diagram.code}: {result.stdout}")
        if 'data-bpmn-warnings="0"' not in result.stdout:
            raise RuntimeError(f"Advertencias de importación BPMN en {diagram.code}")
        if not output.is_file():
            raise RuntimeError(f"Chrome no generó {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", type=Path, help="Ruta a bpmn-viewer.production.min.js")
    parser.add_argument("--chrome", help="Ejecutable de Chrome/Chromium")
    parser.add_argument("--solo-bpmn", action="store_true", help="Generar únicamente los XML BPMN")
    arguments = parser.parse_args()
    chrome = arguments.chrome or shutil.which("google-chrome") or shutil.which("chromium")
    if not arguments.solo_bpmn:
        if not arguments.viewer or not arguments.viewer.is_file():
            parser.error("Se requiere --viewer con la ruta local de bpmn-js; consultar README.md")
        if not chrome:
            parser.error("No se encontró Chrome; proporcionar --chrome")
    directory = Path(__file__).resolve().parent
    diagrams = [estructura(), usuarios(), vinculos(), roles(), areas()]
    # Validar todos los recorridos antes de producir artefactos.
    models = [(diagram, diagram.xml()) for diagram in diagrams]
    for diagram, xml in models:
        source = directory / f"{diagram.filename}.bpmn"
        source.write_text(xml + "\n", encoding="utf-8")
        if not arguments.solo_bpmn:
            render(diagram, xml, arguments.viewer.resolve(), chrome,
                   directory / f"{diagram.filename}.png")
        print(f"{diagram.code}: {len(diagram.nodes)} nodos, {len(diagram.flows)} flujos; "
              + ("BPMN generado" if arguments.solo_bpmn else "BPMN importado sin advertencias y PNG generado"))


if __name__ == "__main__":
    main()
