from typing import List
import gradio as gr
from pathlib import Path
from sonic_wrapper.sonic_api_wrapper import CartesiaVoiceManager, VoiceAccessibility, improve_tts_text
import os
import json
import datetime

# Global variable to hold the manager instance
manager = None

# Constants
LANGUAGE_CHOICES = ["all", "ru", "en", "es", "pl", "de", "fr", "tr", "pt", "zh", "ja", "hi", "it", "ko", "nl", "sv"]
ACCESS_TYPE_MAP = {
    "All": VoiceAccessibility.ALL,
    "Custom Only": VoiceAccessibility.ONLY_CUSTOM,
    "Private Only": VoiceAccessibility.ONLY_PRIVATE,
    "API": VoiceAccessibility.ONLY_PUBLIC
}
SPEED_CHOICES = ["Very Slow", "Slow", "Normal", "Fast", "Very Fast"]
EMOTION_CHOICES = ["Neutral", "Happy", "Sad", "Angry", "Surprised", "Curious"]
EMOTION_INTENSITY = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong"]

def map_speed(speed_type: str) -> float:
    speed_map = {
        "Very Slow": -1.0,
        "Slow": -0.5,
        "Normal": 0.0,
        "Fast": 0.5,
        "Very Fast": 1.0
    }
    return speed_map[speed_type]

def generate_output_filename(language: str) -> str:
    """Generate output filename with timestamp and language"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"output/{timestamp}_{language}.wav"

def extract_voice_id_from_label(voice_label: str) -> str:
    """
    Extracts voice ID from label in dropdown
    For example: "John (en) [Custom]" -> extract ID from voices dictionary
    """
    global manager
    try:
        if not manager:
            return None

        # Get all voices and their labels
        choices = manager.get_voice_choices()
        # Find voice by label and get its ID
        voice_data = next((c for c in choices if c["label"] == voice_label), None)
        return voice_data["value"] if voice_data else None
    except Exception as e:
        print(f"❌ Error getting voices: {str(e)}")
        return None

def initialize_manager(api_key: str) -> str:
    global manager
    try:
        if not api_key:
            return "❌ API key is required to initialize the manager"

        manager = CartesiaVoiceManager(api_key=api_key, base_dir=Path("voice2voice"))
        return "✅ Manager initialized"
    except Exception as e:
        manager = None
        return f"❌ Error: {str(e)}"

def get_initial_voices():
    global manager
    """Get initial list of voices"""
    if not manager:
        return [], None
    choices = manager.get_voice_choices()
    if not choices:
        return [], None  
    return [c["label"] for c in choices], choices[0]["label"] if choices else None

def update_voice_list(language: str, access_type: str, current_voice: str = None):
    """
    Update the list of voices, preserving the current selection
    """
    global manager
    if not manager:
        return gr.update(choices=[], value=None), "❌ Manager is not initialized"
    
    try:
        choices = manager.get_voice_choices(
            language=None if language == "all" else language,
            accessibility=ACCESS_TYPE_MAP[access_type]
        )
        
        # Convert to list of labels
        choice_labels = [c["label"] for c in choices]
        
        # Determine value to select
        if current_voice in choice_labels:
            # Preserve current selection if available
            new_value = current_voice
        else:
            # Otherwise, take the first available voice
            new_value = choice_labels[0] if choice_labels else None
            
        return gr.update(choices=choice_labels, value=new_value), "✅ Voice list updated"
    except Exception as e:
        return gr.update(choices=[], value=None), f"❌ Error: {str(e)}"

def update_voice_info(voice_label: str) -> str:
    """Update voice information"""
    global manager
    if not manager or not voice_label:
        return ""
    
    try:
        voice_id = extract_voice_id_from_label(voice_label)
        if not voice_id:
            return "❌ Voice not found"
            
        info = manager.get_voice_info(voice_id)
        return (
            f"Name: {info['name']}\n"
            f"Language: {info['language']}\n"
            f"Type: {'Custom' if info.get('is_custom') else 'API'}\n"
            f"ID: {info['id']}"
        )
    except Exception as e:
        return f"❌ Error: {str(e)}"

def create_custom_voice(name: str, language: str, audio_data: tuple) -> tuple:
    """
    Creates a custom voice and updates the list of voices
    Returns: (status, updated dropdown, voice info)
    """
    global manager
    if not manager:
        return "❌ Manager is not initialized", gr.update(), ""
    
    if not name or not audio_data:
        return "❌ Name and voice file are required", gr.update(), ""
    
    try:
        # Get the audio file path
        audio_path = audio_data[0] if isinstance(audio_data, tuple) else audio_data
        
        # Create the voice
        voice_id = manager.create_custom_voice(
            name=name,
            source=audio_path,
            language=language
        )
        
        print(voice_id)
        
        # Get updated list of voices
        choices = manager.get_voice_choices()
        choice_labels = [c["label"] for c in choices]
        
        # Find label for the new voice
        new_voice_label = next(c["label"] for c in choices if c["value"] == voice_id)
        
        # Get info of the new voice
        voice_info = manager.get_voice_info(voice_id)
        info_text = (
            f"Name: {voice_info['name']}\n"
            f"Language: {voice_info['language']}\n"
            f"Type: Custom\n"
            f"ID: {voice_info['id']}"
        )
        
        return (
            f"✅ Custom voice created: {voice_id}",
            gr.update(choices=choice_labels, value=new_voice_label),
            info_text
        )
        
    except Exception as e:
        return f"❌ Error creating voice: {str(e)}", gr.update(), ""

def on_auto_language_change(auto_language: bool):
    """Handler for changing the auto-detect language checkbox"""
    return gr.update(visible=not auto_language)

def map_emotions(selected_emotions, intensity):
    emotion_map = {
        "Happy": "positivity",
        "Sad": "sadness",
        "Angry": "anger",
        "Surprised": "surprise",
        "Curious": "curiosity"
    }
    
    intensity_map = {
        "Very Weak": "lowest",
        "Weak": "low",
        "Medium": "medium",
        "Strong": "high",
        "Very Strong": "highest"
    }
    
    emotions = []
    for emotion in selected_emotions:
        if emotion == "Neutral":
            continue
        if emotion in emotion_map:
            emotions.append({
                "name": emotion_map[emotion],
                "level": intensity_map[intensity]
            })
    return emotions

def generate_speech(
    text: str,
    voice_label: str,
    improve_text: bool,
    auto_language: bool,
    manual_language: str,
    speed_type: str,
    use_custom_speed: bool,
    custom_speed: float,
    emotions: List[str],
    emotion_intensity: str
):
    global manager
    """Generate speech considering language settings"""
    if not manager:
        return None, "❌ Manager is not initialized"
    
    if not text or not voice_label:
        return None, "❌ Text and voice are required"
    
    try:
        # Extract voice ID from label
        voice_id = extract_voice_id_from_label(voice_label)
        if not voice_id:
            return None, "❌ Voice not found"
            
        # Set the voice by ID
        manager.set_voice(voice_id)
        
        # If auto-detect is off, set language manually
        if not auto_language:
            manager.set_language(manual_language)
        
        # Set speed
        if use_custom_speed:
            manager.speed = custom_speed
        else:
            manager.speed = map_speed(speed_type)
        
        # Set emotions
        if emotions and emotions != ["Neutral"]:
            manager.set_emotions(map_emotions(emotions, emotion_intensity))
        else:
            manager.set_emotions()  # Reset emotions
        
        # Generate output file name
        output_file = generate_output_filename(
            manual_language if not auto_language else manager.current_language
        )
        
        # Create output directory if it doesn't exist
        os.makedirs("output", exist_ok=True)
        
        # Generate speech
        output_path = manager.speak(
            text=text if not improve_text else improve_tts_text(text, manager.current_language),
            output_file=output_file
        )
        
        return output_path, "✅ Audio generated successfully"
        
    except Exception as e:
        return None, f"❌ Error generating speech: {str(e)}"

def initialize_manager_and_update(api_key: str, language: str, access_type: str, current_voice: str = None):
    status = initialize_manager(api_key)
    if manager:
        voice_update, voice_status = update_voice_list(language, access_type, current_voice)
        combined_status = f"{status}\n{voice_status}"
        return combined_status, voice_update
    else:
        return status, gr.update(choices=[], value=None)

# Create the interface
with gr.Blocks() as demo:
    # API key
    cartesia_api_key = gr.Textbox(
        label="Cartesia API Key",
        value="",  # No default API key
        type='password'
    )
    
    with gr.Row():
        # Left column
        with gr.Column():
            cartesia_text = gr.TextArea(label="Text")
            
            with gr.Accordion(label="Settings", open=True):
                # Filters
                with gr.Accordion("Filters", open=True):
                    cartesia_setting_filter_lang = gr.Dropdown(
                        label="Language",
                        choices=LANGUAGE_CHOICES,
                        value="all"
                    )
                    cartesia_setting_filter_type = gr.Dropdown(
                        label="Type",
                        choices=list(ACCESS_TYPE_MAP.keys()),
                        value="All"
                    )
                
                # Settings tabs
                with gr.Tab("Standard"):
                    cartesia_setting_voice_info = gr.Textbox(
                        label="Voice Information",
                        interactive=False
                    )
                    with gr.Row():
                        initial_choices, initial_value = get_initial_voices()
                        cartesia_setting_voice = gr.Dropdown(
                            label="Voice",
                            choices=initial_choices,
                            value=initial_value
                        )
                    cartesia_setting_voice_update = gr.Button("Refresh")
                    cartesia_setting_auto_language = gr.Checkbox(
                         label="Automatically detect language from voice",
                         value=True
                     )
                    cartesia_setting_manual_language = gr.Dropdown(
                         label="Speech Language",
                         choices=["ru", "en", "es", "fr", "de", "pl", "it", "ja", "ko", "zh", "hi"],
                         value="en",
                         visible=False  # Initially hidden
                     )
                
                with gr.Tab("Custom"):
                    cartesia_setting_custom_name = gr.Textbox(label="Name")
                    cartesia_setting_custom_lang = gr.Dropdown(
                        label="Language",
                        choices=LANGUAGE_CHOICES[1:]  # Exclude "all"
                    )
                    cartesia_setting_custom_voice = gr.Audio(label="Voice File", type='filepath')
                    cartesia_setting_custom_add = gr.Button("Add")
            
            # Emotion control
            with gr.Accordion(label="Emotion Control (Beta)", open=False):
                cartesia_emotions = gr.Dropdown(
                    label="Emotions",
                    multiselect=True,
                    choices=EMOTION_CHOICES
                )
                cartesia_emotions_intensity = gr.Dropdown(
                    label="Intensity",
                    choices=EMOTION_INTENSITY,
                    value="Medium"
                )
            
            # Speed settings
            with gr.Accordion("Speed", open=True):
                cartesia_speed_speed = gr.Dropdown(
                    label="Speech Speed",
                    choices=SPEED_CHOICES,
                    value="Normal"
                )
                cartesia_speed_speed_allow_custom = gr.Checkbox(
                    label="Use custom speed value"
                )
                cartesia_speed_speed_custom = gr.Slider(
                    label="Speed",
                    value=0,
                    minimum=-1,
                    maximum=1,
                    step=0.1,
                    visible=False
                )
            
            cartesia_setting_improve_text = gr.Checkbox(
                label="Improve text according to recommendations",
                value=True
            )
        
        # Right column
        with gr.Column():
            cartessia_status_bar = gr.Label(value="Status")
            cartesia_output_audio = gr.Audio(
                label="Result",
                interactive=False
            )
            cartesia_output_button = gr.Button("Generate")

    # Events
    cartesia_api_key.change(
        initialize_manager_and_update,
        inputs=[cartesia_api_key, cartesia_setting_filter_lang, cartesia_setting_filter_type, cartesia_setting_voice],
        outputs=[cartessia_status_bar, cartesia_setting_voice]
    )
    
    cartesia_setting_filter_lang.change(
        update_voice_list,
        inputs=[
            cartesia_setting_filter_lang,
            cartesia_setting_filter_type,
            cartesia_setting_voice  # Pass the current selection
        ],
        outputs=[cartesia_setting_voice, cartessia_status_bar]
    )

    cartesia_setting_filter_type.change(
        update_voice_list,
        inputs=[
            cartesia_setting_filter_lang,
            cartesia_setting_filter_type,
            cartesia_setting_voice  # Pass the current selection
        ],
        outputs=[cartesia_setting_voice, cartessia_status_bar]
    )
    
    cartesia_setting_voice.change(
        update_voice_info,
        inputs=[cartesia_setting_voice],
        outputs=[cartesia_setting_voice_info]
    )
    
    cartesia_setting_voice_update.click(
        update_voice_list,
        inputs=[cartesia_setting_filter_lang, cartesia_setting_filter_type, cartesia_setting_voice],
        outputs=[cartesia_setting_voice, cartessia_status_bar]
    )
    
    cartesia_speed_speed_allow_custom.change(
        lambda x: gr.update(visible=x),
        inputs=[cartesia_speed_speed_allow_custom],
        outputs=[cartesia_speed_speed_custom]
    )
    
    cartesia_setting_custom_add.click(
        create_custom_voice,
        inputs=[
            cartesia_setting_custom_name,
            cartesia_setting_custom_lang,
            cartesia_setting_custom_voice
        ],
        outputs=[
            cartessia_status_bar,
            cartesia_setting_voice,  # Update dropdown
            cartesia_setting_voice_info  # Update voice info
        ]
    )
    
    cartesia_setting_auto_language.change(
        on_auto_language_change,
        inputs=[cartesia_setting_auto_language],
        outputs=[cartesia_setting_manual_language]
    )

    cartesia_output_button.click(
        generate_speech,
        inputs=[
            cartesia_text,
            cartesia_setting_voice,
            cartesia_setting_improve_text,
            cartesia_setting_auto_language,
            cartesia_setting_manual_language,
            cartesia_speed_speed,
            cartesia_speed_speed_allow_custom,
            cartesia_speed_speed_custom,
            cartesia_emotions,
            cartesia_emotions_intensity
        ],
        outputs=[
            cartesia_output_audio,
            cartessia_status_bar
        ]
    )

# Run the app
if __name__ == "__main__":
    demo.queue()
    demo.launch(share=True)
