# Cartesia Voice Manager

A wrapper around the official Cartesia API for more convenient work with text-to-speech functionality. It also includes a Gradio interface for easy interaction (currently in Russian).

## TODO
- [x] Package and publish to PyPI
- [x] Translate Gradio interface to English
- [ ] Implement voice mixing functionality in Gradio interface

## Features

- Easy-to-use wrapper for Cartesia API
- Voice management (listing, creating custom voices, getting voice info)
- Text-to-speech generation with various controls:
  - Language selection (auto-detect or manual)
  - Speed control
  - Emotion control
  - Text improvement options
- Gradio web interface for interactive use (currently in Russian)

## Functionality

1. **Voice Management**
   - List available voices with filtering options
   - Create custom voices from audio files
   - Get detailed information about voices

2. **Text-to-Speech**
   - Generate speech from text with selected voice
   - Control speech speed (very slow to very fast)
   - Add emotions to speech (happiness, sadness, anger, surprise, curiosity)
   - Adjust emotion intensity
   - Automatically improve input text for better TTS results

3. **Gradio Interface**
   - User-friendly web interface for all functionalities
   - Real-time updates and previews
   - Easy configuration of TTS parameters

## Note

This project is still a work in progress. Some features may be incomplete or subject to change. Contributions and suggestions are welcome!
