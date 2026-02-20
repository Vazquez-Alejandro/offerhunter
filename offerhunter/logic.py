def evaluar_oferta(precio_actual, config):
    """
    precio_actual: int (ej: 1300000)
    config: dict con 'tipo' (piso/descuento) y 'objetivo' (valor o %)
    """
    tipo = config.get('tipo')
    objetivo = config.get('objetivo')

    if tipo == 'piso':
        if precio_actual <= objetivo:
            return True, f"¡Bajó del piso de ${objetivo}!"
            
    elif tipo == 'descuento':
        ref = config.get('precio_referencia')
        if not ref: return False, ""
        ahorro = ((ref - precio_actual) / ref) * 100
        if ahorro >= objetivo:
            return True, f"¡Superó el {objetivo}% de descuento! (Ahorro real: {int(ahorro)}%)"

    return False, ""