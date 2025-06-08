# -*- coding: utf-8 -*-
# pylint: disable=locally-disabled, multiple-statements
# pylint: disable=fixme, line-too-long, invalid-name
# pylint: disable=W0703
# pylint: disable=W0605

# Libreria estándar ----------------------------------------------------------------------------------------------------
#
import sys
import re
import time
import json
# ----------------------------------------------------------------------------------------------------------------------

# Paquetes instalados --------------------------------------------------------------------------------------------------
#
import paho.mqtt.client as mqtt
# ----------------------------------------------------------------------------------------------------------------------

# Importaciones locales ------------------------------------------------------------------------------------------------
#
import settings
# ----------------------------------------------------------------------------------------------------------------------

# Entorno --------------------------------------------------------------------------------------------------------------
#
DEBUG = settings.Config.DEBUG
MQTT_HOST = settings.Config.MQTT_HOST
MQTT_PORT = settings.Config.MQTT_PORT
MQTT_TOPIC_IN = settings.Config.MQTT_TOPIC_IN
MQTT_TOPIC_OUT = settings.Config.MQTT_TOPIC_OUT
# ----------------------------------------------------------------------------------------------------------------------

# Variable global ------------------------------------------------------------------------------------------------------
#
mqtt_client = None
# ----------------------------------------------------------------------------------------------------------------------

def validar_json(data):
    campos_requeridos = {
        "ts": int,
        "parser": str,
        "igate": str,
        "call": str,
        "fw": str,
        "rssi": int,
        "snr": (int, float)
    }

    regex_call_igate = re.compile(r'^E[A-D][1-9][A-Z]{1,3}-[0-9]{1,2}$|^E[A-D][1-9][A-Z]{1,3}$')
    regex_fw = re.compile(r'^AP[A-Z0-9]{4}$')

    # Verifica campos presentes y tipos correctos
    for campo, tipo in campos_requeridos.items():
        if campo not in data:
            return False, f"Falta el campo requerido: '{campo}'"
        if not isinstance(data[campo], tipo):
            return False, f"Tipo incorrecto para '{campo}': se esperaba {tipo}, se recibió {type(data[campo])}"

    # Validaciones adicionales
    if data["rssi"] > 0:
        return False, "RSSI debe ser un valor negativo o cero"
    if not -25 <= data["snr"] <= 40:
        return False, "SNR fuera de rango razonable (-20 a 40)"

    # Validar 'call' e 'igate' con regex
    for campo in ["call", "igate"]:
        if not regex_call_igate.match(data[campo]):
            return False, f"El campo '{campo}' no coincide con el formato esperado"

    # Validar 'fw' con regex
    if not regex_fw.match(data["fw"]):
        return False, "El campo 'fw' no coincide con el formato esperado"

    return True, "JSON válido"

def on_connect(client, userdata, flags, reasonCode, properties):
    global mqtt_client
    print(f"🔗 Conectado al broker MQTT: {MQTT_HOST}:{MQTT_PORT} - {reasonCode}")
    client.subscribe(MQTT_TOPIC_IN, qos=1)
    print(f"🔔 Suscrito al topic: {MQTT_TOPIC_IN}")

def on_message(client, userdata, msg):
    lora_payload = msg.payload.decode()
    no_parse = ["CRC", "CRC-ERROR", "TX", "OBJECT", "RADIOLIB_ERR_CRC_MISMATCH"]

    # Formato de salida esperado: --------------------------------------------------------------------------------------
    #
    # {"ts": 1748953837, "parser": "134", "igate": "EB1TK-10", "call": "EA6APL-7", "fw": "APLRT1", "rssi": -124, "snr": -1}
    # ------------------------------------------------------------------------------------------------------------------
    if DEBUG:
        print(lora_payload)

    patron_digi = re.compile(r'(E[A-D][1-9][A-Z]{1,3}-[0-9]{1,2}\*|E[A-D][1-9][A-Z]{1,3}\*|WIDE[1-3](?:-[1-3])?\*)')

    # Parser para CA2RXU
    #
    if "<165>" in lora_payload and not any(term in lora_payload for term in no_parse):
        try:
            data = lora_payload.split("/")
            data_header = data[0].split(" ")

            if not re.search(patron_digi, data[3]):

                data = [x.replace(" ", "") for x in data]
                call = re.fullmatch(r'E[A-D][1-9][A-Z]{1,3}-[0-9]{1,2}', data[2].replace(" ", ""))
                igate = data_header[2]
                rssi = re.search(r"-?\d+", data[5].upper())
                snr = re.search(r"-?\d+\.\d+", data[6].upper())

                json_data = {
                    'ts': int(time.time()),
                    'parser': "165",
                    'igate': igate,
                    'call': call[0],
                    'fw': data[3][:6],
                    'rssi': int(rssi[0]),
                    'snr': float(snr[0])
                }

                validez = validar_json(json_data)

                if validez[0]:
                    mqtt_client.publish(MQTT_TOPIC_OUT, str(json.dumps(json_data)), 1)
                    if DEBUG:
                        print(f"[165] Publicado: {json_data}")
                else:
                    print(f'\n{validez[1]}')
                    print(json_data)
                    print(lora_payload)
            else:
                print(f'DIGI: {lora_payload}')
                raise ValueError("Paquete repetido por DIGI")

        except Exception as e:
            pass

    # Parser para CA2RXU
    #
    elif "<134>" in lora_payload:
        try:
            diva = lora_payload.split(" - ")

            if not re.search(patron_digi, diva[3]):
                call = re.search(r"'.*?>", diva[3])
                call = call[0].replace("'", "").replace(">", "")

                igate = diva[1].split(" ")[0]

                rssi = re.search(r'RSSI:-\d*,', lora_payload)
                rssi = rssi[0].replace(r'RSSI:', "").replace(" ", "").replace(",", "")

                snr = re.search(r'SNR:.*', lora_payload)
                snr = snr[0].replace("SNR:", "").replace(" ", "")

                fw = re.search(r'AP[A-Z0-9]{4}', diva[3])
                fw = fw[0]

                json_data = {
                    'ts': int(time.time()),
                    'parser': "134",
                    'igate': igate,
                    'call': call,
                    'fw': fw[:6],
                    'rssi': int(rssi),
                    'snr': int(snr)
                }

                validez = validar_json(json_data)

                if validez[0]:
                    mqtt_client.publish(MQTT_TOPIC_OUT, str(json.dumps(json_data)), 1)
                    if DEBUG:
                        print(f"[134] Publicado: {json_data}")
                else:
                    print(f'\n{validez[1]}')
                    print(json_data)
                    print(lora_payload)

            else:
                print(f'DIGI: {lora_payload}')
                raise ValueError("Paquete repetido por DIGI")

        except Exception as e:
            pass

    else:
        pass

# Main function --------------------------------------------------------------------------------------------------------
#
def main():
    print("Iniciando: Lora Parser")

    if DEBUG:
        print("Configuración:")
        print(f"  MQTT_HOST: {MQTT_HOST}")
        print(f"  MQTT_PORT: {MQTT_PORT}")
        print(f"  MQTT_TOPIC_IN: {MQTT_TOPIC_IN}")
        print(f"  MQTT_TOPIC_OUT: {MQTT_TOPIC_OUT}")
        print("Presione enter para continuar...")
        input()

    try:
        # Crear cliente MQTT -------------------------------------------------------------------------------------------
        #
        global mqtt_client
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        # --------------------------------------------------------------------------------------------------------------

        # Configurar el cliente MQTT -----------------------------------------------------------------------------------
        #
        mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        # --------------------------------------------------------------------------------------------------------------

        # Callbacks para conexión y mensajes MQTT ----------------------------------------------------------------------
        #
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        # --------------------------------------------------------------------------------------------------------------

        # Loop MQTT ----------------------------------------------------------------------------------------------------
        #
        mqtt_client.loop_forever()
        # --------------------------------------------------------------------------------------------------------------

    except KeyboardInterrupt:
        print("Parando: Usuario")
        sys.exit(0)
    except EOFError:
        text = 'EOFError: %s' % EOFError
        print(text)
        print("Parando: EOFError")
        sys.exit(0)
    except OSError:
        text = 'OSError: %s' % OSError
        print("Parando: OSError")
        print(text)
        sys.exit(0)
    except Exception as e:
        text = 'Excepción general: %s' % e
        print("Parando: General")
        print(text)
        sys.exit(0)
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == '__main__':
    main()