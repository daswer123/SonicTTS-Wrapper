# Cartesia Sonic TTS Wrapper

**You need your own [API key](**https://play.cartesia.ai/keys**) to use demo.**

<a href="https://huggingface.co/spaces/daswer123/sonic-tts-webui"  style='padding-left: 0.5rem;'><img src='https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Demo-orange'></a> <a href='https://colab.research.google.com/drive/1-AWeWhPvCTBX0KfMtgtMk10uPU05ihoA?usp=sharing' style='padding-left: 0.5rem;'></a>


## About

A simple and powerful wrapper for the [Cartesia Sonic Text-to-Speech (TTS) API](https://www.cartesia.ai/sonic), providing an easy-to-use interface for generating speech from text in multiple languages with advanced features. The package includes:

- A Python library for developers.
- A Command-Line Interface (CLI) for terminal interaction.
- A Gradio web interface for user-friendly interaction.

**Note**: To use this wrapper, you need a valid API key from Cartesia. A subscription is required to access the Sonic TTS API. Visit [Cartesia Sonic](https://www.cartesia.ai/sonic) for more information.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Setting Up the API Key](#setting-up-the-api-key)
- [Usage](#usage)
  - [As a Python Library](#as-a-python-library)
    - [Initializing the Voice Manager](#initializing-the-voice-manager)
    - [Voice Management](#voice-management)
    - [Text-to-Speech Generation](#text-to-speech-generation)
  - [Command-Line Interface (CLI)](#command-line-interface-cli)
    - [Commands and Usage](#commands-and-usage)
  - [Gradio Web Interface](#gradio-web-interface)
    - [Running the Interface](#running-the-interface)
    - [Online Demo](#online-demo)
- [Examples](#examples)
  - [Generating Speech with Emotions](#generating-speech-with-emotions)
  - [Creating and Using a Custom Voice](#creating-and-using-a-custom-voice)
- [Notes](#notes)
- [TODO](#todo)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contact](#contact)

## Features

- **Easy-to-use Python Wrapper**: Simplifies interaction with the Cartesia Sonic TTS API.
- **Text-to-Speech Generation**:
  - Supports multiple languages.
  - Speed control from very slow to very fast.
  - Emotion control with adjustable intensity.
  - Text improvement options for better TTS results.
- **Voice Management**:
  - List available voices with filtering options.
  - Create custom voices from audio files.
  - Get detailed information about voices.
- **Command-Line Interface (CLI)**: Interact with the TTS functionality via the terminal.
- **Gradio Web Interface**: User-friendly web application for interactive use.

## Installation

Install the `sonic-wrapper` package via pip:

```bash
pip install sonic-wrapper
```

**Note**: The package requires Python 3.9 or higher.

### Additional Dependencies for Gradio Interface

If you plan to use the Gradio web interface, install Gradio:

```bash
pip install gradio>=5.0.0
```

## Getting Started

### Setting Up the API Key

To use the Cartesia Sonic TTS API, you need a valid API key. Obtain an API key by subscribing to the service on the [Cartesia Sonic](https://www.cartesia.ai/sonic) website.

Once you have your API key, you can set it up:

- **Using the Python Library**: Provide the API key when initializing the `CartesiaVoiceManager`.
- **Using the CLI**: Set the API key using the `set-api-key` command.
- **Using the Gradio Interface**: Enter the API key in the provided field.

The API key is stored in a `.env` file for subsequent use.

## Usage

### As a Python Library

#### Initializing the Voice Manager

```python
from sonic_wrapper import CartesiaVoiceManager

# Initialize the manager with your API key
manager = CartesiaVoiceManager(api_key='your_api_key_here')
```

Alternatively, if you have set the `CARTESIA_API_KEY` environment variable or stored the API key in a `.env` file, you can initialize without passing the API key:

```python
manager = CartesiaVoiceManager()
```

#### Voice Management

**Listing Available Voices:**

```python
voices = manager.list_available_voices()
for voice in voices:
    print(f"ID: {voice['id']}, Name: {voice['name']}, Language: {voice['language']}")
```

**Filtering Voices by Language and Accessibility:**

```python
from sonic_wrapper import VoiceAccessibility

voices = manager.list_available_voices(
    languages=['en'],
    accessibility=VoiceAccessibility.ONLY_PUBLIC
)
```

**Getting Voice Information:**

```python
voice_info = manager.get_voice_info('voice_id')
print(voice_info)
```

**Creating a Custom Voice:**

```python
voice_id = manager.create_custom_voice(
    name='My Custom Voice',
    source='path/to/your_voice_sample.wav',
    language='en',
    description='This is a custom voice created from my own sample.'
)
```

#### Text-to-Speech Generation

**Setting the Voice:**

```python
manager.set_voice('voice_id')
```

**Adjusting Speed and Emotions:**

```python
# Set speech speed (-1.0 to 1.0)
manager.speed = 0.5  # Faster speech

# Set emotions
emotions = [
    {'name': 'positivity', 'level': 'high'},
    {'name': 'surprise', 'level': 'medium'}
]
manager.set_emotions(emotions)
```

**Generating Speech:**

```python
output_file = manager.speak(
    text='Hello, world!',
    output_file='output.wav'
)
print(f"Audio saved to {output_file}")
```

**Improving Text Before Synthesis:**

```python
from sonic_wrapper import improve_tts_text

text = 'Your raw text here.'
improved_text = improve_tts_text(text, language='en')
manager.speak(text=improved_text, output_file='improved_output.wav')
```

### Command-Line Interface (CLI)

The package includes a CLI tool for interacting with the TTS functionality directly from the terminal.

#### Commands and Usage

**Set API Key**

Set your Cartesia API key:

```bash
python -m sonic_wrapper.cli set-api-key your_api_key_here
```

**List Voices**

List all available voices:

```bash
python -m sonic_wrapper.cli list-voices
```

With filters:

```bash
python -m sonic_wrapper.cli list-voices --language en --accessibility api
```

**Generate Speech**

Generate speech from text using a specific voice:

```bash
python -m sonic_wrapper.cli generate-speech --text "Hello, world!" --voice "Voice Name or ID"
```

Additional options:

- **Specify Output File:**

  ```bash
  --output output.wav
  ```

- **Adjust Speech Speed:**

  ```bash
  --speed 0.5  # Speed ranges from -1.0 (slowest) to 1.0 (fastest)
  ```

- **Add Emotions:**

  ```bash
  --emotions "positivity:medium" "surprise:high"
  ```

  Valid emotions: `anger`, `positivity`, `surprise`, `sadness`, `curiosity`

  Valid intensities: `lowest`, `low`, `medium`, `high`, `highest`

**Create Custom Voice**

Create a custom voice from an audio file:

```bash
python -m sonic_wrapper.cli create-voice --name "My Custom Voice" --source path/to/audio.wav
```

### Gradio Web Interface

The Gradio interface provides a user-friendly web application for interacting with the TTS functionality.

#### Running the Interface

1. **Install Gradio** (if not already installed):

   ```bash
   pip install gradio>=5.0.0
   ```

2. **Run the Application**:

   ```bash
   python app.py
   ```

3. **Access the Web Interface**:

   Open the provided local URL in your web browser.

#### Online Demo

Try the Gradio interface online without installing anything:

[![Gradio Demo](https://img.shields.io/badge/Gradio-Demo-brightgreen)](https://huggingface.co/spaces/daswer123/sonic-tts-webui)

## Examples

### Generating Speech with Emotions

```bash
python -m sonic_wrapper.cli generate-speech \
  --text "I'm so excited to share this news with you!" \
  --voice "Enthusiastic Voice" \
  --emotions "positivity:high" "surprise:medium" \
  --speed 0.5 \
  --output excited_message.wav
```

### Creating and Using a Custom Voice

**Step 1: Create a Custom Voice**

```bash
python -m sonic_wrapper.cli create-voice \
  --name "Custom Voice" \
  --source path/to/your_voice_sample.wav \
  --description "A custom voice created from my own audio sample."
```

**Step 2: Generate Speech with the Custom Voice**

```bash
python -m sonic_wrapper.cli generate-speech \
  --text "This is my custom voice." \
  --voice "Custom Voice" \
  --output custom_voice_output.wav
```

## Notes

- **API Key**: A valid Cartesia API key is required to use this wrapper. Set your API key using the CLI or in your code. Visit [Cartesia Sonic](https://www.cartesia.ai/sonic) to obtain an API key.
- **Subscription**: Access to the Cartesia Sonic TTS API requires a subscription. Please refer to their [pricing page](https://www.cartesia.ai/sonic/pricing) for more details.
- **Voice Mixing**: Currently, voice mixing functionality is not available in the CLI and Gradio versions but is available in the Python library.
- **Voice Embeddings**: The wrapper handles voice embeddings for you, storing them locally for faster access.

## TODO

- [ ] Implement voice mixing functionality in Gradio interface and CLI.
- [ ] Enhance error handling and logging.
- [ ] Improve documentation with more examples and use cases.
- [ ] Add support for additional languages and voices as they become available.

## License

This project is licensed under the MIT License.
