"""
User-facing literal messages of the Auth module (single source of truth).

The wording is fixed by the user stories HU_DN_01_02 .. HU_DN_01_05 and must not be
paraphrased: the frontend and the tests assert these exact strings.
@sad 4.1.1
@origin [HU-Spec]
"""

# --- HU_DN_01_02: register manager ------------------------------------------------
NAME_REQUIRED = "El nombre completo es obligatorio."
NAME_TOO_LONG = "El nombre completo no puede superar los 100 caracteres."
EMAIL_INVALID = "El correo electrónico ingresado no tiene un formato válido."
EMAIL_ALREADY_REGISTERED = "Ya existe una cuenta registrada con este correo electrónico."
PASSWORD_WEAK = "La contraseña no cumple los requisitos mínimos de seguridad."
PASSWORD_MISMATCH = "Las contraseñas no coinciden."
REQUIRED_FIELDS = "Todos los campos obligatorios deben ser diligenciados."
ROLE_NOT_ALLOWED = "El registro público solo está disponible para el rol Gerente."
REGISTER_SUCCESS = "Su cuenta de Gerente ha sido registrada correctamente. Puede iniciar sesión."

# --- HU_DN_01_03: login ------------------------------------------------------------
INVALID_CREDENTIALS = "Credenciales no válidas. Verifique su correo y contraseña."
LOGIN_ATTEMPTS_EXCEEDED = (
    "Ha superado el número de intentos permitidos. Intente nuevamente más tarde."
)
ACCOUNT_DISABLED = "Su cuenta está desactivada. Contacte al Administrador."

# --- HU_DN_01_04 / HU_DN_01_05: session --------------------------------------------
LOGOUT_SUCCESS = "Sesión cerrada correctamente."
SESSION_EXPIRED = "Su sesión ha expirado. Inicie sesión nuevamente."
# Not worded by the stories: used when no valid session accompanies the request.
NOT_AUTHENTICATED = "Debe iniciar sesión para continuar."

# --- HU_DN_01_06: request password reset -------------------------------------------
PASSWORD_RESET_REQUEST_SUCCESS = (
    "Si el correo está registrado, recibirá un enlace para restablecer su contraseña."
)
EMAIL_SEND_FAILED = "No fue posible enviar el correo. Intente nuevamente."

# --- HU_DN_01_07: set password via one-time link -----------------------------------
PASSWORD_SET_SUCCESS = "Su contraseña ha sido establecida correctamente. Ya puede iniciar sesión."
INVALID_OR_EXPIRED_LINK = "El enlace no es válido o ha expirado. Solicite uno nuevo."

# --- HU_DN_01_10: admin-triggered reset --------------------------------------------
ADMIN_RESET_SENT = "Se ha enviado el enlace de restablecimiento al correo del usuario."
ADMIN_RESET_DISABLED_TARGET = "No se puede restablecer la contraseña de un usuario desactivado."

# --- EP-02: user provisioning and administration -----------------------------------
USER_CREATED = "Usuario creado correctamente. Se ha enviado un enlace de activación a su correo."
INVITE_DEVELOPER_SUCCESS = "Invitación enviada correctamente al Desarrollador."
INVITE_DEVELOPER_WITH_PASSWORD = (
    "Desarrollador creado. Comunica la contraseña inicial al usuario; "
    "debe cambiarla en su primer acceso."
)
USER_UPDATED = "Usuario actualizado correctamente."
MANAGER_ROLE_CHANGE_BLOCKED = (
    "No puede cambiar el rol de un Gerente responsable de proyectos. "
    "Reasigne primero la responsabilidad."
)
USER_NOT_FOUND = "Usuario no encontrado."
USER_DEACTIVATED = "Usuario desactivado correctamente."
USER_REACTIVATED = "Usuario reactivado correctamente."
SELF_DEACTIVATE_BLOCKED = "No puede desactivar su propia cuenta de Administrador."
MANAGER_DEACTIVATE_BLOCKED = (
    "No puede desactivar a un Gerente responsable de proyectos. "
    "Reasigne primero la responsabilidad."
)
REACTIVATE_NOT_INACTIVE = "Solo se pueden reactivar usuarios desactivados."
PROFILE_UPDATED = "Perfil actualizado correctamente."
AVATAR_INVALID = "El avatar debe ser una imagen PNG, JPG o WEBP de hasta 2 MB."
