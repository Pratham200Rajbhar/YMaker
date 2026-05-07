# NVIDIA Magpie TTS — Hindi via NIM API (gRPC)

## Prerequisites

- Python 3.8+
- NVIDIA API Key from [build.nvidia.com](https://build.nvidia.com)

## Installation

```bash
pip install -U nvidia-riva-client
git clone https://github.com/nvidia-riva/python-clients.git
cd python-clients
```

## Configuration

| Parameter | Value |
|---|---|
| Server | `grpc.nvcf.nvidia.com:443` |
| SSL | Required (`--use-ssl`) |
| Function ID | `877104f7-e885-42b9-8de8-f6e4c6303969` |
| Language Code | `hi-IN` |

## Set API Key

```bash
export NVIDIA_API_KEY="nvapi-xxxxxxxxxxxxxxxxxxxx"
```

## Run Hindi TTS

```bash
python scripts/tts/talk.py \
  --server grpc.nvcf.nvidia.com:443 --use-ssl \
  --metadata function-id "877104f7-e885-42b9-8de8-f6e4c6303969" \
  --metadata authorization "Bearer $NVIDIA_API_KEY" \
  --language-code hi-IN \
  --text "नमस्ते, यह एनवीडिया का टेक्स्ट टू स्पीच मॉडल है।" \
  --voice "Magpie-Multilingual.HI-IN.Aria" \
  --output hindi_output.wav
```

## Available Hindi Voices

| Voice String | Speaker |
|---|---|
| `Magpie-Multilingual.HI-IN.John` | John |
| `Magpie-Multilingual.HI-IN.Sofia` | Sofia |
| `Magpie-Multilingual.HI-IN.Aria` | Aria |
| `Magpie-Multilingual.HI-IN.Jason` | Jason |
| `Magpie-Multilingual.HI-IN.Leo` | Leo |

## List All Available Voices

```bash
python scripts/tts/talk.py \
  --server grpc.nvcf.nvidia.com:443 --use-ssl \
  --metadata function-id "877104f7-e885-42b9-8de8-f6e4c6303969" \
  --metadata authorization "Bearer $NVIDIA_API_KEY" \
  --list-voices
```

## Python gRPC Client (Programmatic)

```python
import riva.client

auth = riva.client.Auth(
    uri="grpc.nvcf.nvidia.com:443",
    use_ssl=True,
    metadata_args=[
        ["function-id", "877104f7-e885-42b9-8de8-f6e4c6303969"],
        ["authorization", f"Bearer {NVIDIA_API_KEY}"]
    ]
)

tts_client = riva.client.SpeechSynthesisService(auth)

response = tts_client.synthesize(
    text="नमस्ते, यह एनवीडिया का टेक्स्ट टू स्पीच मॉडल है।",
    voice_name="Magpie-Multilingual.HI-IN.Aria",
    language_code="hi-IN",
    encoding=riva.client.AudioEncoding.LINEAR_PCM,
    sample_rate_hz=22050,
)

# Save to WAV
import soundfile as sf
import numpy as np

audio = np.frombuffer(response.audio, dtype=np.int16)
sf.write("hindi_output.wav", audio, samplerate=22050)
print("Saved: hindi_output.wav")
```

## Notes

- Output format is **LINEAR PCM WAV** at **22050 Hz**
- Max audio generation: **~20 seconds** per request
- Text Normalization (TN) is **supported** for Hindi via the NIM cloud API
- No GPU required — inference runs on NVIDIA cloud infrastructure

## References

- [NIM API Page](https://build.nvidia.com/nvidia/magpie-tts-multilingual/api)
- [Riva Python Clients — GitHub](https://github.com/nvidia-riva/python-clients)
- [Riva TTS Proto Docs](https://docs.nvidia.com/nim/riva/tts/latest/protos.html)