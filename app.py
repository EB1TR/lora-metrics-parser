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


def on_connect(client, userdata, flags, reasonCode, properties):
    global mqtt_client
    print(f"🔗 Conectado al broker MQTT: {MQTT_HOST}:{MQTT_PORT} - {reasonCode}")
    client.subscribe(MQTT_TOPIC_IN, qos=1)
    print(f"🔔 Suscrito al topic: {MQTT_TOPIC_IN}")

def on_message(client, userdata, msg):
    lora_payload = msg.payload.decode()

    # Formato de salida esperado: ----------------------------------------------------------------------------------------------------
    #
    # {"ts": 1748953837, "parser": "134", "igate": "EB1TK-10", "call": "EA6APL-7", "fw": "APLRT1", "digi": 0, "rssi": -124, "snr": -1}
    # --------------------------------------------------------------------------------------------------------------------------------
    if DEBUG:
        print(lora_payload)
    # Parser para CA2RXU
    #
    if "<165>" in lora_payload:
        data = lora_payload.split("/")
        data_header = data[0].split(" ")
        if data_header[7].upper() not in ("CRC", "CRC-ERROR", "TX", "OBJECT", "RADIOLIB_ERR_CRC_MISMATCH"):

            data = [x.replace(" ", "") for x in data]
            try:
                igate = data_header[2]
                call = re.fullmatch(r'E[A-D][1-9][A-Z]{1,3}-[0-9]{1,2}', data[2].replace(" ", ""))
                rssi = re.search(r"-?\d+", data[5].upper())
                snr = re.search(r"-?\d+\.\d+", data[6].upper())
                fw = data[3]
                digi = 0

                if len(fw.split(',')) > 1:
                    digi = 1
                    fw = fw.split(',')[0]

                json_data = {
                    'ts': int(time.time()),
                    'parser': "165",
                    'igate': igate,
                    'call': call[0],
                    'fw': fw[:6],
                    'digi': digi,
                    'rssi': int(rssi[0]),
                    'snr': float(snr[0])
                }

                if json_data['digi'] == 0 and len(json_data['call']) < 10:
                    mqtt_client.publish(MQTT_TOPIC_OUT, str(json.dumps(json_data)), 1)
                    if DEBUG:
                        print(f"📤 Publicado: {json_data}")
                else:
                    mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)

            except Exception as e:
                mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)

    # Parser para CA2RXU
    #
    elif "<134>" in lora_payload:
        try:
            diva = lora_payload.split(" - ")
            igate = diva[1].split(" ")[0]

            rssi = re.search(r'RSSI:-\d*,', lora_payload)
            rssi = rssi[0].replace(r'RSSI:', "").replace(" ", "").replace(",", "")

            snr = re.search(r'SNR:.*', lora_payload)
            snr = snr[0].replace("SNR:", "").replace(" ", "")

            call = re.search(r"'.*>", diva[3])
            call = call[0].replace("'", "").replace(">", "")

            fw = re.search(r'AP[A-Z0-9]{4}', diva[3])
            fw = fw[0]

            json_data = {
                'ts': int(time.time()),
                'parser': "134",
                'igate': igate,
                'call': call,
                'fw': fw[:6],
                'digi': 0,
                'rssi': int(rssi),
                'snr': int(snr)
            }

            if len(call.split(",")) > 1:
                json_data['digi'] = 1


            if json_data['digi'] == 0 and len(json_data['call']) < 10:
                mqtt_client.publish(MQTT_TOPIC_OUT, str(json.dumps(json_data)), 1)
                if DEBUG:
                    print(f"📤 Publicado: {json_data}")
            else:
                mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)
        except Exception as e:
            mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)

    else:
        mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)

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