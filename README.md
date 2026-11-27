# TRACE – Offline Speech-to-Text and Meeting Report System

**TRACE (Transcription, Recognition and Acoustic Context Engine)** is an offline AI-powered system that converts English speech into structured meeting reports. It is designed to automate meeting documentation by combining speech recognition with natural language processing (NLP).

The system consists of two main modules:

- **Module 1 – Automatic Speech Recognition (ASR):** Converts spoken English audio into text using a custom CNN-BiGRU-CTC acoustic model developed and trained from scratch in PyTorch.
- **Module 2 – Natural Language Processing (NLP):** Processes the generated transcript using rule-based extraction and a TF-IDF + Logistic Regression classifier to identify summaries, decisions, action items, deadlines, important dates, people, discussion points, and keywords.

TRACE operates locally without relying on cloud-based speech recognition APIs or pretrained speech models. It provides an integrated Gradio interface and supports exporting structured meeting reports in PDF and DOCX formats.

---

## 1. Features

### Module 1 – Automatic Speech Recognition (ASR)

- Offline English speech recognition.
- Custom CNN + 5-layer Bidirectional GRU (BiGRU) architecture.
- Approximately 16.4 million model parameters.
- Developed and trained from scratch using PyTorch.
- No pretrained speech-recognition models or external speech APIs.
- 80-band Log-Mel spectrogram feature extraction.
- Audio preprocessing, mono conversion, and resampling to 16 kHz.
- Connectionist Temporal Classification (CTC) loss.
- Greedy CTC decoding for transcript generation.
- Training and validation using LibriSpeech.
- Word Error Rate (WER) and Character Error Rate (CER) evaluation.
- Saved model checkpoints for local inference.

### Module 2 – Natural Language Processing (NLP)

- Transcript preprocessing and sentence segmentation.
- Rule-based extraction of meeting information.
- TF-IDF feature extraction.
- Logistic Regression sentence classification.
- Identification of action items and decisions.
- Extraction of deadlines and important dates.
- Identification of people and task owners.
- Extractive meeting summarization.
- Discussion-point identification.
- Keyword extraction.
- Confidence-based evidence classification.
- Structured meeting report generation.
- PDF and DOCX report export.

### Application Features

- Local Gradio web interface.
- Audio upload and microphone recording.
- Generated English transcript.
- Transcript-based meeting analysis.
- Structured meeting report generation.
- PDF and DOCX export.
- Independent execution of the ASR and NLP modules.

---

## 2. System Architecture

TRACE follows a modular architecture consisting of two connected components.

### Module 1: ASR Processing Pipeline

The ASR module converts audio into an English transcript.

1. Audio input through file upload or microphone recording.
2. Audio preprocessing and resampling to 16 kHz.
3. Conversion into 80-band Log-Mel spectrogram features.
4. Feature extraction through two CNN layers.
5. Sequential processing through five bidirectional GRU layers.
6. Character probability generation through a linear layer.
7. Greedy CTC decoding to produce the final transcript.

### Module 2: NLP Processing Pipeline

The NLP module takes the generated transcript and transforms it into a structured meeting report.

1. Transcript preprocessing and sentence segmentation.
2. Rule-based extraction of relevant meeting information.
3. TF-IDF feature extraction and Logistic Regression classification.
4. Identification of meeting information and supporting sentences.
5. Extractive summary generation.
6. Structured report construction.
7. PDF and DOCX export.

### Integrated Workflow

```text
             AUDIO INPUT
           (Upload / Record)
                   |
                   v
        MODULE 1: ASR
                   |
          Audio Preprocessing
           (16 kHz, Mono)
                   |
                   v
         Log-Mel Features
           (80 Bands)
                   |
                   v
              CNN
           (2 Layers)
                   |
                   v
              BiGRU
          (5 Layers)
                   |
                   v
          Linear + CTC
                   |
                   v
           Greedy Decoder
                   |
                   v
          ENGLISH TRANSCRIPT
                   |
                   v
        MODULE 2: NLP
                   |
          Text Preprocessing
                   |
             +-----+-----+
             |           |
             v           v
        Rule-Based    TF-IDF +
        Extraction   Logistic Regression
             |           |
             +-----+-----+
                   |
                   v
             Report Builder
                   |
                   v
          STRUCTURED REPORT
                   |
             +-----+-----+
             |           |
             v           v
           PDF         DOCX
```

Both modules can also operate independently. The integrated workflow passes the transcript produced by the ASR module directly to the NLP module.

---

## 3. Model Architecture and Training

The ASR model, named `DeepSpeechLite` in the implementation, is a custom neural network developed from scratch.

| Component | Configuration |
|---|---|
| Input sample rate | 16 kHz |
| Input features | 80 Log-Mel bands |
| CNN | 2 convolutional layers |
| CNN channels | 32 |
| Activation | Hardtanh |
| Normalization | BatchNorm |
| Recurrent network | 5-layer BiGRU |
| Hidden size | 512 |
| Dropout | 0.1 |
| Output classes | 29 |
| Output activation | Log-Softmax |
| Loss function | CTC Loss |
| Optimizer | AdamW |
| Learning rate | 0.0003 |
| Weight decay | 0.00001 |
| Batch size | 2 |
| Gradient clipping | 5.0 |
| Random seed | 42 |
| Parameters | Approximately 16.4 million |

### Training Configuration

The model was trained using four different training subsets from LibriSpeech:

- 500 samples
- 1,500 samples
- 2,000 samples
- 4,000 samples

Each training experiment used one or two epochs, depending on the available computational resources.

The model uses:

- AdamW optimization.
- CTC loss with zero-infinity handling.
- Gradient clipping.
- StepLR learning-rate scheduling.
- Validation after each epoch.
- Best and latest checkpoint saving.
- Training history tracking.

The best checkpoint is selected based on validation WER.

---

## 4. Dataset

TRACE uses the **LibriSpeech ASR Corpus**, an English audiobook speech dataset.

Dataset source: https://www.openslr.org/12/

### ASR Dataset

| Dataset Split | Purpose |
|---|---|
| train-clean-100 | ASR training |
| dev-clean | Validation and demonstration |

Four training subsets were used in the experiments.

| Training Samples | Validation Samples |
|---:|---:|
| 500 | 100 |
| 1,500 | 300 |
| 2,000 | 300 |
| 4,000 | 500 |

Audio is processed as float32 waveforms at 16 kHz and converted into normalized 80-band Log-Mel spectrograms.

Text transcripts are lowercased and converted into a 29-symbol vocabulary consisting of:

- CTC blank symbol.
- Space.
- Apostrophe.
- Letters a–z.

**Dataset limitation:** The experiments used subsets of LibriSpeech rather than the complete corpus. No separate held-out test set was maintained; reported ASR results are validation results.

### NLP Dataset

The NLP sentence classifier uses project-labelled examples with four categories:

1. Action item
2. Decision
3. Discussion
4. Other

The NLP module was evaluated using 24 synthetic meeting transcripts with draft manual annotations.

The size of the classifier's training set was not recorded. The reference annotations have not been independently reviewed.

---

## 5. Experimental Results

### ASR Evaluation

The ASR module was evaluated using Word Error Rate (WER) and Character Error Rate (CER).

| Training Samples | Epochs | Training Loss | Validation Loss | WER | CER |
|---:|---:|---:|---:|---:|---:|
| Empty-output baseline | – | – | – | 1.0000 | 1.0000 |
| 500 | 2 | 2.7573 | 2.8702 | 1.0568 | 0.7462 |
| 1,500 | 2 | 2.4429 | 2.1810 | 1.0498 | 0.6257 |
| 2,000 | 2 | 2.3122 | 2.0380 | 1.0655 | 0.5989 |
| 4,000 | 1 | 2.1013 | 1.7998 | **0.9807** | **0.5539** |

The 4,000-sample experiment achieved the best results, with a validation WER of 0.9807 and CER of 0.5539.

It was the only experiment to achieve a WER below the empty-output baseline of 1.0.

Increasing the training data also reduced CER:

- 500 samples: 0.7462
- 1,500 samples: 0.6257
- 2,000 samples: 0.5989
- 4,000 samples: 0.5539

These results indicate improvements in character-level recognition as the training data increases.

However, the model remains a prototype and requires substantially more training to achieve reliable transcription accuracy.

### NLP Evaluation

The NLP module was evaluated using precision, recall, and F1-score on 24 synthetic meeting transcripts.

| Section / Field | Precision | Recall | F1-Score |
|---|---:|---:|---:|
| Summary | 0.287 | 0.375 | 0.325 |
| Decisions | 0.500 | 0.019 | 0.036 |
| Action Items | 0.573 | 0.553 | **0.562** |
| Risks | 1.000 | 0.013 | 0.025 |
| Open Questions | 0.000 | 0.000 | 0.000 |
| Deadline Expressions | 0.632 | 0.538 | **0.581** |

Additional results:

- Owner exact match: 45/62 (72.6%).
- Deadline exact match: 39/62 (62.9%).
- Predicted action items: 124.
- Reference action items: 108.

Action items and deadline expressions achieved moderate F1-scores, while decision extraction, risk identification, and open-question detection require further improvement.

These NLP measurements are diagnostic results based on draft reference annotations, not a complete measure of report quality.

---

## 6. Meeting Report Generation

The NLP module generates a structured meeting report containing nine sections:

1. **Summary** – Extractive summary of the meeting.
2. **Decisions** – Identified decisions and agreements.
3. **Discussion Points** – Important topics discussed.
4. **Action Items** – Tasks and responsibilities identified from the transcript.
5. **Scheduled Follow-ups** – Follow-up activities and arrangements.
6. **Deadlines** – Extracted deadline expressions.
7. **Important Dates** – Relevant dates mentioned in the meeting.
8. **People** – Identified participants and mentioned individuals.
9. **Keywords** – Important terms and topics.

The system uses rule-based patterns and classifier outputs to identify supporting sentences.

Each action item can include:

- Responsible person.
- Task description.
- Deadline.
- Confidence score.

If an owner or deadline is missing from the transcript, it is marked as **Not Specified** rather than being guessed.

The generated meeting report can be exported in:

- PDF format.
- DOCX format.

---

## 7. Project Structure

The repository contains the ASR implementation, model checkpoints, configuration files, sample audio, and application components. The integrated NLP implementation is organized into separate preprocessing, analysis, processing, and report-generation components.

A logical representation of the system is:

```text
TRACE/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .gitattributes
│
├── configs/
│   └── english_2000_config.yaml
│
├── checkpoints_2000/
│   ├── best.pt
│   ├── last.pt
│   └── history.json
│
├── datasets/
│   ├── README.md
│   └── sample_audio/
│       ├── FLAC recordings
│       └── metadata.csv
│
├── data/
│   └── LibriSpeech/
│       ├── train-clean-100/
│       └── dev-clean/
│
├── src/
│   ├── dataset.py
│   ├── model.py
│   ├── decoder.py
│   ├── train.py
│   ├── inference.py
│   └── utils.py
│
├── NLP/
│   ├── preprocessing
│   ├── analysis
│   ├── processing
│   └── PDF report generation
│
├── tests/
│
├── prepare_samples.py
└── fix_metadata.py
```

The exact filenames and directories may differ from this logical representation.

**Important:**
- Model checkpoint files are stored using Git LFS.
- The complete LibriSpeech dataset is excluded from Git because of its size.
- The repository includes 100 selected sample audio recordings and their reference transcripts.
- The NLP module is a separate component of the complete TRACE system.

---

## 8. Requirements

- Windows, macOS, or Linux.
- Python 3.13 recommended (development environment).
- Git.
- Git LFS.
- PyTorch.
- Torchaudio.
- SoundFile.
- Gradio 6.x.
- PyYAML.
- Scikit-learn.
- NumPy.
- Required NLP and document-generation dependencies listed in `requirements.txt`.

A CPU is sufficient for inference. A compatible NVIDIA GPU or Apple MPS device can be used where supported.

Internet access is required for initial setup and dependency installation. After setup, the application can operate locally.

---

## 9. Setup on a New Computer

### Step 1: Install Git LFS

Download Git LFS:

https://git-lfs.com/

Initialize it:

```powershell
git lfs install
```

### Step 2: Clone the Repository

```powershell
git clone https://github.com/MariaZahid62/TRACE--ASR-MODEL.git
cd TRACE--ASR-MODEL
```

Download the model checkpoints:

```powershell
git lfs pull
```

The main application checkpoint is:

```text
checkpoints_2000/best.pt
```

### Step 3: Create a Virtual Environment

```powershell
py -3.13 -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**PyTorch compatibility:** Ensure that the installed PyTorch and Torchaudio versions are compatible.

If installation fails, use the official PyTorch installation selector:

https://pytorch.org/get-started/locally/

### Step 5: Download LibriSpeech

Download the dataset from:

https://www.openslr.org/12/

Extract the required splits into:

```text
TRACE/
└── data/
    └── LibriSpeech/
        ├── train-clean-100/
        └── dev-clean/
```

The full dataset is not stored in Git.

The repository also includes 100 selected sample recordings in:

```text
datasets/sample_audio/
```

Their corresponding reference transcripts are available in:

```text
datasets/sample_audio/metadata.csv
```

### Step 6: Run the Application

From the project root:

```powershell
python app.py
```

Open the application in your browser:

http://127.0.0.1:7860

---

## 10. Running and Evaluating the ASR Module

To evaluate the existing 2,000-sample checkpoint:

```powershell
python -m src.train --config configs/english_2000_config.yaml --eval-only --checkpoint checkpoints_2000/best.pt
```

This command evaluates the saved checkpoint without starting a new training run.

To start training:

```powershell
python -m src.train --config configs/english_2000_config.yaml
```

Training is optional because the trained checkpoint is already provided through Git LFS.

CPU training can be slow, particularly with the five-layer BiGRU architecture.

---

## 11. Software Testing

The project includes automatic unit tests and manual application checks.

### Unit Testing

The following components are covered by pytest tests:

- Model forward pass.
- Tokenizer conversion and reconstruction.
- Greedy CTC decoder.
- WER and CER calculations.

### Functional Testing

| Test Case | Expected Result |
|---|---|
| Model forward pass | Correct batch and vocabulary dimensions |
| Tokenizer round trip | Text converts to indices and back |
| Greedy decoder | Repeated symbols merge and blanks are removed |
| WER / CER | Correct error calculations |
| Missing audio | User is prompted to upload or record audio |
| Missing checkpoint | Checkpoint-not-found message is displayed |
| Audio upload | Audio is accepted and a transcript is generated |
| Microphone input | Recorded audio is accepted and transcribed |

The application was also manually checked using demonstration recordings and user-provided audio.

---

## 12. Limitations

TRACE is a working research prototype, and several limitations remain.

### ASR Limitations

- The model was trained on relatively small LibriSpeech subsets.
- Training was limited to one or two epochs.
- The achieved WER and CER are still high.
- Greedy decoding does not use an external language model.
- The model has not been evaluated on a separate held-out test set.
- LibriSpeech contains audiobook speech rather than natural meeting conversations.
- Real-world accents, background noise, and microphone variations may affect performance.

### NLP Limitations

- The NLP classifier uses a limited labelled dataset.
- Only 24 synthetic meeting transcripts were used for evaluation.
- Reference annotations have not been independently reviewed.
- Decision extraction has very low recall.
- Risk and open-question identification need improvement.
- Extractive summarization can select sentences that do not fully represent the meeting.
- Missing task owners and deadlines cannot be reliably inferred.

### Integration Limitations

Although TRACE contains both ASR and NLP modules, end-to-end performance has not been measured.

The NLP module was evaluated on written transcripts rather than transcripts generated by the ASR model.

Consequently, transcription errors may affect the quality of the final meeting report.

---

## 13. Future Work

Potential improvements include:

- Training the ASR model for more epochs.
- Using the complete LibriSpeech train-clean-100 dataset.
- Evaluating the model on an independent held-out test set.
- Improving transcription accuracy through language-model-assisted decoding.
- Applying data augmentation to improve robustness.
- Expanding the labelled NLP training dataset.
- Improving decision, risk, and open-question extraction.
- Obtaining independently reviewed NLP annotations.
- Improving extractive summarization.
- Evaluating the complete ASR-to-NLP pipeline.
- Testing with real meeting recordings and different speakers.
- Improving the accuracy and reliability of generated meeting reports.

---

## 14. Project Scope

TRACE currently focuses on:

- English speech recognition.
- Offline speech-to-text processing.
- Custom CNN-BiGRU-CTC acoustic modeling.
- Audio preprocessing and Log-Mel feature extraction.
- Bidirectional sequence modeling.
- CTC-based model training and greedy decoding.
- LibriSpeech dataset integration.
- Model checkpoint management.
- WER and CER evaluation.
- Hybrid NLP-based transcript analysis.
- Rule-based information extraction.
- TF-IDF and Logistic Regression classification.
- Meeting summarization.
- Decision and action-item identification.
- Deadline and important-date extraction.
- Structured meeting report generation.
- PDF and DOCX export.
- Modular local application architecture.

---

## 15. Authors

Maria Zahid (Roll No. 062)
Usman Ahmed (Roll No. 134)

Department of Computer Science
Bahria University Islamabad, Pakistan

Course: AI 5C
Instructor: Ms. Afrah Naeem Najmi

Project: TRACE – An Offline Speech-to-Text and Meeting Report System Built from Scratch