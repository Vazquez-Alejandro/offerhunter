from auth.supabase_client import supabase

def supa_login(email: str, password: str):
    """
    Devuelve (user, error_str). user es dict-like si ok.
    """
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        # res.user existe si ok
        if getattr(res, "user", None):
            return res.user, None
        return None, "Login falló."
    except Exception as e:
        return None, str(e)
    
from auth.supabase_client import supabase

def supa_signup(email: str, password: str):
    """
    Devuelve (user, error_str). user si ok.
    """
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if getattr(res, "user", None):
            return res.user, None
        # a veces devuelve user None pero manda email igual; dejamos mensaje claro
        return None, "Registro iniciado. Revisá tu email para confirmar."
    except Exception as e:
        return None, str(e)