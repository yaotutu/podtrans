# Translation Module Guide

## Overview

The translation module translates ASR (transcription) results from English to Chinese using OpenAI-compatible API (Alibaba DashScope).

## Setup

### 1. Get API Key

1. Visit [DashScope Console](https://dashscope.console.aliyun.com/)
2. Create or obtain your API key

### 2. Configure Environment

```bash
# Copy the example .env file
cp .env.example .env

# Edit .env and add your API key
DASHSCOPE_API_KEY=your_api_key_here
```

### 3. Configuration Options

You can customize translation behavior in `.env`:

```bash
# Model selection (default: qwen-coder-plus)
TRANSLATION_MODEL=qwen-coder-plus

# API endpoint (default: DashScope)
TRANSLATION_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# Batch size for translation (default: 10 segments per API call)
TRANSLATION_BATCH_SIZE=10

# Maximum retries for failed API calls (default: 3)
MAX_RETRIES=3
```

## Usage

### Basic Translation

Translate an existing ASR result:

```bash
podtrans translate data/output/demo/asr_result.json
```

### Custom Output Directory

```bash
podtrans translate data/output/demo/asr_result.json -o ./my_translations
```

### Custom Language Pair

```bash
podtrans translate asr_result.json -s en -t zh
```

## Output Files

The translation command generates three files:

1. **translation_result.json**: Complete translation data in JSON format
   - Contains original text, translated text, timestamps, and speaker info
   - Machine-readable format for further processing

2. **translation_result.zh.txt**: Chinese-only transcript
   - Clean Chinese text with speaker labels
   - Human-readable format

3. **translation_result.bilingual.txt**: Bilingual transcript
   - Original English and Chinese translation side-by-side
   - Useful for reviewing translation quality

## Example Workflow

```bash
# Step 1: Transcribe audio
podtrans transcribe data/input/demo.mp3

# Step 2: Translate transcription
podtrans translate data/output/demo/asr_result.json

# Output files will be in: data/output/demo/
# - asr_result.json (from step 1)
# - translation_result.json
# - translation_result.zh.txt
# - translation_result.bilingual.txt
```

## Troubleshooting

### API Key Not Set

```
Error: DASHSCOPE_API_KEY not set
```

**Solution**: Make sure you've created a `.env` file and added your API key.

### Translation Count Mismatch

```
Translation count mismatch: expected X, got Y
```

**Solution**: This usually indicates an API issue. The system will retry automatically (up to 3 times by default).

### Rate Limiting

If you're translating a large number of segments, the API might rate-limit your requests.

**Solution**: 
- Reduce `TRANSLATION_BATCH_SIZE` in `.env`
- Increase retry delay (code modification needed)
- Contact DashScope support for higher rate limits

## Advanced Features

### Batch Processing

The translator automatically batches segments to optimize API usage:
- Default batch size: 10 segments per API call
- Configurable via `TRANSLATION_BATCH_SIZE`
- Each batch is translated in a single API call

### Automatic Retry

Failed translations are automatically retried:
- Default: 3 retries
- Configurable via `MAX_RETRIES`
- Exponential backoff (future enhancement)

### Speaker Preservation

Speaker information from ASR is preserved in translation:
- Each segment retains its speaker ID
- Bilingual output shows speaker labels
- Useful for multi-speaker podcasts

## Model Selection

Available models on DashScope (as of 2025):
- `qwen-coder-plus`: Recommended for technical content
- `qwen-plus`: General-purpose translation
- `qwen-turbo`: Faster, lower cost
- `qwen-max`: Highest quality (may have higher cost)

Update `TRANSLATION_MODEL` in `.env` to switch models.
