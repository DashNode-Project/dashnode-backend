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
