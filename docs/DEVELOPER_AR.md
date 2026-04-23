# دليل المطور

## العربية

### حول AIOL

> **AIOL** (Artificial Intelligence Open Lab) - مشروع طوّر لمسابقة JOYS T323.

---

## جدول المحتويات

1. [نظرة عامة على البنية](#نظرة-عامة-على-البنية)
2. [مكونات النظام](#مكونات-النظام)
3. [مرجع API](#مرجع-api)
4. [تدفق خط المعالجة](#تدفق-خط-المعالجة)
5. [خادم MCP والأدوات](#خادم-mcp-والأدوات)
6. [اكتشاف كلمة التنبيه](#اكتشاف-كلمة-التنبيه)
7. [مرجع التكوين](#مرجع-التكوين)
8. [تشغيل النظام](#تشغيل-النظام)
9. [الاختبار](#الاختبار)
10. [التوثيق ذي الصلة](#التوثيق-ذو-الصلة)

---

## نظرة عامة على البنية

يتبع مساعد الصوت حكيم خط معالجة تسلسلي STT → LLM → TTS:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   إدخال      │───▶│    تحويل     │───▶│    النموذج   │───▶│   تحويل      │
│   الصوت      │    │   الكلام    │    │   اللغوي     │    │   النص       │
│  (كلمة       │    │   إلى نص    │    │   الطبي      │    │   إلى صوت    │
│   التنبيه)   │    │   (Whisper) │    │   (MCP)      │    │   (Piper)    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                           │                    │                    │
                           └────────────────────┴────────────────────┘
                                                 │
                                          ┌──────┴──────┐
                                          │  FastAPI   │
                                          │   :8003    │
                                          └────────────┘
```

### تفصيل المكونات

| المكون | التقنية | الغرض |
|--------|---------|--------|
| **كلمة التنبيه** | openWakeWord (نموذج "حكيم" المخصص) | الاستماع لعبارة التفعيل |
| **تحويل الكلام إلى نص** | Faster-Whisper | تحويل الكلام إلى نص |
| **النموذج اللغوي** | MedGemma (معدّل طبي) عبر llama.cpp | معالجة الاستفسارات بالمعرفة الطبية |
| **MCP** | بروتوكول سياق النموذج + ملفات ZIM | الوصول لموسوعة ويكيبيديا دون إنترنت |
| **تحويل النص إلى كلام** | Piper (الإنجليزية + العربية) | تحويل النص إلى صوت |

---

## مكونات النظام

### 1. عميل كلمة التنبيه (`wake_word_client.py`)

يستمع لكلمة "حكيم" باستخدام نماذج ONNX:

- يستخدم مكتبة `openwakeword` للاستدلال
- WebRTC VAD لكشف الصمت
- يسجل كلام المستخدم حتى يتم اكتشاف الصمت
- يرسل الصوت إلى API خط المعالجة
- يشغّل استجابة TTS عبر PyAudio

```python
# المعلمات الرئيسية
python wake_word_client.py \
    --api-url http://localhost:8003/process-audio \
    --model-path models/Hakeem/Hakeem.onnx \
    --threshold 0.5
```

### 2. خادم خط المعالجة (`pipeline.py`)

خادم FastAPI الذي يتعامل مع تدفق STT → LLM → TTS:

- **بدون Streaming**: `/process-audio` - إرجاع ملف صوتي كامل
- **Streaming**: `/process-audio-stream` - إخراج TTS المتدفق

### 3. خادم MCP (`MCP-servers/Open-zim/`)

يوفر قاعدة معرفة دون اتصال باستخدام ملفات ZIM (نسخ ويكيبيديا):

- يعمل كخادم FastMCP منفصل
- الأدوات: `search`, `get_article`, `list_articles`, `get_suggestions`
- يتصل بخط المعالجة الرئيسي عبر SSE (أحداث إرسال الخادم)

---

## مرجع API

### نقاط النهاية

| نقطة النهاية | الطريقة | الوصف |
|--------------|---------|-------|
| `/health` | GET | فحص الصحة - إرجاع حالة النماذج |
| `/process-audio` | POST | معالجة الصوت → استجابة صوتية (بدون streaming) |
| `/process-audio-stream` | POST | معالجة الصوت → استجابة صوتية متدفقة |

### الحصول على /health

**الاستجابة:**
```json
{
  "status": "healthy",
  "device": "cpu",
  "models_loaded": {
    "stt": true,
    "tts_en": true,
    "tts_ar": true
  }
}
```

### نشر /process-audio

**الطلب:**
- نوع المحتوى: `multipart/form-data`
- الجسم: `file` - ملف صوتي (wav, mp3, ogg, flac)

**الاستجابة:**
- نوع المحتوى: `audio/wav`
- الجسم: ملف صوتي

**مثال:**
```bash
curl -X POST http://localhost:8003/process-audio \
  -F "file=@audio.wav" \
  --output response.wav
```

### نشر /process-audio-stream

مثل السابق لكن يقوم بتدفق صوت TTS في الوقت الفعلي.

---

## تدفق خط المعالجة

### الخطوة 1: تحويل الكلام إلى نص (STT)

```python
from faster_whisper import WhisperModel

whisper_model = WhisperModel("medium", device="auto", compute_type="int8")
segments, info = whisper_model.transcribe(
    audio_file,
    vad_filter=True,
    vad_parameters={"threshold": 0.5, "min_speech_duration_ms": 250}
)
text = " ".join(segment.text for segment in segments)
```

**الميزات الرئيسية:**
- كشف النشاط الصوتي (VAD)过滤 الكلام غير
- يتضمن كشف اللغة
- حجم الشعاع: 5 للدقة

### الخطوة 2: معالجة LLM مع MCP

```python
from src.mcp import MCPWrapper

mcp = MCPWrapper(
    llama_base_url="http://localhost:2312/v1",
    llama_model="medgemma",
    mcp_urls=["http://localhost:2527/sse"]
)
response = await mcp.run_query(user_text)
```

**النموذج الرئيسي: MedGemma**
- نموذج مضبوط للمجال الطبي من Google
- محسّن للأسئلة الطبية
- يعمل محلياً عبر llama.cpp (مكمّم للكفاءة)

**نتائج المعايير:**
| النموذج | الدقة | متوسط الوقت |
|---------|-------|-------------|
| **MedGemma** | النموذج المستهدف | - |
| Qwen3-4B | 25% | 1.4 ثانية MCQ / 10.6 ثانية توليدي |

**نظام LLM:**
> "أنت مساعد صوت موجز. قدم إجابات قصيرة وطبيعية. تجنب النص العريض أو قوائم markdown أو التفسيرات الطويلة ما لم يُطلب منك."

**حلقة الأدوات:** يمكن لـ LLM استدعاء أدوات MCP حتى 5 مرات لكل استعلام.

### الخطوة 3: تحويل النص إلى كلام (TTS)

```python
from piper import PiperVoice

voice = PiperVoice.load("en_GB-cori-high.onnx")
wav_buffer = voice.synthesize_wav(text)
```

**كشف اللغة:** يكتشف تلقائياً العربية مقابل الإنجليزية ويحدد الصوت المناسب.

---

## خادم MCP والأدوات

### الأدوات المتاحة

يوفر خادم MCP هذه الأدوات لـ LLM:

| الأداة | الوصف |
|--------|-------|
| `search` | بحث نص كامل في ملف ZIM |
| `get_article` | قراءة مقال بالمسار |
| `list_articles` | سرد جميع المدخلات |
| `get_metadata` | الحصول على بيانات ملف ZIM |
| `get_suggestions` | اقتراحات البحث |
| `list_zim_files` | سرد ملفات ZIM المتاحة |

### تشغيل خادم MCP

```bash
cd MCP-servers/Open-zim
docker-compose up --build
```

---

## اكتشاف كلمة التنبيه

### نموذج كلمة التنبيه المخصص

تم تدريب نموذج كلمة "حكيم" باستخدام openWakeWord:

1. **جمع الصوت**: تسجيل عينات متعددة للنطق "حكيم"
2. **التدريب**: استخدام خط تدريب openwakeword
3. **التصدير**: تنسيق ONNX للاستدلال الفعال

### موقع النموذج

```
models/
└── Hakeem/
    └── Hakeem.onnx    # نموذج كلمة التنبيه المخصص
```

---

## مرجع التكوين

### الإعدادات المسبقة

```yaml
preset: "default"  # أو "lightweight" أو "heavy"
```

| الإعداد | نموذج STT | الأصوات | الحساب | الأفضل لـ |
|---------|-----------|---------|--------|----------|
| `default` | whisper-medium | EN + AR | int8 | CPU/GPU جيد |
| `lightweight` | whisper-small | EN فقط | int8 | CPU ضعيف |
| `heavy` | whisper-large-v3 | EN + AR | float16 | GPU قوي |

---

## تشغيل النظام

### الخيار 1: Docker Compose (موصى به)

```bash
# 1. استنساخ المستودع
git clone https://github.com/2kfi/Hakeem.git
cd Hakeem

# 2. نسخ ملف الإعدادات
cp .env.example .env

# 3. البناء والتشغيل
docker-compose up --build

# 4. اختبار نقطة النهاية الصحية
curl http://localhost:8003/health
```

### الخيار 2: بدون Docker

```bash
pip install -r backend-requirements.txt
python pipeline.py
```

---

## الاختبار

```bash
curl http://localhost:8003/health
```

```bash
curl -X POST http://localhost:8003/process-audio \
  -F "file=@test_audio.wav" \
  --output response.wav
```

---

## التوثيق ذي الصلة

- [دليل المطور](./DEVELOPER.md) - Developer Guide
- [دليل المستخدم](./USER.md) - توثيق المستخدم النهائي
- [دليل المستخدم (العربية)](./USER_AR.md) - دليل المستخدم
- [تقرير الحكام](./JUDGES.md) - التقرير التقني للمسابقة
- [تقرير الحكام (العربية)](./JUDGES_AR.md) - تقرير الحكام
- [مرجع API](./API.md) - توثيق API التفصيلي
- [التكوين](./CONFIG.md) - خيارات التكوين