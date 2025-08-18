# hub/saver.py
import os, json, time, pathlib, sys
import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "localhost")
TOPIC  = "lab/device/+/telemetry"
base = pathlib.Path("./data"); base.mkdir(exist_ok=True)

def log(*a):
    print(*a, flush=True)

def on_connect(client, userdata, flags, reason_code, properties=None):
    log(f"[saver] Connected to {BROKER} rc={reason_code}")
    client.subscribe(TOPIC)
    log(f"[saver] Subscribed to {TOPIC}")

def on_message(client, userdata, msg):
    try:
        d = json.loads(msg.payload)
        day = time.strftime("%Y-%m-%d", time.localtime(d["ts"]))
        outdir = base / day
        outdir.mkdir(exist_ok=True)
        path = outdir / f"{d['device']}.ndjson"
        with path.open("a") as f:
            f.write(json.dumps(d)+"\n")
        log(f"[saver] Saved {path}")
    except Exception as e:
        log("[saver] ERROR parsing/saving:", e)

def on_log(client, userdata, level, buf):
    # uncomment if you want MQTT client logs
    # log("[mqtt]", buf)
    pass

c = mqtt.Client()
c.on_connect = on_connect
c.on_message = on_message
c.on_log = on_log

log(f"[saver] Connecting to {BROKER}…")
c.connect(BROKER, 1883, 60)
c.loop_forever()
