async def project_discovery(conn, ev: dict):
    """Si el evento es un hallazgo de auto-descubrimiento, upsertea el
    inventario durable de equipos (marca, modelo, protocolo, compatibilidad,
    si quedó auto-conectado). Se mantiene separado de `process()` en
    main.py para no mezclar la responsabilidad de persistencia genérica de
    eventos con la proyección específica de inventario de dispositivos.
    """
    if ev.get("type") != "DEVICE_DISCOVERED":
        return
    p = ev.get("payload", {})
    await conn.execute(
        """INSERT INTO discovered_devices(device_id,device_class,vendor,model,protocol,address,compatibility,auto_connected,zone,metadata)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
           ON CONFLICT(device_id) DO UPDATE SET
             vendor=EXCLUDED.vendor, model=EXCLUDED.model, protocol=EXCLUDED.protocol,
             compatibility=EXCLUDED.compatibility, auto_connected=EXCLUDED.auto_connected,
             last_seen=now(), metadata=EXCLUDED.metadata""",
        ev["device_id"], p.get("device_class", "UNKNOWN"), p.get("vendor"), p.get("model"),
        p.get("protocol", "UNKNOWN"), p.get("address", ""), p.get("compatibility", "UNKNOWN"),
        bool(p.get("auto_connected", False)), ev.get("zone", ""),
        __import__("json").dumps({"stream_url": p.get("stream_url")}),
    )
