# Install and Serve Seb-9B-v2-Q4_K_M

## 1. Objective

Download and install the `Seb-9B-v2` model in GGUF format and make it available through a local vLLM-compatible API server.

The installation must be reusable by other applications and projects.


## 2. Model details

| Parameter | Value |
|---|---|
| Model name | Seb-9B-v2 |
| Quantization | Q4_K_M |
| Format | GGUF |
| Hugging Face repository | `mradermacher/Seb-9B-v2-GGUF` |
| Model filename | `Seb-9B-v2.Q4_K_M.gguf` |
| Tokenizer/config source | `ironbcc/Seb-9B-v2` |
| Served model name | `seb` |

Model download URI:

`hf://mradermacher/Seb-9B-v2-GGUF/Seb-9B-v2.Q4_K_M.gguf`

## 3. Detect the environment

Before installation, identify:

- Operating system and version.
- CPU architecture.
- Whether the machine has Apple Silicon or an NVIDIA GPU.
- Available RAM and, where applicable, GPU memory.
- Python version.
- Whether `hf` and `vllm` commands are already installed.

Choose the appropriate runtime based on the detected platform.

### Runtime selection

| Environment | Runtime |
|---|---|
| macOS, Apple Silicon | vLLM Metal |
| Linux, NVIDIA GPU | Standard vLLM with GGUF plugin |
| Other environments | Check official vLLM platform support before proceeding |

Do not attempt to install standard CUDA-based vLLM as if it were the macOS runtime.

## 4. Download the model

### 4.1 Install Hugging Face CLI

Check whether the CLI is available:

```bash
hf --version
```

If missing, install or upgrade Hugging Face Hub:

```bash
python -m pip install -U huggingface_hub
```

If the repository requires authentication, use:

```bash
hf auth login
```

Do not request or print the user's access token.

### 4.2 Download the GGUF file

Create a dedicated model directory:

```bash
mkdir -p ~/models/Seb-9B-v2
```

Download the exact file:

```bash
hf download hf://mradermacher/Seb-9B-v2-GGUF/Seb-9B-v2.Q4_K_M.gguf \
  --local-dir ~/models/Seb-9B-v2
```

Do not download the entire repository unnecessarily.

### 4.3 Verify the download

```bash
ls -lh ~/models/Seb-9B-v2/Seb-9B-v2.Q4_K_M.gguf
```

Verify:

- The file exists.
- Its size is non-zero.
- The filename matches the requested quantization.
- The download command completed successfully.

If the file already exists and is valid, do not download it again unless explicitly requested.

## 5. Install the inference runtime

### 5.1 macOS with Apple Silicon

Use the official vLLM Metal installation method.

Stable Homebrew installation:

```bash
brew tap vllm-project/vllm-metal https://github.com/vllm-project/vllm-metal
brew install vllm-project/vllm-metal/vllm-metal
```

Verify:

```bash
vllm --version
```

The agent must confirm that the installed runtime is vLLM Metal, not a standard CUDA-oriented installation.

### 5.2 Linux with NVIDIA GPU

Install standard vLLM using its official installation instructions.

For GGUF support, install the required plugin:

```bash
uv pip install vllm-gguf-plugin
```

Verify the installation:

```bash
vllm --version
```

Do not assume that macOS-specific vLLM Metal instructions apply to Linux.

## 6. Start the model server

Use the following command as the initial configuration:

```bash
vllm serve ~/models/Seb-9B-v2/Seb-9B-v2.Q4_K_M.gguf \
  --tokenizer ironbcc/Seb-9B-v2 \
  --served-model-name seb \
  --logprobs-mode processed_logprobs \
  --max-logprobs 32 \
  --generation-config vllm \
  --max-model-len 8192 \
  --max-num-seqs 8 \
  --enable-prefix-caching
```

Important:

- Use the actual downloaded model path.
- Keep the tokenizer source as `ironbcc/Seb-9B-v2`.
- Preserve the requested model name `seb`.
- Check `vllm serve --help` before using the optional flags.
- If a flag is unsupported by the installed runtime, report it and identify an equivalent supported configuration. Do not silently remove configuration options.
- Do not assume that the model will fit in available memory. Check memory requirements and runtime logs.

## 7. Verify the server

Once the server starts, check the model endpoint:

```bash
curl -s http://localhost:8000/v1/models | jq .
```

Expected model identifier:

`seb`

Run a basic inference test:

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "seb",
    "messages": [
      {
        "role": "user",
        "content": "Hello. Briefly introduce yourself."
      }
    ],
    "max_tokens": 100
  }' | jq .
```

The test is successful if the server returns a valid completion without errors.

## 8. Installation requirements and constraints

- Do not substitute another model or quantization.
- Do not change the tokenizer source without justification.
- Do not download model files into the application source directory.
- Do not expose the API server publicly by default.
- Keep model files available for future applications.
- Do not repeatedly download an existing valid model.
- Do not claim successful installation until a real inference request succeeds.

## 9. Acceptance criteria

- [ ] Correct operating system and architecture detected.
- [ ] Appropriate vLLM runtime selected.
- [ ] Hugging Face CLI installed and working.
- [ ] Exact GGUF file downloaded.
- [ ] Model stored in a reusable directory.
- [ ] Model file verified.
- [ ] vLLM runtime installed.
- [ ] Model successfully loaded.
- [ ] Tokenizer source configured correctly.
- [ ] API server starts.
- [ ] `/v1/models` returns `seb`.
- [ ] A test inference request succeeds.

## 10. Final installation report

Provide:

1. Operating system and architecture.
2. Runtime selected and its version.
3. Hugging Face repository and downloaded filename.
4. Local model path and file size.
5. Tokenizer source.
6. Exact command used to start the server.
7. API endpoint.
8. Result of the inference test.
9. Any unsupported flags, compatibility problems, or memory limitations.

If installation fails, report the exact error and the stage at which it occurred. Do not silently switch runtimes or model versions.