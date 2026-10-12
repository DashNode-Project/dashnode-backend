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
