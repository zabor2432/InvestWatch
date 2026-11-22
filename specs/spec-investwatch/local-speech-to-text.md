# Technical Specification: Local Speech-to-Text with OpenAI Whisper

## 1. Objective

Implement a local speech-to-text solution using Whisper models available through Hugging Face.

The solution should support:
- Automatic Speech Recognition (ASR).
- Polish-language transcription.
- Local inference on macOS.
- Audio files longer than 30 seconds.
- Timestamped transcription segments.

Two model options should be available:

| Model | Size | Expected quality |
|---|---:|---|
| `openai/whisper-large-v3-turbo` | ~809M parameters | Recommended – better transcription quality |
| `bardsai/whisper-small-pl` | ~244M parameters | Lightweight alternative – lower transcription quality |

The smaller Polish-specific model is an option for machines with limited memory or computational resources. However, its transcription quality is noticeably worse in the example below.

## 2. Technology Stack

- Python 3.10+
- PyTorch
- Hugging Face Transformers
- Hugging Face Hub
- Accelerate
- FFmpeg

Use Apple's Metal Performance Shaders (MPS) backend when available. Otherwise, fall back to CPU.

## 3. Environment Setup

Create an isolated Python environment:

```bash
mkdir whisper-transcription
cd whisper-transcription

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install torch transformers accelerate
```

Install FFmpeg:

```bash
brew install ffmpeg
```

Verify the installation:

```bash
ffmpeg -version
```

## 4. Available Models

### Option A: Recommended – OpenAI Whisper Large V3 Turbo

Hugging Face repository:

https://huggingface.co/openai/whisper-large-v3-turbo

- Approximately 809M parameters.
- Multilingual model with Polish-language support.
- Better transcription quality in the comparison below.
- Requires more memory and computational resources than Whisper Small.

```python
MODEL_ID = "openai/whisper-large-v3-turbo"
```

### Option B: Lightweight – Whisper Small Polish

Hugging Face repository:

https://huggingface.co/bardsai/whisper-small-pl

- Approximately 244M parameters.
- Fine-tuned for Polish transcription.
- Lower computational requirements.
- Less accurate transcription in the example below, particularly with names, punctuation, and less clearly articulated speech.

```python
MODEL_ID = "bardsai/whisper-small-pl"
```

**Important:** The two models have different generation configurations. Load the model and processor from the same repository. The OpenAI model should use its own generation configuration. The smaller Polish model may require additional compatibility handling with newer Transformers versions.

## 5. Model Comparison – Real Audio Example

To demonstrate the difference in transcription quality, both models were tested on the same audio recording.

**Source video:** https://youtu.be/aqGSQ-8NGV0

The YouTube video was converted to MP3 and used as input for both models.

### Result from Whisper Small Polish

> Pieniądze są tylko narzędziem, ty decydujesz, czy będą pracować dla ciebie. Dobra robota! Dzięki Zlatan i Dajson inwestowanie, dodbanie o swoją przyszłość. Szanuję to, zrobimy sobie selfie? Bo to, co robisz dzisiaj, pływa na to, gdzie będziesz jutro.Dysyplina... Lo wieta... Tak robią nowocześni ludzie, inwestują... I mają prawo być z tego dumii... Powinni być, bo ich pieniądze pracują w XTB. XTB tu pracują twoje pieniądze. Uważaj, inwestowanie wiąże się z ryzykiem utraty środków i może nie być dla ciebie odpowiedni.

### Result from OpenAI Whisper Large V3 Turbo

> Pieniądze są tylko narzędziem. Ty decydujesz, czy będą pracować dla Ciebie. Dobra robota. Dzięki z latem. I Tyson. Inwestowanie to dbanie o swoją przyszłość. Szanuję to. Zrobimy sobie selfie? Bo to, co robisz dzisiaj, wpływa na to, gdzie będziesz jutro. Dyscyplina. Lubię to. Tak robią nowocześni ludzie. Inwestują. I mają prawo być z tego dumni. Powinni być, bo ich pieniądze pracują w XTB. XTB. Tu pracują Twoje pieniądze. Uważaj. Inwestowanie wiąże się z ryzykiem utraty środków i może nie być dla Ciebie odpowiednie.

### Observations

The OpenAI model produces a noticeably more readable result in this example:

- Better sentence segmentation and punctuation.
- Fewer spelling and word-recognition errors.
- More coherent transcription of conversational speech.
- Better preservation of the overall meaning.

Both models still make mistakes, particularly with proper names. Whisper Large V3 Turbo is not a perfect transcription system, and results should be reviewed when high accuracy is required.

**Recommendation:** Use `openai/whisper-large-v3-turbo` as the default model. Keep `bardsai/whisper-small-pl` as an optional lightweight alternative.

## 6. Model Initialization

Select the model through a configuration variable:

```python
MODEL_ID = "openai/whisper-large-v3-turbo"
```

Configure the device:

```python
import torch

device = "mps" if torch.backends.mps.is_available() else "cpu"

dtype = (
    torch.float16
    if device == "mps"
    else torch.float32
)
```

Load the model and processor:

```python
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    MODEL_ID,
    torch_dtype=dtype,
    low_cpu_mem_usage=True,
    use_safetensors=True,
).to(device)

processor = AutoProcessor.from_pretrained(MODEL_ID)
```

For the OpenAI model, use the generation configuration included in its repository. For the Polish Small model, check compatibility with the installed Transformers version before using the same initialization code.

## 7. Transcription Implementation

Create a Hugging Face ASR pipeline:

```python
from transformers import pipeline

asr = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=dtype,
    device=device,
)
```

Implement transcription:

```python
def transcribe(audio_path: str) -> dict:
    return asr(
        audio_path,
        return_timestamps=True,
        generate_kwargs={
            "language": "polish",
            "task": "transcribe",
        },
    )
```

The implementation must support audio longer than 30 seconds. Use `return_timestamps=True` to enable long-form transcription and timestamped chunks.

## 8. Expected Output

The transcription function should return:

```python
{
    "text": "Przykładowy tekst transkrypcji.",
    "chunks": [
        {
            "timestamp": (0.0, 3.5),
            "text": "Przykładowy tekst"
        },
        {
            "timestamp": (3.5, 6.2),
            "text": "transkrypcji."
        }
    ]
}
```

The application should expose:
- Full transcription text.
- Individual timestamped segments.
- Original audio filename.
- Transcription execution status and errors.

## 9. Requirements and Constraints

1. All inference must run locally.
2. No external transcription API should be used.
3. Polish must be explicitly selected as the transcription language.
4. Support audio files longer than 30 seconds.
5. Use MPS when available and CPU otherwise.
6. Load the model and processor from the same repository.
7. Handle model-loading and audio-processing errors.
8. Initialize the model once and reuse it for subsequent requests.
9. Keep model initialization separate from the transcription function.
10. Allow switching between the two models through configuration.
11. Do not modify generation settings unless a concrete compatibility issue requires it.

## 10. Validation

Test both models using the same audio recordings:

- Short Polish recording (under 30 seconds).
- Longer Polish recording (over 30 seconds).
- Recording with pauses and multiple speakers.
- Recording with background noise.

Compare transcription readability, word-recognition accuracy, punctuation, and processing time.

Verify that:
- Polish transcription works correctly.
- Timestamped segments are returned.
- Long recordings are processed without the 30-second limitation.
- The application can run offline after the models have been downloaded and cached.

## 11. Execution

Run the application inside the activated virtual environment:

```bash
python transcribe.py
```

The model should be initialized once, followed by transcription of the configured audio file.

## 12. Additional Notes

- The first execution requires an internet connection to download the selected model.
- Subsequent executions can use the local Hugging Face cache.
- FFmpeg should be available for decoding and converting audio formats.
- Whisper Large V3 Turbo requires more memory than Whisper Small.
- MPS performance and supported operations depend on Mac hardware and PyTorch version.
- If MPS produces unsupported-operation errors, retry using CPU.
- Transcription quality depends on audio quality, accents, background noise, and speaker characteristics.