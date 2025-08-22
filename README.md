# Lab-OS: Operating System for Physics & Engineering Labs

Lab-OS is a comprehensive platform designed to streamline laboratory operations by providing real-time data monitoring, AI-powered insights, and automated experiment management for physics and engineering laboratories.

##  Features

### Core Functionality
- **Real-time Data Streaming**: MQTT-based telemetry from lab instruments
- **Multi-instrument Support**: VISA, SCPI, and custom driver support
- **Data Persistence**: Time-series data storage in NDJSON format
- **Web Dashboard**: Real-time charts and system monitoring

### AI Integration
- **Anomaly Detection**: Machine learning-based drift and anomaly detection
- **Predictive Maintenance**: AI-powered instrument health monitoring
- **Lab Assistant**: Conversational AI for experiment guidance
- **System Health Scoring**: Real-time health assessment

### Experiment Management
- **Device Discovery**: Automatic VISA instrument detection
- **Configuration Management**: YAML-based device configuration
- **Experiment Optimization**: AI-suggested parameter optimization

##  Architecture

```
Lab-OS/
├── hub/                 # Central API and coordination
│   ├── api.py          # FastAPI web server
│   ├── analyzer.py     # AI analysis engine
│   ├── discovery.py    # Device discovery
│   ├── saver.py        # Data persistence
│   └── lab_assistant.py # AI chat interface
├── drivers/            # Instrument drivers
│   ├── demo/           # Demo/simulation drivers
│   └── rigol/          # Rigol instrument drivers
├── sidecars/           # Device communication
├── config/             # Device configurations
└── data/               # Time-series data storage
```

## Installation

### Prerequisites
- Python 3.8+
- Anaconda (recommended)
- Git

### Setup
```bash
# Clone the repository
git clone https://github.com/zackdonovan/lab-os.git
cd lab-os

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export OPENAI_API_KEY="your_openai_api_key_here"
```

##  Quick Start

### 1. Start the Data Pipeline
```bash
# Start the sidecar (device communication)
PYTHONPATH=. python sidecars/generic_sidecar.py config/scope1.yaml

# Start the analyzer (AI processing)
PYTHONPATH=. python hub/analyzer.py

# Start the web server
uvicorn hub.api:app --reload --port 8002
```

### 2. Access the Dashboard
- **Main Dashboard**: http://localhost:8002/
- **AI Assistant**: http://localhost:8002/ai
- **API Documentation**: http://localhost:8002/docs

##  Dashboard Features

### Main Dashboard (`/`)
- Real-time voltage and current charts
- System health monitoring
- AI insights and recommendations
- Device control interface

### AI Assistant (`/ai`)
- Conversational AI interface
- Experiment guidance
- Data analysis requests
- System troubleshooting

## 🔧 Configuration

### Device Configuration
Create YAML configuration files in `config/`:

```yaml
# config/scope1.yaml
device:
  name: "scope1"
  driver: "drivers.demo.random_meter"
  parameters:
    sample_rate: 1.0
    voltage_range: [0, 5]
    current_range: [0, 0.2]
```

### Environment Variables
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `MQTT_BROKER`: MQTT broker address (default: localhost)
- `MQTT_PORT`: MQTT broker port (default: 1883)

##  AI Features

### Anomaly Detection
- **Drift Detection**: Exponential moving average analysis
- **Multivariate Anomaly Detection**: Isolation Forest algorithm
- **Real-time Alerts**: Instant notification of anomalies

### Lab Assistant
- **Natural Language Interface**: Ask questions about your experiments
- **Context Awareness**: Access to real-time lab data
- **Actionable Insights**: AI-powered recommendations

### System Health
- **Health Scoring**: 0-100% system health assessment
- **Device Status**: Individual instrument health monitoring
- **Predictive Alerts**: Early warning system

##  Data Flow

```
Instruments → Sidecars → MQTT → Analyzer → Database
     ↓           ↓        ↓        ↓         ↓
  VISA/SCPI   Drivers   Broker   AI/ML    NDJSON
     ↓           ↓        ↓        ↓         ↓
  Discovery   Config   Real-time  Insights  History
```

##  API Endpoints

### Data Endpoints
- `GET /latest` - Latest device readings
- `GET /history` - Historical data
- `GET /ai/insights` - AI analysis results

### Control Endpoints
- `POST /chat` - AI assistant chat
- `GET /discover/visa` - VISA device discovery

##  Supported Instruments

### Currently Supported
- **Demo/Random Meter**: Simulation driver for testing
- **Rigol Instruments**: Oscilloscopes and function generators

### Planned Support
- **Keithley Instruments**: Multimeters and source meters
- **Tektronix**: Oscilloscopes and analyzers
- **Custom Drivers**: User-defined instrument support

##  Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

##  Acknowledgments

- **OpenAI**: For GPT integration and AI capabilities
- **FastAPI**: For the web framework
- **MQTT**: For real-time messaging
- **VISA**: For instrument communication standards

##  Support

For questions, issues, or contributions:
- **Issues**: [GitHub Issues](https://github.com/zackdonovan/lab-os/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zackdonovan/lab-os/discussions)

---

**Lab-OS**: Making laboratory automation accessible and intelligent. 
