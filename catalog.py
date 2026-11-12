"""Fictional demo catalogue; never represents live product availability."""
CATALOG = [
    {"sku": "AUDIO-001", "name": "Auriculares inalámbricos Flow", "price": 49.90, "category": "Audio", "icon": "🎧", "features": "auriculares cascos inalámbricos bluetooth música deporte micrófono comodidad earbuds wireless headphones"},
    {"sku": "AUDIO-002", "name": "Auriculares Studio ANC", "price": 89.00, "category": "Audio", "icon": "🎵", "features": "auriculares cascos diadema cancelación de ruido activa ANC viajes oficina música premium noise cancelling headphones"},
    {"sku": "AUDIO-003", "name": "Altavoz portátil Mini", "price": 34.50, "category": "Audio", "icon": "🔊", "features": "altavoz bluetooth portátil música viaje sonido speaker outdoor compacto"},
    {"sku": "TECH-004", "name": "Teclado mecánico Compact", "price": 65.00, "category": "Tecnología", "icon": "⌨️", "features": "teclado mecánico gaming programación trabajo oficina RGB compacto teclado keyboard"},
    {"sku": "TECH-005", "name": "Ratón ergonómico Pro", "price": 38.90, "category": "Tecnología", "icon": "🖱️", "features": "ratón mouse inalámbrico ergonómico gaming precisión oficina trabajo"},
    {"sku": "TECH-006", "name": "SSD externo 1 TB", "price": 79.90, "category": "Tecnología", "icon": "💾", "features": "disco externo SSD almacenamiento 1 terabyte USB C backup archivos juegos velocidad storage"},
    {"sku": "HOME-007", "name": "Lámpara escritorio Focus", "price": 27.90, "category": "Hogar", "icon": "💡", "features": "lámpara luz escritorio estudio trabajo lectura regulable iluminación desk lamp"},
    {"sku": "HOME-008", "name": "Mochila urbana Travel", "price": 55.00, "category": "Hogar", "icon": "🎒", "features": "mochila para portátil laptop viajar universidad oficina impermeable backpack"},
    {"sku": "TECH-009", "name": "Webcam Full HD", "price": 44.00, "category": "Tecnología", "icon": "📷", "features": "webcam cámara videoconferencia ordenador reuniones streaming full hd 1080p"},
    {"sku": "AUDIO-010", "name": "Micrófono USB Podcast", "price": 62.50, "category": "Audio", "icon": "🎙️", "features": "micrófono usb grabación podcast videollamada streaming audio voz"},
]
BY_SKU = {p["sku"]: p for p in CATALOG}
