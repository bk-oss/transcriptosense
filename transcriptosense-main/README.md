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

# 5. Run the REST API locally
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# 6. Test the health endpoint
curl http://127.0.0.1:8000/health

# 7. Run the pipeline on a test file
python src/ingestion/preprocess.py --input data/raw/test.wav

# 8. For GPU-heavy ASR / diarization → open notebooks/colab_pipeline.ipynb in Google Colab
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

## Translation backend (local defaults)

- By default the project prefers a local Ollama instance for translation and NLP tasks (faster, private, no external API keys).
- To use Ollama, run your local Ollama daemon and ensure the `mistral:latest` model is available. The API is expected at `http://localhost:11434`.
- Quick test (from project root):

	PowerShell:
	```powershell
	python scripts\ollama_generate_test.py
	```

- If you don't want to use Ollama (for example to test the offline Argos fallback), set the environment variable `OLLAMA_DISABLED=1` before running tests or the API. Example (PowerShell):

	```powershell
	$env:OLLAMA_DISABLED = '1'
	python scripts\run_translate_local.py
	```

- Notes:
	- If Ollama is not available, the service will attempt Argos Translate (offline) if models are installed, then Google/Libre web translators as fallbacks. Network SSL issues may prevent web translators from working in some environments.
	- To enable Argos offline translation, install `argostranslate` and the desired model package (scripts/setup_argos.py and scripts/install_argos_en_fr.py are provided to help).
	- If you see SSL certificate verification errors (e.g. "unable to get local issuer certificate" or `SSLCertVerificationError`), fix by pointing Python/requests/httpx to the certifi CA bundle:

		PowerShell (current session):
		```powershell
		$env:SSL_CERT_FILE = (python -c "import certifi; print(certifi.where())")
		$env:REQUESTS_CA_BUNDLE = (python -c "import certifi; print(certifi.where())")
		```

		To persist across sessions (Windows):
		```powershell
		setx SSL_CERT_FILE "$(python -c \"import certifi; print(certifi.where())\")"
		setx REQUESTS_CA_BUNDLE "$(python -c \"import certifi; print(certifi.where())\")"
		```

		After setting these, re-run the Argos setup or your translation test.
