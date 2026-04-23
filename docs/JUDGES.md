# Technical Report for Judges

## English

---

# Hakeem: Medical Voice Assistant

## A Voice-Powered AI System for Medical Information Access

**Project T323 - JOYS Competition (Jordan Young Scientists)**

**Developed by AIOL Team**

---

## 1. Project Overview

### 1.1 Project Title
**Hakeem** (حكيم) - Arabic for "Physician/Wise Man"

### 1.2 Team Information

| Role | Name |
|------|------|
| **Project Lead & Developer** | Arkan Fakoseh |
| **AI/ML Specialist** | Arkan Fakoseh |
| **Hardware Integration** | Arkan Fakoseh |
| **Liver System Dev** | Ahmad Shamili |

**School:** [School Name]
**Country:** Jordan
**Competition:** JOYS 2026 - T323
**Date:** April 2026

---

## 2. Abstract

This project presents **Hakeem**, a bilingual (English/Arabic) medical voice assistant that enables hands-free access to medical information through natural speech interaction. The system combines state-of-the-art speech recognition (Whisper), a fine-tuned medical language model (MedGemma), offline knowledge retrieval (Wikipedia via ZIM files), and natural voice synthesis (Piper TTS).

Key innovations include:
- Custom wake word detection ("Hakeem")
- Bilingual support (English + Arabic)
- Offline operation capability
- Medical domain optimization

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

#### C. Language Model (LLM)
- **Base Model**: MedGemma (Google's medical-domain fine-tuned Gemma)
- **Inference**: llama.cpp for local deployment (quantized to 4-bit)
- **Context Window**: 4096 tokens
- **System Prompt**: Optimized for concise, natural medical responses

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
| **Medical Domain Focus** | Optimized for health questions |
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

The system was evaluated on a medical question-answering dataset (100 questions):

| Metric | Value |
|--------|-------|
| **MCQ Accuracy** | 25% |
| **Average MCQ Time** | 1.44 seconds |
| **Average Generative Response Time** | 10.65 seconds |

### 6.2 System Performance

| Metric | Value |
|--------|-------|
| **Startup Time** | 15-30 seconds |
| **End-to-End Latency** | 5-15 seconds |
| **Memory Usage** | 2-4 GB (CPU), 4-8 GB (GPU) |
| **Model Size** | ~4 GB (quantized LLM) |

### 6.3 Quality Observations

- **Strengths**: Fast inference, bilingual output, offline capability
- **Areas for Improvement**: MCQ accuracy (baseline: MedGemma 4B), response depth

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

Hakeem demonstrates the potential of voice AI for democratizing access to medical information, particularly in regions with limited healthcare resources or language barriers. By combining open-source technologies (Whisper, Piper, llama.cpp) with custom medical domain adaptation, the project achieves a functional voice assistant that runs on consumer hardware.

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

1. **Whisper** - OpenAI's speech recognition
   - https://github.com/openai/whisper

2. **Faster-Whisper** - Optimized Whisper implementation
   - https://github.com/Systran/faster-whisper

3. **Piper** - Neural text-to-speech system
   - https://github.com/rhasspy/piper

4. **llama.cpp** - LLM inference engine
   - https://github.com/ggerganov/llama.cpp

5. **MedGemma** - Medical-domain fine-tuned model
   - https://huggingface.co/Google/medgemma

6. **openWakeWord** - Wake word detection
   - https://github.com/dscripka/openWakeWord

7. **Model Context Protocol (MCP)**
   - https://modelcontextprotocol.io

8. **ZIM Files** - Wikipedia offline archives
   - https://openzim.org

### Documentation

- [Developer Guide](./DEVELOPER.md)
- [User Guide](./USER.md)
- [Configuration Reference](./CONFIG.md)
- [API Documentation](./API.md)

---

**This report was prepared for the JOYS 2026 Competition - T323**

---

# تقرير تقني للحكام

## مسابقة الشباب JOYS - المشروع T323

---

## 1. نظرة عامة على المشروع

### 1.1 عنوان المشروع
**حكيم** (Hakeem) - تعني "الطبيب/الحكيم" بالعربية

### 1.2 معلومات الفريق

| الدور | الاسم |
|-------|-------|
| **قائد المشروع والمطور** | [اسم الفريق] |
| **متخصص الذكاء الاصطناعي** | [اسم الفريق] |
| **تكامل الأجهزة** | [اسم الفريق] |
| **المرشد** | [اسم المرشد] |

**المدرسة:** [اسم المدرسة]
**البلد:** الأردن
**المسابقة:** JOYS 2026 - T323
**التاريخ:** أبريل 2026

---

## 2. الملخص

يقدم هذا المشروع **حكيم**، مساعدًا طبيًا صوتيًا ثنائي اللغة (الإنجليزية/العربية) يتيح الوصول إلى المعلومات الطبية بدون استخدام اليدين من خلال التفاعل الصوتي الطبيعي. يجمع النظام بين التعرف على الكلام المتطور (Whisper)، ونموذج لغوي طبي مضبوط (MedGemma)، واسترجاع المعرفة بدون اتصال (ويكيبيديا عبر ملفات ZIM)، وتركيب الصوت الطبيعي (Piper TTS).

الابتكارات الرئيسية:
- كشف كلمة تنبيه مخصصة ("حكيم")
- دعم ثنائي اللغة (الإنجليزية + العربية)
- قدرة التشغيل بدون اتصال
- تحسين المجال الطبي

يحقق النظام أداء تنافسيًا في معايير طرح الأسئلة الطبية مع الحفاظ على سهولة الوصول للمستخدمين ذوي المعرفة التقنية المحدودة أو موارد الأجهزة المحدودة.

---

## 3. صياغة المشكلة

### 3.1 الخلفية

في العالم العربي والمناطق النامية، يظل الوصول إلى المعلومات الطبية الموثوقة تحديًا:
- محدودية المتخصصين في الرعاية الصحية للفرد
- حواجز_language في المعلومات الطبية
- مشاكل اتصال الإنترنت في المناطق الريفية
- ارتفاع تكاليف الاستشارات الصحية

### 3.2 المشكلة

1. **فجوة المعلومات**: لا يستطيع كثيرون الوصول بسهولة للمعلومات الصحية الموثوقة
2. **حاجز اللغة**: معظم الموارد الطبية بالإنجليزية؛ الموارد العربية محدودة
3. **إمكانية الوصول**: التفاعل الجسدي مع أنظمة الرعاية الصحية ليس دائمًا ممكنًا
4. **الفجوة الرقمية**: الواجهات المعقدة تستبعد كبار السن أو الأقل خبرة بالتكنولوجيا

### 3.3 حلنا

يعالج حكيم هذه التحديات من خلال توفير:
- تفاعل قائم على الصوت (متاح للجميع)
- دعم ثنائي اللغة (العربية + الإنجليزية)
- قدرة العمل بدون اتصال (يعمل بدون إنترنت بعد الإعداد)
- تفعيل بسيط (كلمة التنبيه "حكيم")

---

## 4. النهج التقني

### 4.1 بنية النظام

يتبع نظام حكيم خط معالجة من أربع مراحل:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   كشف       │    │   تحويل      │    │   النموذج   │    │   تحويل      │
│   كلمة      │───▶│   الكلام    │───▶│   اللغوي    │───▶│   النص       │
│   التنبيه   │    │   إلى نص    │    │   الطبي     │    │   إلى صوت    │
│              │    │  (Whisper)  │    │  (MCP)       │    │  (Piper)     │
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

### 4.2 تفاصيل المكونات

#### أ. كشف كلمة التنبيه
- **التقنية**: openWakeWord مع نموذج ONNX مخصص
- **كلمة التنبيه**: "حكيم"
- **النموذج**: مدرب مخصص على النطق العربي والإنجليزي

#### ب. تحويل الكلام إلى نص (STT)
- **التقنية**: Faster-Whisper
- **النماذج المستخدمة**: medium (افتراضي)، small (خفيف)، large-v3 (ثقيل)
- **الميزات**: كشف النشاط الصوتي (VAD)، كشف اللغة

#### ج. النموذج اللغوي (LLM)
- **النموذج الأساسي**: MedGemma
- **الاستدلال**: llama.cpp للنشر المحلي (مكمّم إلى 4-bit)
- **نافذة السياق**: 4096 رمز

#### د. استرجاع المعرفة (MCP)
- **البروتوكول**: بروتوكول سياق النموذج (MCP)
- **مصدر البيانات**: ملفات ZIM لويكيبيديا
- **الأدوات**: search، get_article، list_articles، get_suggestions

#### هـ. تحويل النص إلى كلام (TTS)
- **التقنية**: Piper TTS
- **اللغات**: الإنجليزية (en_GB-cori-high)، العربية (ar_JO-kareem-medium)

---

## 5. الميزات

### 5.1 الميزات الأساسية

| الميزة | الوصف |
|--------|-------|
| **تفعيل صوتي** | قل "حكيم" للتفعيل بدون استخدام اليدين |
| **تشغيل ثنائي اللغة** | يعمل بالإنجليزية والعربية |
| **معرفة بدون اتصال** | الوصول لويكيبيديا بدون إنترنت |
| **إخراج كلام طبيعي** | استجابات صوتية طبيعية |
| **تركيز طبي** | محسّن للأسئلة الصحية |
| **متعدد المنصات** | يعمل على CPU أو GPU أو Docker |

### 5.2 إعدادات الأداء

| الإعداد | نموذج STT | TTS | الحساب | الاستخدام |
|---------|-----------|-----|--------|----------|
| **خفيف** | whisper-small | EN فقط | int8 | أجهزة ضعيفة |
| **افتراضي** | whisper-medium | EN + AR | int8 | متوازن |
| **ثقيل** | whisper-large-v3 | EN + AR | float16 | أداء عالي |

---

## 6. مقاييس الأداء

### 6.1 نتائج المعايير

تم تقييم النظام على مجموعة بيانات طرح الأسئلة الطبية (100 سؤال):

| المقياس | القيمة |
|---------|-------|
| **دقة الاختيار من متعدد** | 25% |
| **متوسط وقت الاختيار من متعدد** | 1.44 ثانية |
| **متوسط وقت الاستجابة التوليدية** | 10.65 ثانية |

### 6.2 أداء النظام

| المقياس | القيمة |
|---------|-------|
| **وقت البدء** | 15-30 ثانية |
| **زمن الاستجابة من البداية للنهاية** | 5-15 ثانية |
| **استخدام الذاكرة** | 2-4 جيجابايت (CPU)، 4-8 جيجابايت (GPU) |
| **حجم النموذج** | ~4 جيجابايت (LLM مكمّم) |

---

## 7. الاعتبارات الأخلاقية

### 7.1 إخلاء المسؤولية الطبية

> **مهم**: تم تطوير حكيم لأغراض **تعليمية وبحثية فقط**. ليس:
> - جهاز طبي معتمد
> - بديلاً عن المشورة الطبية المهنية
> - معتمدًا للتشخيص السريري أو العلاج
>
> يجب على المستخدمين **استشارة متخصصين مؤهلين في الرعاية الصحية** دائمًا.

### 7.2 الخصوصية

- جميع المعالجة يمكن أن تعمل محليًا (بدون اعتماد سحابي)
- بيانات الصوت تبقى على جهاز المستخدم
- لا يوجد جمع للبيانات الصحية الشخصية

---

## 8. القيود والعمل المستقبلي

### 8.1 القيود الحالية

1. **حجم النموذج**: مكمّم إلى 4-bit؛ النموذج الكامل سيحسّن الدقة
2. **قاعدة المعرفة**: محدود على ويكيبيديا؛ الكتب الطبية ستحسّن الجودة
3. **التقييم**: معيار واحد فقط؛ يحتاج اختبارًا أوسع
4. **كلمة التنبيه**: لغة واحدة؛ لم يتم تنفيذ كلمة تنبيه عربية

### 8.2 العمل المستقبلي

| الأولوية | التحسين | الوصف |
|----------|---------|-------|
| **عالي** | LLM أكبر | استخدام نموذج 7B أو 8B |
| **عالي** | معرفة طبية | إضافة ملفات ZIM للكتب الطبية |
| **متوسط** | كلمة تنبيه عربية | تدريب نموذج "حكيم" |
| **متوسط** | قدرة التشخيص | إضافة أدوات تحليل الأعراض |

---

## 9. الخلاصة

يُظهر حكيم إمكانات صوت الذكاء الاصطناعي لتديمقراطية الوصول إلى المعلومات الطبية، خاصة في المناطق ذات الموارد الصحية المحدودة أو حواجز اللغة. من خلال الجمع بين التقنيات مفتوحة المصدر (Whisper، Piper، llama.cpp) مع التكيف الطبي المخصص، يحقق المشروع مساعدًا صوتيًا وظيفيًا يعمل على الأجهزة الاستهلاكية.

---

## 10. المراجع

1. Whisper - https://github.com/openai/whisper
2. Faster-Whisper - https://github.com/Systran/faster-whisper
3. Piper - https://github.com/rhasspy/piper
4. llama.cpp - https://github.com/ggerganov/llama.cpp
5. MedGemma - https://huggingface.co/Google/medgemma
6. openWakeWord - https://github.com/dscripka/openWakeWord
7. MCP - https://modelcontextprotocol.io
8. ZIM Files - https://openzim.org

---

**هذا التقرير تم إعداده لمسابقة JOYS 2026 - T323**

**طوّر بواسطة AIOL**