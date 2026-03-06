# offerhunter/config.py

PLANS_PUBLIC = ["revendedor", "empresa"]  # lo que ve el usuario
PLAN_DEFAULT = "trial"  # para nuevos usuarios (si querés)

PLAN_LIMITS = {
    # interno / beta
    "trial": {
        "max_cazas_activas": 5,
        "min_interval_minutes": 12 * 60,
        "stores": ["mercadolibre", "generic"],
        "features": {
            "dashboard_empresa": False,
            "export_csv": False,
            "multi_store_same_hunt": False,
        },
    },
    # Plan 1
    "revendedor": {
        "max_cazas_activas": 100,
        "min_interval_minutes": 60,  # 60 min (ajustable)
        "stores": ["mercadolibre", "generic"],
        "features": {
            "dashboard_empresa": False,
            "export_csv": True,
            "multi_store_same_hunt": True,
        },
    },
    # Plan 2
    "empresa": {
        # acá el core no son "cazas", pero igual ponemos un tope por seguridad
        "max_cazas_activas": 300,
        "min_interval_minutes": 30,
        "stores": ["mercadolibre", "generic"],
        "features": {
            "dashboard_empresa": True,
            "export_csv": True,
            "multi_store_same_hunt": True,
        },
    },
}