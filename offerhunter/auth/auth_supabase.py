from auth.supabase_client import supabase


# =========================
# REGISTRO
# =========================
def supa_signup(email: str, password: str, username: str, plan: str):
    try:
        email = email.strip().lower()
        username = username.strip()
        plan = (plan or "omega").strip().lower()

        # 1️⃣ Crear usuario en Supabase Auth
        res = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        user = getattr(res, "user", None)

        if not user:
            return None, "No se pudo crear el usuario."

        # 2️⃣ Crear perfil asociado
        supabase.table("profiles").insert({
            "user_id": user.id,
            "username": username,
            "email": email,
            "plan": plan,
            "role": "user"
        }).execute()

        return user, None

    except Exception as e:
        return None, str(e)


# =========================
# LOGIN (usuario o email)
# =========================
def supa_login(identifier: str, password: str):
    try:
        identifier = identifier.strip()

        # Si tiene @ → es email
        if "@" in identifier:
            res = supabase.auth.sign_in_with_password({
                "email": identifier.lower(),
                "password": password
            })
            user = getattr(res, "user", None)
            return (user, None) if user else (None, "Login falló.")

        # Si NO tiene @ → es username
        profile = (
            supabase
            .table("profiles")
            .select("email")
            .eq("username", identifier)
            .limit(1)
            .execute()
        )

        data = profile.data or []

        if not data:
            return None, "Usuario no encontrado."

        email = data[0]["email"]

        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        user = getattr(res, "user", None)
        return (user, None) if user else (None, "Login falló.")

    except Exception as e:
        return None, str(e)


# =========================
# RESET PASSWORD
# =========================
def supa_reset_password(email: str):
    try:
        supabase.auth.reset_password_email(email.strip().lower())
        return True
    except:
        return False