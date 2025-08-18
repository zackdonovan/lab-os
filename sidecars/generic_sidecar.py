# sidecars/generic_sidecar.py
import importlib, time, sys, yaml, json
import paho.mqtt.client as mqtt

def load_driver(path, resource=None):
    mod = importlib.import_module(path)
    return mod.Driver(resource=resource)

def main(config_path):
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    name = cfg["name"]
    driver_path = cfg["driver"]
    poll_hz = cfg.get("poll_hz", 1.0)
    mqtt_host = cfg.get("mqtt_host", "localhost")
    mqtt_port = cfg.get("mqtt_port", 1883)
    resource = cfg.get("resource")

    print(f"[sidecar] Starting {name} using {driver_path}…")
    drv = load_driver(driver_path, resource=resource)

    client = mqtt.Client()
    client.connect(mqtt_host, mqtt_port, 60)
    client.loop_start()

    try:
        while True:
            data = drv.poll()
            topic = f"lab/device/{name}/telemetry"
            client.publish(topic, payload=json.dumps(data))
            print(f"[sidecar] sent {data}")
            time.sleep(1.0 / poll_hz)
    except KeyboardInterrupt:
        pass
    finally:
        drv.close()
        client.loop_stop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sidecars/generic_sidecar.py <config.yaml>")
        sys.exit(1)
    main(sys.argv[1])
