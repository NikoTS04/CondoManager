# Lista de Verificación de Cumplimiento SDD (Compliance Checklist)

Utilice esta lista de verificación durante la revisión de código (Peer Review) antes de aprobar cualquier Pull Request hacia la rama `develop`.

---

## 1. Alineación con las Especificaciones
- [ ] ¿Existe una carpeta de dominio en `specs/02-domains/` vinculada al cambio?
- [ ] ¿Se actualizó la máquina de estados si se agregó un nuevo estado o transición?
- [ ] ¿Se actualizaron o añadieron los archivos `.feature` de prueba en Gherkin?
- [ ] Si se alteraron endpoints o payloads, ¿se actualizó `specs/03-contracts/openapi/condomanager.openapi.yaml`?

## 2. Guardarraíles de Arquitectura y Código
- [ ] **Zero-Float Check:** ¿Todos los importes monetarios usan `Decimal` y no `float`?
- [ ] **Audit Trail Check:** ¿Toda mutación de saldo o estado llama a `AuditoriaPayload` con los 7 campos obligatorios?
- [ ] **Idempotencia:** ¿Las operaciones de registro de pago o cobro implementan clave de idempotencia?
- [ ] **Concurrencia:** ¿Las reservas utilizan bloqueo pesimista `SELECT FOR UPDATE`?
- [ ] **Invariante de Solvencia:** ¿El módulo de reservas bloquea a departamentos con moras activas?

## 3. Calidad Automatizada
- [ ] ¿El script `python scripts/verify_sdd_compliance.py` pasa con 0 errores?
- [ ] ¿Las pruebas de `pytest src/tests/` pasan al 100%?
