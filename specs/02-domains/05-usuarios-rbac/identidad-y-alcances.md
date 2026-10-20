# Identidad, cuatro roles y vínculos de departamento

CON-04 sustituye el directorio de login en memoria por PostgreSQL. Contrato de alta,
habilitación manual, selección de contexto y revocación: [alta-administrativa.md](alta-administrativa.md).
Los UUID de usuario proceden de la base de datos; los identificadores `usr-*` de los
ejemplos históricos no son identidades de login persistentes. El JWT v2 incorpora
`auth_revision`, comprobada en cada petición protegida.

Fuente de verdad: checks `ck_rol_nombre` y `ck_tipo_relacion` de
`condomanager_schema.sql`. No se requiere migración de roles: el ORM/SQL ya usan
`RESIDENTE`; se actualizan el directorio piloto, JWT y cliente.

## Contrato de autenticación v2

`POST /auth/login`, `GET /auth/me` y `GET /auth/demo-users` comparten el perfil:

```json
{
  "id": "usr-res-102",
  "email": "residente102@villabonita3.pe",
  "nombre": "Ana",
  "apellido": "Gómez (Solvente)",
  "rol": "RESIDENTE",
  "condominio_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "departamentos": [
    {
      "departamento_id": "48c8c328-8a14-59b6-bc14-c905db21e630",
      "numero": "102",
      "tipo_relacion": "PROPIETARIO_TITULAR",
      "es_activo": true
    }
  ]
}
```

El UUID del ejemplo es ilustrativo; se utiliza siempre el UUID devuelto por la API.
No hay `tipo_relacion` global: un administrador sin vínculo real devuelve una lista
vacía. La condición de propietario/inquilino se muestra según el vínculo seleccionado.
El JWT transporta el mismo arreglo, el identificador de usuario como `sub` y
`session_version: 2`. Las sesiones anteriores requieren un nuevo login.

## Recursos autorizados

- `GET /cuotas/departamentos`: padrón piloto filtrado por condominio y, para
  residentes, por sus vínculos activos. Devuelve UUID, número, piso, coeficiente,
  saldo y estado financiero; nunca todas las unidades a un residente.
- `GET /pagos/comprobantes` y `GET /reservas`: solo recursos de unidades autorizadas;
  `condominio_id` opcional selecciona el contexto para administrativos globales.
- `POST /pagos/reportar`, `POST /reservas` y cancelación: validar UUID del recurso,
  rol, condominio y vínculo antes de ejecutar lógica de negocio.
- `GET /areas` y `GET /areas/{area_id}/disponibilidad?fecha=YYYY-MM-DD`:
  catálogo contextual y horarios ocupados sin revelar propietarios ni unidades.
- Notificaciones: consulta para administrativos/auditor de su condominio;
  despacho, reenvío y envío masivo solo para `SUPERADMIN`/`ADMIN_JUNTA`.
- `AUDITOR` no escribe; `RESIDENTE` no accede a operaciones administrativas.
- Los clientes no sustituyen errores de autorización/red por éxitos o datos mock.

## Verificación

Probar ambos perfiles de residentes, relaciones mixtas en varias unidades, vínculos
inactivos, unidad ajena, cruce de condominios, escritura por auditor, roles antiguos,
suplantación de `es_admin`, mora y límite de cancelación de 24 horas. Verificar
restauración de sesión y cambios de unidad mediante UUID en la navegación.
