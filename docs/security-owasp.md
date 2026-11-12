# Revisión de seguridad (OWASP) — invitación y backlog

Fecha: 2026-10-20. Alcance: invitación de desarrollador y HU_DN_04_56–61.

| Riesgo | Control |
|---|---|
| A01 control de acceso roto | El desarrollador solo cambia el estado de sus tareas y el árbol no incluye tareas ajenas. El gerente no administra proyectos que no dirige. |
| A02 fallos criptográficos | La contraseña inicial ya no sale del servidor. El código de 6 dígitos se guarda con Argon2. El enlace guarda solo el hash del token. |
| A03 inyección | Consultas vía SQLAlchemy. Los filtros de texto no concatenan SQL. |
| A04 diseño inseguro | La cuenta nace inactiva. Hacen falta enlace y código. Máximo 5 códigos erróneos y 3 renovaciones de 24 horas. |
| A05 configuración | Secretos solo en `.env`. Las pruebas fuerzan `SMTP_HOST` vacío. CORS sin comodín. |
| A07 identificación | Sesión HttpOnly. Un pendiente o rechazado no inicia sesión. |
| A09 registro | El correo de invitación no se escribe en logs (ni código ni enlace). |

No se declara ausencia total de vulnerabilidades. La revisión cubre los flujos tocados en este cambio.
