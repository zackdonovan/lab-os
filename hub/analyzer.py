# hub/analyzer.py
import json, os, time
from collections import defaultdict, deque
import paho.mqtt.client as mqtt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

BROKER = "localhost"
ALERT_TOPIC = "lab/alerts"
SUB_TOPIC = "lab/device/+/telemetry"
OUTDIR = os.path.join("data", time.strftime("%Y-%m-%d"))

os.makedirs(OUTDIR, exist_ok=True)
alerts_path = os.path.join(OUTDIR, "alerts.ndjson")

class OnlineStats:
    # Welford online mean/std + EMA slope
    def __init__(self, ema_alpha=0.2, slope_window=30):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0
        self.ema = None
        self.alpha = ema_alpha
        self.hist = deque(maxlen=slope_window)

    def update(self, x):
        # Welford
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.M2 += delta * (x - self.mean)
        # EMA + slope buffer
        self.ema = x if self.ema is None else (self.alpha * x + (1-self.alpha) * self.ema)
        self.hist.append(self.ema)

    @property
    def std(self):
        return (self.M2 / (self.n - 1))**0.5 if self.n > 1 else 0.0

    def slope(self):
        if len(self.hist) < 2: return 0.0
        return (self.hist[-1] - self.hist[0]) / (len(self.hist) - 1)

class IntelligentAnomalyDetector:
    """Enhanced anomaly detection using isolation forests and multivariate analysis"""
    
    def __init__(self, contamination=0.1):
        self.isolation_forest = IsolationForest(contamination=contamination, random_state=42)
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_buffer = deque(maxlen=100)  # Keep last 100 samples for training
        
    def extract_features(self, data_point):
        """Extract features from a data point for anomaly detection"""
        features = []
        
        # Basic statistical features
        if 'voltage' in data_point:
            features.extend([
                data_point['voltage'],
                data_point.get('voltage_avg', data_point['voltage']),
                data_point.get('voltage_std', 0.0)
            ])
        
        if 'current' in data_point:
            features.extend([
                data_point['current'],
                data_point.get('current_avg', data_point['current']),
                data_point.get('current_std', 0.0)
            ])
        
        # Temporal features
        features.extend([
            data_point.get('ts', time.time()) % 86400,  # Time of day
            data_point.get('ts', time.time()) % 3600,   # Minute of hour
        ])
        
        # Device-specific features
        device_hash = hash(data_point.get('device', 'unknown')) % 1000
        features.append(device_hash)
        
        return np.array(features)
    
    def detect_anomaly(self, data_point):
        """Detect anomalies using isolation forest"""
        features = self.extract_features(data_point)
        
        if len(features) == 0:
            return False, 0.0
        
        # Add to buffer for training
        self.feature_buffer.append(features)
        
        # Train model if we have enough data
        if len(self.feature_buffer) >= 50 and not self.is_fitted:
            self._train_model()
        
        if self.is_fitted:
            # Predict anomaly
            features_scaled = self.scaler.transform([features])
            prediction = self.isolation_forest.predict(features_scaled)[0]
            score = self.isolation_forest.score_samples(features_scaled)[0]
            
            # prediction = -1 for anomaly, 1 for normal
            is_anomaly = prediction == -1
            return is_anomaly, score
        
        return False, 0.0
    
    def _train_model(self):
        """Train the isolation forest model"""
        if len(self.feature_buffer) < 50:
            return
            
        features_array = np.array(list(self.feature_buffer))
        features_scaled = self.scaler.fit_transform(features_array)
        self.isolation_forest.fit(features_scaled)
        self.is_fitted = True
        print(f"[AI] Trained anomaly detection model with {len(features_array)} samples")

class PredictiveMaintenance:
    """Predictive maintenance using drift analysis and trend prediction"""
    
    def __init__(self):
        self.device_health = defaultdict(lambda: {
            'drift_rate': 0.0,
            'last_calibration': None,
            'failure_probability': 0.0,
            'recommendations': []
        })
        self.calibration_intervals = {
            'scope1': 30,  # days
            'multimeter': 90,
            'power_supply': 180,
            'default': 60
        }
    
    def update_health(self, device, data_point, stats):
        """Update device health metrics"""
        health = self.device_health[device]
        
        # Calculate drift rate
        if 'voltage' in data_point and stats['voltage'].n > 10:
            current_drift = abs(stats['voltage'].slope())
            health['drift_rate'] = 0.9 * health['drift_rate'] + 0.1 * current_drift
        
        # Predict failure probability based on drift
        if health['drift_rate'] > 0.01:  # High drift
            health['failure_probability'] = min(0.9, health['failure_probability'] + 0.01)
        else:
            health['failure_probability'] = max(0.0, health['failure_probability'] - 0.005)
        
        # Generate recommendations
        health['recommendations'] = self._generate_recommendations(device, health)
        
        return health
    
    def _generate_recommendations(self, device, health):
        """Generate maintenance recommendations"""
        recommendations = []
        
        if health['failure_probability'] > 0.7:
            recommendations.append(f"High failure risk detected. Consider replacement or maintenance.")
        
        if health['drift_rate'] > 0.005:
            recommendations.append(f"Significant drift detected. Calibration recommended.")
        
        days_since_cal = (time.time() - (health['last_calibration'] or 0)) / 86400
        cal_interval = self.calibration_intervals.get(device, self.calibration_intervals['default'])
        
        if days_since_cal > cal_interval:
            recommendations.append(f"Calibration overdue by {int(days_since_cal - cal_interval)} days.")
        
        return recommendations

class CrossInstrumentCorrelator:
    """Analyze correlations between different instruments"""
    
    def __init__(self):
        self.correlation_data = defaultdict(lambda: defaultdict(list))
        self.correlation_threshold = 0.7
        self.significant_correlations = []
    
    def add_data_point(self, device, metric, value, timestamp):
        """Add data point for correlation analysis"""
        self.correlation_data[device][metric].append({
            'value': value,
            'timestamp': timestamp
        })
    
    def analyze_correlations(self):
        """Analyze correlations between all devices and metrics"""
        correlations = []
        
        devices = list(self.correlation_data.keys())
        for i, dev1 in enumerate(devices):
            for dev2 in devices[i+1:]:
                for metric1 in self.correlation_data[dev1]:
                    for metric2 in self.correlation_data[dev2]:
                        corr = self._calculate_correlation(dev1, metric1, dev2, metric2)
                        if abs(corr) > self.correlation_threshold:
                            correlations.append({
                                'device1': dev1,
                                'metric1': metric1,
                                'device2': dev2,
                                'metric2': metric2,
                                'correlation': corr,
                                'strength': 'strong' if abs(corr) > 0.8 else 'moderate'
                            })
        
        self.significant_correlations = correlations
        return correlations
    
    def _calculate_correlation(self, dev1, metric1, dev2, metric2):
        """Calculate correlation between two metrics"""
        data1 = self.correlation_data[dev1][metric1]
        data2 = self.correlation_data[dev2][metric2]
        
        if len(data1) < 10 or len(data2) < 10:
            return 0.0
        
        # Align timestamps and calculate correlation
        values1 = [d['value'] for d in data1[-50:]]  # Last 50 points
        values2 = [d['value'] for d in data2[-50:]]
        
        if len(values1) != len(values2):
            return 0.0
        
        try:
            return np.corrcoef(values1, values2)[0, 1]
        except:
            return 0.0

# Initialize AI components
anomaly_detector = IntelligentAnomalyDetector()
maintenance_predictor = PredictiveMaintenance()
correlation_analyzer = CrossInstrumentCorrelator()

stats = defaultdict(lambda: {"voltage": OnlineStats(), "current": OnlineStats()})

def log_alert(alert):
    with open(alerts_path, "a") as f:
        f.write(json.dumps(alert) + "\n")

def on_connect(c, u, f, rc):
    print("[AI Analyzer] connected", rc)
    c.subscribe(SUB_TOPIC)

def on_message(c, u, msg):
    try:
        payload = msg.payload.decode("utf-8")
        # Try to parse as JSON first
        try:
            d = json.loads(payload)
        except json.JSONDecodeError:
            # If JSON fails, try to eval the Python dict string (for backward compatibility)
            try:
                d = eval(payload)
            except:
                print(f"[AI Analyzer] Failed to parse message: {payload[:100]}")
                return
        
        dev = d.get("device", "unknown")
        
        # Update basic statistics
        for key in ("voltage", "current"):
            val = d.get(key)
            if val is None: continue
            s = stats[dev][key]
            s.update(val)
            
            # Add to correlation analysis
            correlation_analyzer.add_data_point(dev, key, val, d.get("ts", time.time()))
            
            # Basic anomaly detection (legacy)
            st = s.std
            if s.n > 20 and st > 1e-9:
                z = abs(val - s.mean) / st
                if z >= 3.0:
                    alert = {
                        "ts": d["ts"], "device": dev, "metric": key,
                        "type": "statistical_anomaly", "value": val, "mean": s.mean, "std": st, "z": z
                    }
                    c.publish(ALERT_TOPIC, json.dumps(alert))
                    log_alert(alert)
            
            # Drift detection
            sl = s.slope()
            if s.n > 30 and abs(sl) > 0.002:
                alert = {
                    "ts": d["ts"], "device": dev, "metric": key,
                    "type": "drift", "slope": sl, "ema": s.ema
                }
                c.publish(ALERT_TOPIC, json.dumps(alert))
                log_alert(alert)
        
        # AI-powered anomaly detection
        is_anomaly, anomaly_score = anomaly_detector.detect_anomaly(d)
        if is_anomaly:
            alert = {
                "ts": d["ts"], "device": dev,
                "type": "ai_anomaly", "score": float(anomaly_score),
                "message": f"AI detected unusual pattern in {dev} data"
            }
            c.publish(ALERT_TOPIC, json.dumps(alert))
            log_alert(alert)
        
        # Predictive maintenance
        device_health = maintenance_predictor.update_health(dev, d, stats[dev])
        if device_health['recommendations']:
            alert = {
                "ts": d["ts"], "device": dev,
                "type": "maintenance_recommendation",
                "health_score": 1.0 - device_health['failure_probability'],
                "recommendations": device_health['recommendations']
            }
            c.publish(ALERT_TOPIC, json.dumps(alert))
            log_alert(alert)
        
        # Cross-instrument correlation analysis (run every 100 messages)
        if sum(len(correlation_analyzer.correlation_data[d][m]) for d in correlation_analyzer.correlation_data for m in correlation_analyzer.correlation_data[d]) % 100 == 0:
            correlations = correlation_analyzer.analyze_correlations()
            if correlations:
                alert = {
                    "ts": d["ts"],
                    "type": "correlation_discovery",
                    "correlations": correlations[:5]  # Top 5 correlations
                }
                c.publish(ALERT_TOPIC, json.dumps(alert))
                log_alert(alert)
                
    except Exception as e:
        print(f"[AI Analyzer] Error processing message: {e}")
        print(f"[AI Analyzer] Payload: {msg.payload.decode('utf-8', errors='ignore')[:100]}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
print("[AI Analyzer] subscribing to", SUB_TOPIC)
client.connect(BROKER, 1883, 60)
client.loop_forever()
