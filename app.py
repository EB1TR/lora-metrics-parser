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
MQTT_HOST = settings.Config.MQTT_HOST
MQTT_PORT = settings.Config.MQTT_PORT
MQTT_TOPIC_IN = settings.Config.MQTT_TOPIC_IN
MQTT_TOPIC_OUT = settings.Config.MQTT_TOPIC_OUT
# ----------------------------------------------------------------------------------------------------------------------



def on_connect(client, userdata, flags, reasonCode, properties):
    print("✅ Conectado correctamente.")
    client.subscribe(MQTT_TOPIC_IN, qos=1)

def on_message(client, userdata, msg):
    lora_payload = msg.payload.decode()

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
                    mqtt_client.publish(MQTT_TOPIC_OUT, str(json_data), 1)
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
                mqtt_client.publish(MQTT_TOPIC_OUT, str(json_data), 1)
            else:
                mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)
        except Exception as e:
            mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)

    else:
        mqtt_client.publish("lora/syslog/unparsed", str(lora_payload), 1)

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def main():
    try:
    # Conectar al broker MQTT ------------------------------------------------------------------------------------------
        mqtt_client.loop_forever()

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