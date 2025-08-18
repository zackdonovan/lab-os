# hub/ai_dashboard.py
import json
import time
from collections import defaultdict, deque
import paho.mqtt.client as mqtt
from typing import Dict, List, Optional

class AIDashboard:
    """Real-time AI insights dashboard"""
    
    def __init__(self):
        self.alerts = deque(maxlen=100)  # Last 100 alerts
        self.device_health = defaultdict(dict)
        self.correlations = []
        self.anomaly_stats = defaultdict(lambda: {'count': 0, 'last_seen': None})
        self.maintenance_schedule = defaultdict(dict)
        
    def add_alert(self, alert):
        """Add new alert to dashboard"""
        self.alerts.append(alert)
        
        # Update device health
        if 'device' in alert:
            device = alert['device']
            if alert['type'] == 'maintenance_recommendation':
                self.device_health[device] = {
                    'health_score': alert.get('health_score', 1.0),
                    'recommendations': alert.get('recommendations', []),
                    'last_updated': time.time()
                }
            elif alert['type'] == 'ai_anomaly':
                self.anomaly_stats[device]['count'] += 1
                self.anomaly_stats[device]['last_seen'] = time.time()
        
        # Update correlations
        if alert['type'] == 'correlation_discovery':
            self.correlations = alert.get('correlations', [])
    
    def get_dashboard_data(self) -> Dict:
        """Get current dashboard data"""
        return {
            'alerts': list(self.alerts)[-10:],  # Last 10 alerts
            'device_health': dict(self.device_health),
            'correlations': self.correlations,
            'anomaly_stats': dict(self.anomaly_stats),
            'summary': self._generate_summary()
        }
    
    def _generate_summary(self) -> Dict:
        """Generate AI insights summary"""
        total_alerts = len(self.alerts)
        ai_anomalies = sum(1 for a in self.alerts if a.get('type') == 'ai_anomaly')
        maintenance_alerts = sum(1 for a in self.alerts if a.get('type') == 'maintenance_recommendation')
        correlation_discoveries = sum(1 for a in self.alerts if a.get('type') == 'correlation_discovery')
        
        # Calculate average health score
        health_scores = [h.get('health_score', 1.0) for h in self.device_health.values()]
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 1.0
        
        return {
            'total_alerts': total_alerts,
            'ai_anomalies': ai_anomalies,
            'maintenance_alerts': maintenance_alerts,
            'correlation_discoveries': correlation_discoveries,
            'average_device_health': avg_health,
            'devices_monitored': len(self.device_health),
            'critical_issues': sum(1 for h in self.device_health.values() if h.get('health_score', 1.0) < 0.5)
        }

class AIDashboardAPI:
    """FastAPI integration for AI dashboard"""
    
    def __init__(self):
        self.dashboard = AIDashboard()
        self.mqtt_client = None
        self._setup_mqtt()
    
    def _setup_mqtt(self):
        """Setup MQTT client to receive alerts"""
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        
        try:
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"[AI Dashboard] MQTT connection failed: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        print("[AI Dashboard] Connected to MQTT")
        client.subscribe("lab/alerts")
    
    def _on_message(self, client, userdata, msg):
        try:
            alert = json.loads(msg.payload.decode("utf-8"))
            self.dashboard.add_alert(alert)
        except Exception as e:
            print(f"[AI Dashboard] Error processing alert: {e}")
    
    def get_dashboard(self):
        """Get dashboard data for API endpoint"""
        return self.dashboard.get_dashboard_data()
    
    def get_ai_insights(self):
        """Get AI insights and recommendations"""
        data = self.dashboard.get_dashboard_data()
        
        insights = {
            'system_health': self._assess_system_health(data),
            'recommendations': self._generate_recommendations(data),
            'trends': self._analyze_trends(data),
            'anomaly_analysis': self._analyze_anomalies(data)
        }
        
        return insights
    
    def _assess_system_health(self, data):
        """Assess overall system health"""
        health_scores = [h.get('health_score', 1.0) for h in data['device_health'].values()]
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 1.0
        
        if avg_health > 0.8:
            status = "excellent"
        elif avg_health > 0.6:
            status = "good"
        elif avg_health > 0.4:
            status = "fair"
        else:
            status = "poor"
        
        return {
            'overall_score': avg_health,
            'status': status,
            'devices_healthy': sum(1 for h in health_scores if h > 0.7),
            'devices_at_risk': sum(1 for h in health_scores if h < 0.5)
        }
    
    def _generate_recommendations(self, data):
        """Generate actionable recommendations"""
        recommendations = []
        
        # Device health recommendations
        for device, health in data['device_health'].items():
            if health.get('health_score', 1.0) < 0.5:
                recommendations.append({
                    'type': 'critical',
                    'device': device,
                    'message': f'Device {device} has critical health issues',
                    'action': 'Immediate maintenance required'
                })
        
        # Anomaly recommendations
        for device, stats in data['anomaly_stats'].items():
            if stats['count'] > 5:
                recommendations.append({
                    'type': 'warning',
                    'device': device,
                    'message': f'Device {device} showing frequent anomalies',
                    'action': 'Investigate measurement conditions'
                })
        
        # Correlation recommendations
        if data['correlations']:
            strong_correlations = [c for c in data['correlations'] if c['strength'] == 'strong']
            if strong_correlations:
                recommendations.append({
                    'type': 'info',
                    'message': f'Found {len(strong_correlations)} strong correlations between instruments',
                    'action': 'Review instrument placement and interference'
                })
        
        return recommendations
    
    def _analyze_trends(self, data):
        """Analyze trends in the data"""
        recent_alerts = [a for a in data['alerts'] if time.time() - a.get('ts', 0) < 3600]  # Last hour
        
        trend_analysis = {
            'alert_frequency': len(recent_alerts),
            'anomaly_trend': 'increasing' if len(recent_alerts) > 5 else 'stable',
            'most_active_device': self._get_most_active_device(data),
            'peak_activity_time': self._get_peak_activity_time(data)
        }
        
        return trend_analysis
    
    def _analyze_anomalies(self, data):
        """Analyze anomaly patterns"""
        ai_anomalies = [a for a in data['alerts'] if a.get('type') == 'ai_anomaly']
        
        if not ai_anomalies:
            return {'pattern': 'no_anomalies', 'confidence': 'high'}
        
        # Analyze anomaly patterns
        devices_with_anomalies = set(a.get('device') for a in ai_anomalies)
        anomaly_times = [a.get('ts') for a in ai_anomalies]
        
        return {
            'total_anomalies': len(ai_anomalies),
            'affected_devices': len(devices_with_anomalies),
            'pattern': 'clustered' if len(devices_with_anomalies) > 1 else 'isolated',
            'time_distribution': 'uniform' if len(set(anomaly_times)) > len(anomaly_times) * 0.8 else 'clustered'
        }
    
    def _get_most_active_device(self, data):
        """Get the device with most recent activity"""
        if not data['device_health']:
            return None
        
        return max(data['device_health'].keys(), 
                  key=lambda d: data['device_health'][d].get('last_updated', 0))
    
    def _get_peak_activity_time(self, data):
        """Get peak activity time from alerts"""
        if not data['alerts']:
            return None
        
        # Simple analysis - could be enhanced with more sophisticated time analysis
        return "recent" if any(time.time() - a.get('ts', 0) < 300 for a in data['alerts']) else "historical"

# Global instance for API integration
ai_dashboard = AIDashboardAPI()
