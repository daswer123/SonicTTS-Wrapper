import argparse
import sys
from pathlib import Path
from sonic_api_wrapper import CartesiaVoiceManager, VoiceAccessibility, improve_tts_text
import os
from dotenv import load_dotenv

def main():
    parser = argparse.ArgumentParser(
        description="Cartesia Voice Manager CLI",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Set API key (without --api-key flag)
    parser_set_key = subparsers.add_parser('set-api-key', help='Set or update the API key and save it to .env file')
    parser_set_key.add_argument('api_key', help='Cartesia API Key')

    # List voices
    parser_list = subparsers.add_parser('list-voices', help='List available voices')
    parser_list.add_argument('--language', default='all', help='Filter voices by language (default: all)')
    parser_list.add_argument('--accessibility', choices=['all', 'custom', 'api'], default='all',
                             help='Filter voices by accessibility (default: all)')

    # Generate speech
    parser_generate = subparsers.add_parser('generate-speech', help='Generate speech from text')
    parser_generate.add_argument('--text', required=True, help='Text to synthesize')
    parser_generate.add_argument('--voice', required=True, help='Voice ID or name to use')
    parser_generate.add_argument('--language', help='Language of the speech (optional)')
    parser_generate.add_argument('--output', help='Output file path (optional)')
    parser_generate.add_argument('--improve-text', action='store_true', help='Improve text before synthesis')
    parser_generate.add_argument('--speed', type=float, default=0.0,
                                 help='Speech speed (-1 to 1, default: 0.0)')
    parser_generate.add_argument('--emotions', nargs='+', metavar='EMOTION:INTENSITY',
                                 help='List of emotions and intensities.\n'
                                      'Format: emotion:intensity\n'
                                      'Example: --emotions "positivity:medium" "curiosity:high"\n'
                                      'Valid emotions: anger, positivity, surprise, sadness, curiosity\n'
                                      'Valid intensities: lowest, low, medium, high, highest')

    # Create custom voice
    parser_create_voice = subparsers.add_parser('create-voice', help='Create a custom voice')
    parser_create_voice.add_argument('--name', required=True, help='Name of the custom voice')
    parser_create_voice.add_argument('--source', required=True, help='Path to the audio file or JSON embedding')
    parser_create_voice.add_argument('--language', help='Language of the custom voice (optional)')
    parser_create_voice.add_argument('--description', default='', help='Description of the custom voice')

    # Parse arguments
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Initialize manager
    manager = CartesiaVoiceManager(base_dir=Path("voice2voice"))

    # Handle set-api-key command
    if args.command == 'set-api-key':
        manager.set_api_key(args.api_key)
        print("API key updated and saved to .env file.")
        sys.exit(0)

    # Ensure API key is set
    if not manager.api_key:
        print("API key is not set. Use 'set-api-key' command to set it.")
        sys.exit(1)

    # Handle list-voices command
    if args.command == 'list-voices':
        accessibility = {
            'all': VoiceAccessibility.ALL,
            'custom': VoiceAccessibility.ONLY_CUSTOM,
            'api': VoiceAccessibility.ONLY_PUBLIC
        }[args.accessibility]
        voices = manager.list_available_voices(
            languages=[args.language] if args.language != 'all' else None,
            accessibility=accessibility
        )
        if not voices:
            print("No voices found with the specified filters.")
        else:
            for voice in voices:
                print(f"ID: {voice['id']}, Name: {voice['name']}, Language: {voice['language']}, "
                      f"Type: {'Custom' if voice.get('is_custom') else 'API'}")
        sys.exit(0)

    # Handle generate-speech command
    if args.command == 'generate-speech':
        # Resolve voice ID or name
        voice_identifier = args.voice
        try:
            # Try loading by voice ID
            manager.load_voice(voice_identifier)
            voice_id = voice_identifier
        except ValueError:
            # Try resolving by voice name
            matching_voice_ids = manager.get_voice_id_by_name(voice_identifier)
            if not matching_voice_ids:
                print(f"Voice '{voice_identifier}' not found by ID or name.")
                sys.exit(1)
            elif len(matching_voice_ids) > 1:
                print(f"Multiple voices found with name '{voice_identifier}'. Please specify the voice ID.")
                for vid in matching_voice_ids:
                    print(f"- {vid}")
                sys.exit(1)
            else:
                voice_id = matching_voice_ids[0]

        # Set the voice
        manager.set_voice(voice_id)

        # Set language if provided
        if args.language:
            manager.set_language(args.language)

        # Set speed
        manager.speed = args.speed

        # Set emotions if provided
        if args.emotions:
            emotions = []
            valid_emotions = ["anger", "positivity", "surprise", "sadness", "curiosity"]
            valid_intensities = ["lowest", "low", "medium", "high", "highest"]
            for item in args.emotions:
                try:
                    name, level = item.split(':')
                    name = name.strip().lower()
                    level = level.strip().lower()
                    if name not in valid_emotions:
                        print(f"Invalid emotion name: {name}. Valid emotions are: {', '.join(valid_emotions)}")
                        sys.exit(1)
                    if level not in valid_intensities:
                        print(f"Invalid intensity level: {level}. Valid intensities are: {', '.join(valid_intensities)}")
                        sys.exit(1)
                    emotions.append({'name': name, 'level': level})
                except ValueError:
                    print(f"Invalid emotion format: {item}. Expected format is emotion:intensity")
                    sys.exit(1)
            manager.set_emotions(emotions)
        else:
            manager.set_emotions()

        # Prepare text
        text = args.text
        if args.improve_text:
            text = improve_tts_text(text, manager.current_language)

        # Set output file path
        output_file = args.output or f"output_{manager.current_language}.wav"

        # Generate speech
        try:
            output_path = manager.speak(
                text=text,
                output_file=output_file
            )
            print(f"Audio generated and saved to {output_path}")
        except Exception as e:
            print(f"Error generating speech: {e}")
        sys.exit(0)

    # Handle create-voice command
    if args.command == 'create-voice':
        try:
            voice_id = manager.create_custom_voice(
                name=args.name,
                source=args.source,
                description=args.description,
                language=args.language or 'en'  # Default to 'en' if not specified
            )
            print(f"Custom voice created with ID: {voice_id}")
        except Exception as e:
            print(f"Error creating custom voice: {e}")
        sys.exit(0)

    # If no valid command is provided, show help
    parser.print_help()

if __name__ == '__main__':
    main()
