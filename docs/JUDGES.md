# Technical Report for Judges

## English

---

# Hakeem: Medical Voice Assistant

## A Voice-Powered AI System for Medical Information Access

**Project T323 - JOYS Competition (Jordan Young Scientists)**

**Developed by AIOL**

---

## 1. Project Overview

### 1.1 Project Title
**Hakeem** (حكيم) - Arabic for "Physician/Wise Man"

### 1.2 Team Information

| Role | Name |
|------|------|
| **Lead Developer / AI/ML / Hardware** | Arkan Fakoseh |
| **Liver System Dev & UI Optimizer** | Ahmad Shamili |
| **Mentor** | Razan Kenji |

**School:** المنشية الثانوية للبيني
**Country:** Jordan
**Competition:** JOYS 2026 - T323
**Date:** April 2026

---

## 2. Abstract

This project presents **Hakeem**, a bilingual (English/Arabic) medical voice assistant that enables hands-free access to medical information through natural speech interaction. The system combines state-of-the-art speech recognition (Whisper), a medical-domain fine-tuned language model (MedGemma), offline knowledge retrieval (Wikipedia via ZIM files), and natural voice synthesis (Piper TTS).

Key innovations include:
- Custom wake word detection ("Hakeem")
- Bilingual support (English + Arabic)
- Offline operation capability
- Medical domain optimization using MedGemma

The system achieves competitive performance on medical question-answering benchmarks while maintaining accessibility for users with limited technical knowledge or hardware resources.

---

## 3. Problem Statement

### 3.1 Background

In the Arab world and developing regions, access to reliable medical information remains challenging:
- Limited healthcare professionals per capita
- Language barriers in medical information
- Internet connectivity issues in rural areas
- High cost of healthcare consultations

### 3.2 The Problem

1. **Information Gap**: Many people cannot easily access reliable health information
2. **Language Barrier**: Most medical resources are in English; Arabic resources are limited
3. **Accessibility**: Physical interactions with healthcare systems are not always possible
4. **Digital Divide**: Complex interfaces exclude elderly or less-tech-savvy users

### 3.3 Our Solution

Hakeem addresses these challenges by providing:
- Voice-based interaction (accessible to all)
- Bilingual support (Arabic + English)
- Offline capability (works without internet after setup)
- Simple activation ("Hakeem" wake word)

---

## 4. Technical Approach

### 4.1 System Architecture

The Hakeem system follows a four-stage pipeline:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Wake      │    │     STT      │    │     LLM      │    │     TTS      │
│   Word      │───▶│  (Whisper)   │───▶│  (MedGemma)  │───▶│   (Piper)    │
│  Detection  │    │              │    │  + MCP Tools │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                           │                    │                    │
                           └────────────────────┴────────────────────┘
                                                 │
                                          ┌──────┴──────┐
                                          │  FastAPI   │
                                          │   Server   │
                                          │   :8003    │
                                          └────────────┘
```

### 4.2 Component Details

#### A. Wake Word Detection
- **Technology**: openWakeWord with custom ONNX model
- **Wake Word**: "Hakeem" (Arabic for physician)
- **Model**: Custom-trained on Arabic-accented English and Arabic pronunciations

#### B. Speech-to-Text (STT)
- **Technology**: Faster-Whisper (optimized Whisper)
- **Models Used**:
  - `medium` (default) - balanced accuracy/speed
  - `small` (lightweight) - for weaker hardware
  - `large-v3` (heavy) - maximum accuracy
- **Features**: Voice Activity Detection (VAD), language detection

#### C. Language Model (LLM) - Primary: MedGemma
- **Primary Model**: MedGemma (Google's medical-domain fine-tuned Gemma)
- **Inference**: llama.cpp for local deployment (quantized to 4-bit)
- **Context Window**: 4096 tokens
- **System Prompt**: Optimized for concise, natural medical responses

**Benchmark Comparison:**
| Model | Type | MCQ Accuracy | Avg MCQ Time | Avg Gen Time |
|-------|------|--------------|--------------|--------------|
| **MedGemma** | Primary (Medical) | Target | - | - |
| Qwen3-4B | Benchmark | 25% | 1.44s | 10.65s |

#### D. Knowledge Retrieval (MCP)
- **Protocol**: Model Context Protocol (MCP)
- **Data Source**: Wikipedia ZIM files (offline Wikipedia dumps)
- **Tools Provided**: search, get_article, list_articles, get_suggestions

#### E. Text-to-Speech (TTS)
- **Technology**: Piper TTS
- **Languages**: 
  - English: en_GB-cori-high
  - Arabic: ar_JO-kareem-medium

### 4.3 Technology Stack

| Layer | Technology |
|-------|------------|
| **Framework** | FastAPI |
| **ML Runtime** | ONNX Runtime, llama.cpp |
| **Container** | Docker, Docker Compose |
| **Audio** | PyAudio, wave |
| **Protocol** | HTTP, SSE (for MCP) |

---

## 5. Features

### 5.1 Core Features

| Feature | Description |
|---------|-------------|
| **Voice Activation** | Say "Hakeem" to activate hands-free |
| **Bilingual Operation** | Works in English and Arabic |
| **Offline Knowledge** | Wikipedia access without internet |
| **Natural Speech Output** | Human-like voice responses |
| **Medical Domain Focus** | Optimized for health questions using MedGemma |
| **Multi-Platform** | Runs on CPU, GPU, Docker, or bare metal |

### 5.2 Performance Presets

| Preset | STT Model | TTS | Compute | Use Case |
|--------|-----------|-----|---------|----------|
| **Lightweight** | whisper-small | EN only | int8 | Weak hardware |
| **Default** | whisper-medium | EN + AR | int8 | Balanced |
| **Heavy** | whisper-large-v3 | EN + AR | float16 | High performance |

### 5.3 Hardware Compatibility

- **CPU-only**: Runs on consumer-grade processors
- **GPU Acceleration**: NVIDIA CUDA support
- **AMD ROCm**: AMD GPU support
- **Docker**: Containerized deployment
- **Bare Metal**: Direct Python execution

---

## 6. Performance Metrics

### 6.1 Benchmark Results

The system was evaluated on a medical question-answering dataset (100 questions) using Qwen3-4B as benchmark:


| **Benchmark Model**                  | **MCQ Accuracy** | **Average MCQ Time** | **Average Generative Response Time** |
| ------------------------------------ | ---------------- | -------------------- | ------------------------------------ |
| Qwen3-4B-it                          | 25%              | 1.435                | 10.65                                |
| Gemm3-4B-it                          | 48%              | 0.909                | 10.96                                |
| MedGemma-4B-it                       | 49%              | 0.909                | 7.815                                |
| MedGemma-4B-it-Fine-tuned            | 53%              | 1.378                | 1.962                                |
**Note:** MedGemma is our primary model for medical accuracy. Qwen3-4B was tested as a benchmark baseline.

### 6.2 System Performance

| Metric | Value |
|--------|-------|
| **Startup Time** | 15-30 seconds |
| **End-to-End Latency** | 5-15 seconds |
| **Memory Usage** | 2-4 GB (CPU), 4-8 GB (GPU) |
| **Model Size** | ~4 GB (quantized LLM) |

### 6.3 Quality Observations

- **Strengths**: Fast inference, bilingual output, offline capability, medical domain optimization
- **Primary Model**: MedGemma provides better medical accuracy than general-purpose models
- **Areas for Improvement**: Larger model capacity, more training data

---

## 7. Ethical Considerations

### 7.1 Medical Disclaimer

> **IMPORTANT**: Hakeem is developed for **educational and research purposes only**. It is NOT:
> - A certified medical device
> - A substitute for professional medical advice
> - Approved for clinical diagnosis or treatment
>
> Users should **always consult qualified healthcare professionals** for medical concerns.

### 7.2 Privacy

- All processing can run locally (no cloud dependency)
- Audio data stays on user's device
- No personal health data collection

### 7.3 Bias & Limitations

- Model trained on English-centric medical data
- Arabic medical vocabulary coverage limited
- Knowledge cutoff based on training data date
- May not represent all regional medical practices

---

## 8. Limitations & Future Work

### 8.1 Current Limitations

1. **Model Size**: Quantized to 4-bit; full model would improve accuracy
2. **Knowledge Base**: Limited to Wikipedia; medical textbooks would improve quality
3. **Evaluation**: Single benchmark; needs broader testing
4. **Wake Word**: Single language (English "Hakeem"); Arabic wake word not implemented
5. **No Diagnosis**: Cannot provide formal medical diagnoses

### 8.2 Future Work

| Priority | Improvement | Description |
|----------|-------------|-------------|
| **High** | Larger LLM | Use 7B or 8B model for better accuracy |
| **High** | Medical Knowledge | Add medical textbook ZIM files |
| **Medium** | Arabic Wake Word | Train Arabic "حكيم" wake word model |
| **Medium** | Diagnosis Capability | Add symptom analysis tools |
| **Low** | Multi-language | Support more languages |
| **Low** | Mobile App | iOS/Android companion app |

### 8.3 Scalability

The system can be deployed:
- Locally on a laptop
- On a home server (Raspberry Pi to desktop)
- In a cloud environment
- On specialized AI hardware

---

## 9. Conclusion

Hakeem demonstrates the potential of voice AI for democratizing access to medical information, particularly in regions with limited healthcare resources or language barriers. By combining open-source technologies (Whisper, Piper, llama.cpp) with medical domain optimization (MedGemma), the project achieves a functional voice assistant that runs on consumer hardware.

The bilingual (English/Arabic) design addresses a critical gap in Arabic-speaking regions, while the offline capability ensures accessibility in areas with limited internet connectivity.

### Key Achievements

✅ Functional voice assistant with medical focus  
✅ Bilingual support (English + Arabic)  
✅ Offline operation capability  
✅ Runs on consumer hardware  
✅ Docker deployment ready  
✅ Open architecture for extension  

---

## 10. References

### Models & Libraries

1. **MedGemma** - Medical-domain fine-tuned model
   - https://huggingface.co/Google/medgemma

2. **Whisper** - OpenAI's speech recognition
   - https://github.com/openai/whisper

3. **Faster-Whisper** - Optimized Whisper implementation
   - https://github.com/Systran/faster-whisper

4. **Piper** - Neural text-to-speech system
   - https://github.com/rhasspy/piper

5. **llama.cpp** - LLM inference engine
   - https://github.com/ggerganov/llama.cpp

6. **openWakeWord** - Wake word detection
   - https://github.com/dscripka/openWakeWord

7. **Model Context Protocol (MCP)**
   - https://modelcontextprotocol.io

8. **ZIM Files** - Wikipedia offline archives
   - https://openzim.org

### Documentation

- [Developer Guide](./DEVELOPER.md)
- [Developer Guide (Arabic)](./DEVELOPER_AR.md)
- [User Guide](./USER.md)
- [User Guide (Arabic)](./USER_AR.md)
- [Configuration Reference](./CONFIG.md)
- [API Documentation](./API.md)

---

**This report was prepared for the JOYS 2026 Competition - T323**

**Developed by AIOL**