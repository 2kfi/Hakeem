# User Guide

## English

### About AIOL

> **AIOL** (Artificial Intelligence Open Lab) - Developed this project for the JOYS T323 competition.

---

## Table of Contents

1. [What is Hakeem?](#what-is-hakeem)
2. [Features](#features)
3. [Language Support](#language-support)
4. [Hardware Requirements](#hardware-requirements)
5. [How to Use](#how-to-use)
6. [Privacy & Disclaimers](#privacy--disclaimers)
7. [Limitations](#limitations)
8. [Getting Help](#getting-help)
9. [Related Documentation](#related-documentation)

---

## What is Hakeem?

Hakeem (حكيم) is a **medical voice assistant** that can listen to your health questions and answer them verbally - in both **English** and **Arabic**.

Think of it as having a knowledgeable medical companion that:
- Listens to your questions when you say "Hakeem"
- Understands what you're asking using advanced speech recognition
- Searches through trusted medical knowledge (Wikipedia)
- Responds with a natural voice answer

**Project Context:** This project was developed for the T323 competition (Jordan Young Scientists - JOYS).

---

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **Voice Activation** | Say "Hakeem" to activate - no buttons needed |
| **Bilingual Support** | Works in both English and Arabic |
| **Offline Knowledge** | Can access Wikipedia without internet |
| **Natural Voice** | Speaks answers back in clear audio |
| **Medical Focus** | Optimized for health-related questions |

### How It Works

1. **Wake Word Detection**: The system listens for "Hakeem"
2. **Speech Recognition**: Converts your voice to text
3. **AI Processing**: Analyzes your question using medical knowledge
4. **Voice Response**: Speaks the answer back to you

---

## Language Support

### Supported Languages

| Language | Speech Recognition | Voice Output |
|----------|-------------------|--------------|
| **English** | ✅ Full support | ✅ Multiple voices |
| **Arabic** | ✅ Full support | ✅ Arabic voice |

### Switching Languages

The system automatically detects which language you're speaking and responds in the same language!

- If you ask in English → Answer in English
- If you ask in Arabic (العربية) → Answer in Arabic (العربية)

---

## Hardware Requirements

### Minimum Requirements (Basic Use)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | Intel i3 / AMD Ryzen 3 | Intel i5 / AMD Ryzen 5 |
| **RAM** | 4 GB | 8 GB |
| **Storage** | 5 GB free | 10 GB free |
| **Microphone** | Built-in or USB mic | Desktop mic with noise reduction |
| **Speaker** | Built-in or headphones | External speakers |

### For Better Performance

| Component | Recommended |
|-----------|-------------|
| **GPU** | NVIDIA GTX 1050+ (optional, for faster processing) |
| **Internet** | Required for first-time model download |

### Running Without Powerful Hardware

The system has **three presets**:
- **Lightweight**: For older/slower computers (English only, smaller AI model)
- **Default**: Balanced performance (English + Arabic, medium AI model)
- **Heavy**: For powerful computers (English + Arabic, largest AI model)

---

## How to Use

### Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/2kfi/Hakeem.git
cd Hakeem

# 2. Copy settings file
cp .env.example .env

# 3. Start the system
docker-compose up --build

# 4. Wait for "Health check passed" message

# 5. Say "Hakeem" and ask a question!
```

### Testing Without Microphone

If you don't have a microphone set up, you can test using audio files:

```bash
# Test with an audio file
curl -X POST http://localhost:8003/process-audio \
  -F "file=@your_question.wav" \
  --output answer.wav

# Then play answer.wav to hear the response
```

### First-Time Setup

On first run, the system will:
1. Download required AI models (~2-5 GB)
2. Load speech recognition (Whisper)
3. Load voice synthesis (Piper)
4. Start the servers

**First run may take 5-15 minutes** depending on your internet speed.

---

## Privacy & Disclaimers

### Privacy

- **All processing happens locally** on your device (or your own server)
- **No audio is sent to external servers** (unless you configure it to)
- Your medical questions stay private

### ⚠️ Important Disclaimer

> **Hakeem is for educational and research purposes only.**
>
> This system:
> - Is NOT a substitute for professional medical advice
> - Is NOT certified for clinical diagnosis
> - May provide incomplete or incorrect information
> - Should NOT be used for medical emergencies
>
> **Always consult a qualified healthcare professional** for medical advice, diagnosis, or treatment.

---

## Limitations

### Current Limitations

| Limitation | Description |
|------------|-------------|
| **Knowledge Cutoff** | Training data may not include latest medical research |
| **Complex Questions** | May not understand very complex medical scenarios |
| **Regional Variations** | Medical practices may vary by country |
| **No Diagnosis** | Cannot provide formal medical diagnoses |
| **Internet Required** | First-time setup needs internet for downloads |

### What Hakeem Can Help With

- General health information
- Medical terminology explanations
- Symptom awareness
- Finding reliable health resources
- Learning about medical conditions

### What Hakeem Cannot Do

- Provide formal medical diagnoses
- Replace doctor consultations
- Handle medical emergencies
- Prescribe medications
- Access your real medical records

---

## Getting Help

### Troubleshooting

**System not starting:**
```bash
# Check Docker is running
docker ps

# Check logs
docker-compose logs
```

**Microphone not detected:**
- Check system microphone permissions
- Try a different microphone
- Test with an audio file instead

**Responses are slow:**
- Try the "lightweight" preset in config
- Consider adding a GPU
- Close other applications

### Support

For issues and questions:
- Check the [Troubleshooting Guide](./TROUBLESHOOTING.md)
- Review the [Configuration Guide](./CONFIG.md)
- Contact the development team

---

## Related Documentation

- [Developer Guide](./DEVELOPER.md) - Technical documentation
- [Developer Guide (Arabic)](./DEVELOPER_AR.md) - دليل المطور
- [Judges Report](./JUDGES.md) - Project technical details
- [Judges Report (Arabic)](./JUDGES_AR.md) - تقرير الحكام
- [Configuration](./CONFIG.md) - Settings and options