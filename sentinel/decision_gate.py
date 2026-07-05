# φ-Confidence Gate
CONFIDENCE_THRESHOLD = 0.75

def gate_decision(data):
    if data.get('confidence', 0) >= CONFIDENCE_THRESHOLD:
        return "EXECUTE"
    return "HARD_STOP"
print("Decision Gate Initialized")
