# TranscriptoSense
**Transcription automatique & analyse sémantique multilingue (FR / AR / Darija)**

---

## Project Structure

```
transcriptosense/
├── data/
│   ├── raw/            # Original audio files (.wav, .mp3, .m4a)
│   ├── processed/      # Resampled / denoised audio (16kHz mono WAV)
│   └── annotations/    # Manual segment labels, role annotations
│
├── src/
│   ├── ingestion/      # Audio loading, VAD, preprocessing
│   ├── asr/            # Whisper transcription + timestamps
│   ├── diarization/    # pyannote speaker diarization
│   ├── nlp/            # NER, keywords, topics, sentiment, action items
│   ├── synthesis/      # Summarization, meeting minutes generation
│   ├── api/            # FastAPI endpoints
│   └── ui/             # Streamlit interface
│
├── models/             # Downloaded / fine-tuned model weights
├── outputs/
│   ├── transcripts/    # Raw + diarized transcripts (JSON)
│   ├── summaries/      # Meeting minutes (JSON/DOCX/PDF)
│   └── exports/        # CSV tasks, ICS calendar, citations
│
├── notebooks/          # Colab notebooks for GPU-heavy steps
├── tests/              # Unit + integration tests
├── docs/               # Model card, data card, annotation protocol
│
├── config.py           # Central configuration (paths, model names, langs)
├── requirements.txt    # Local CPU dependencies
├── requirements_gpu.txt # GPU / Colab dependencies
├── setup_check.py      # Environment health check script
└── README.md
```

## Complexity Tiers

| Tier | What it covers |
|---|---|
| 🥉 Bronze | Whisper ASR + simple keyword/decision rules + extractive summary |
| 🥈 Silver | Diarization + NER/embeddings + topic segmentation + query-focused summary |
| 🥇 Gold | SRL/SVO + fine-tuned action item classifier + ASR calibration |
| 💎 Platinum | Streaming, drift detection, conformal prediction, continual learning |

## Quick Start

```bash
# 1. Clone / open the project folder
cd transcriptosense

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install local dependencies
pip install -r requirements.txt

# 4. Check everything is installed correctly
python setup_check.py

# 5. Run the pipeline on a test file
python src/ingestion/preprocess.py --input data/raw/test.wav

# 6. For GPU-heavy ASR / diarization → open notebooks/colab_pipeline.ipynb in Google Colab
```

## Languages Supported
- French (FR)
- Arabic (AR — Modern Standard)
- Darija (Moroccan Arabic dialect)
- Code-switching mixtures of the above

## Evaluation Metrics
- **ASR**: WER / CER per speaker and per language
- **Diarization**: DER / JER
- **Topic segmentation**: Pk, WindowDiff
- **NLP**: F1 NER, F1 action items, ROUGE / BERTScore for summaries
