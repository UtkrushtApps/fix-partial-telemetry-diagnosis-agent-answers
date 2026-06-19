"""JSON-style tool schemas exposed to the model."""

GET_SENSOR_STATUS = {
    "type": "function",
    "function": {
        "name": "get_sensor_status",
        "description": (
            "Retrieve the latest sensor reading for a single device. Read-only. "
            "Returns status, temperature, battery and the time the reading was "
            "recorded."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "The device identifier, e.g. 'dev-100'.",
                }
            },
            "required": ["device_id"],
        },
    },
}

GET_GATEWAY_STATUS = {
    "type": "function",
    "function": {
        "name": "get_gateway_status",
        "description": (
            "Retrieve the latest status for a device's parent gateway. Read-only. "
            "Returns status, uplink health and the time the status was recorded."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "gateway_id": {
                    "type": "string",
                    "description": "The gateway identifier, e.g. 'gw-001'.",
                }
            },
            "required": ["gateway_id"],
        },
    },
}

ALL_TOOLS = [GET_SENSOR_STATUS, GET_GATEWAY_STATUS]

