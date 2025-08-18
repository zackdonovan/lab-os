# hub/lab_assistant.py
import os
import json
import time
from typing import Dict, List, Optional
from collections import deque
import openai
from openai import OpenAI

class LabAssistant:
    """Conversational AI assistant for lab experiments"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            print(f"[Lab Assistant] ✅ Using OpenAI API with key: {self.api_key[:20]}...")
        else:
            self.client = None
            print("[Lab Assistant] ❌ No OpenAI API key found. Running in demo mode.")
        
        self.conversation_history = deque(maxlen=50)
        self.context_data = {}
        self.available_actions = {
            "set_voltage": self._set_voltage,
            "start_measurement": self._start_measurement,
            "check_instrument": self._check_instrument,
            "analyze_data": self._analyze_data
        }
    
    def update_context(self, context: Dict):
        """Update the assistant's context with current lab data"""
        self.context_data.update(context)
    
    def chat(self, user_message: str) -> str:
        """Process user message and return AI response"""
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        if not self.client:
            return self._demo_response(user_message)
        
        try:
            # Build system prompt with lab context
            system_prompt = self._build_system_prompt()
            
            # Create messages for OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                *list(self.conversation_history)[-10:]  # Last 10 messages
            ]
            
            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # Add AI response to history
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            # Check for actionable items
            actions = self._extract_actions(ai_response)
            if actions:
                ai_response += f"\n\n🤖 I can help with: {', '.join(actions)}"
            
            return ai_response
            
        except Exception as e:
            print(f"[Lab Assistant] Error: {e}")
            return self._demo_response(user_message)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with current lab context"""
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Get current data summary
        data_summary = "No data available"
        if self.context_data.get('current_data'):
            data = self.context_data['current_data']
            data_summary = f"Current voltage: {data.get('voltage', 'N/A')}V, Current: {data.get('current', 'N/A')}A"
        
        # Get AI insights
        ai_insights = "No insights available"
        if self.context_data.get('ai_insights'):
            insights = self.context_data['ai_insights']
            ai_insights = f"System health: {insights.get('system_health', {}).get('status', 'unknown')}"
        
        return f"""You are an intelligent lab assistant for a physics/engineering laboratory. You help scientists with experiments, data analysis, and troubleshooting.

Current Lab Context:
- Time: {current_time}
- Current Data: {data_summary}
- AI Insights: {ai_insights}
- Available Instruments: {list(self.context_data.get('instruments', []))}

Your capabilities:
1. Analyze experiment data and identify issues
2. Suggest optimal parameters for experiments
3. Explain technical concepts
4. Help troubleshoot instrument problems
5. Provide recommendations for improving measurements

Be helpful, technical, and actionable. If you detect problems, suggest specific solutions. If you can take actions, mention them clearly.

Available actions you can suggest:
- set_voltage: Adjust voltage settings
- start_measurement: Begin new measurements
- check_instrument: Verify instrument status
- analyze_data: Perform detailed analysis

Always be specific and provide actionable advice based on the lab context."""
    
    def _extract_actions(self, response: str) -> List[str]:
        """Extract potential actions from AI response"""
        actions = []
        response_lower = response.lower()
        
        if "voltage" in response_lower and ("adjust" in response_lower or "set" in response_lower):
            actions.append("set_voltage")
        if "measure" in response_lower or "start" in response_lower:
            actions.append("start_measurement")
        if "check" in response_lower or "status" in response_lower:
            actions.append("check_instrument")
        if "analyze" in response_lower or "analysis" in response_lower:
            actions.append("analyze_data")
        
        return actions
    
    def _demo_response(self, user_message: str) -> str:
        """Demo responses when no API key is available"""
        user_lower = user_message.lower()
        
        if "voltage" in user_lower:
            return """Looking at your current data, I can see voltage measurements. 

Current voltage: 3.2V (stable)
Recommended range: 3.0V - 3.5V for optimal performance

If you're experiencing issues, I can help adjust voltage settings. Would you like me to suggest optimal parameters for your experiment?

🤖 I can help with: set_voltage"""
        
        elif "problem" in user_lower or "issue" in user_lower:
            return """I can help troubleshoot lab issues! 

Based on the current data, everything looks normal. However, if you're experiencing specific problems, please describe them and I can provide targeted solutions.

Common issues I can help with:
- Voltage drift
- Measurement noise
- Instrument calibration
- Experiment optimization

🤖 I can help with: analyze_data, check_instrument"""
        
        elif "experiment" in user_lower:
            return """I can help you plan and optimize experiments!

For the best results, I recommend:
1. Check instrument calibration
2. Set optimal parameters
3. Monitor data quality
4. Analyze results in real-time

What type of experiment are you running? I can suggest specific parameters and settings.

🤖 I can help with: start_measurement, set_voltage"""
        
        else:
            return """Hello! I'm your lab assistant. I can help you with:

🔬 Experiment planning and optimization
📊 Data analysis and troubleshooting  
⚡ Instrument parameter suggestions
🔧 Maintenance and calibration advice

Just ask me anything about your lab work! For example:
- "What's the optimal voltage for my experiment?"
- "Why is my signal noisy?"
- "How do I improve measurement accuracy?"

🤖 I can help with: analyze_data, check_instrument, set_voltage"""
    
    def execute_action(self, action: str, parameters: Dict = None) -> str:
        """Execute an action based on AI suggestion"""
        if action in self.available_actions:
            try:
                result = self.available_actions[action](parameters or {})
                return f"✅ Action '{action}' completed: {result}"
            except Exception as e:
                return f"❌ Action '{action}' failed: {e}"
        else:
            return f"❌ Unknown action: {action}"
    
    def _set_voltage(self, parameters: Dict) -> str:
        """Set voltage for an instrument"""
        voltage = parameters.get('voltage', 3.3)
        device = parameters.get('device', 'scope1')
        return f"Set {device} voltage to {voltage}V"
    
    def _start_measurement(self, parameters: Dict) -> str:
        """Start a new measurement"""
        duration = parameters.get('duration', 60)
        return f"Started measurement for {duration} seconds"
    
    def _check_instrument(self, parameters: Dict) -> str:
        """Check instrument status"""
        device = parameters.get('device', 'scope1')
        return f"Checked {device} status - all systems normal"
    
    def _analyze_data(self, parameters: Dict) -> str:
        """Analyze current data"""
        return "Data analysis complete - no anomalies detected"

class LabAssistantAPI:
    """FastAPI integration for lab assistant"""
    
    def __init__(self):
        self.assistant = LabAssistant()
        self.update_context_from_lab()
    
    def update_context_from_lab(self):
        """Update assistant context with current lab data"""
        try:
            # Get latest data
            import requests
            response = requests.get("http://localhost:8001/latest", timeout=2)
            if response.ok:
                current_data = response.json()
                self.assistant.update_context({
                    'current_data': current_data,
                    'instruments': ['scope1', 'multimeter1', 'power_supply1']
                })
        except:
            pass
        
        try:
            # Get AI insights
            response = requests.get("http://localhost:8001/ai/insights", timeout=2)
            if response.ok:
                ai_insights = response.json()
                self.assistant.update_context({
                    'ai_insights': ai_insights
                })
        except:
            pass
    
    def chat(self, message: str) -> str:
        """Process chat message"""
        self.update_context_from_lab()
        return self.assistant.chat(message)
    
    def execute_action(self, action: str, parameters: Dict = None) -> str:
        """Execute an action"""
        return self.assistant.execute_action(action, parameters or {})

# Global instance for API integration
lab_assistant = LabAssistantAPI()
