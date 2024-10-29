import os
import json
from pathlib import Path
from typing import List, Dict, Union, Optional
from enum import Enum
from cartesia import Cartesia
from tqdm import tqdm
from loguru import logger
from datetime import datetime
import re

class VoiceAccessibility(Enum):
    ALL = "all"
    ONLY_PUBLIC = "only_public"
    ONLY_PRIVATE = "only_private"
    ONLY_CUSTOM = "only_custom"

class CartesiaVoiceManager:
    SPEED_OPTIONS = {
        "slowest": -1.0,
        "slow": -0.5,
        "normal": 0.0,
        "fast": 0.5,
        "fastest": 1.0
    }
    EMOTION_NAMES = ["anger", "positivity", "surprise", "sadness", "curiosity"]
    EMOTION_LEVELS = ["lowest", "low", "medium", "high", "highest"]

    def __init__(self, api_key: str = None, base_dir: Path = None):
        self.api_key = api_key or os.environ.get("CARTESIA_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required. Please provide it as an argument or set CARTESIA_API_KEY environment variable.")
        
        self.client = Cartesia(api_key=self.api_key)
        self.current_voice = None
        self.current_model = None
        self.current_language = None
        self.current_mix = None
        
        # Настройка директорий
        self.base_dir = base_dir or Path("voice2voice")
        self.api_dir = self.base_dir / "api"
        self.custom_dir = self.base_dir / "custom"
        
        # Создание необходимых директорий
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        
        # Инициализация голосов
        self.voices = {}
        self.loaded_voices = set()
        
        # Настройки скорости и эмоций
        self._speed = 0.0  # normal speed
        self._emotions = {}
        
        logger.add("cartesia_voice_manager.log", rotation="10 MB")
        logger.info("CartesiaVoiceManager initialized")

    def load_voice(self, voice_id: str) -> Dict:
        if voice_id in self.loaded_voices:
            return self.voices[voice_id]
            
        voice_file = None
        # Поиск файла голоса в api и custom директориях
        api_file = self.api_dir / f"{voice_id}.json"
        custom_file = self.custom_dir / f"{voice_id}.json"
        
        if api_file.exists():
            voice_file = api_file
        elif custom_file.exists():
            voice_file = custom_file
            
        if voice_file:
            with open(voice_file, "r") as f:
                voice_data = json.load(f)
                self.voices[voice_id] = voice_data
                self.loaded_voices.add(voice_id)
                logger.info(f"Loaded voice {voice_id} from {voice_file}")
                return voice_data
        else:
            # Если голос не найден локально, пытаемся загрузить из API
            try:
                voice_data = self.client.voices.get(id=voice_id)
                self._save_voice_to_api(voice_data)
                self.voices[voice_id] = voice_data
                self.loaded_voices.add(voice_id)
                logger.info(f"Loaded voice {voice_id} from API")
                return voice_data
            except Exception as e:
                logger.error(f"Failed to load voice {voice_id}: {e}")
                raise ValueError(f"Voice with id {voice_id} not found")

    def extract_voice_id_from_label(self, voice_label: str) -> Optional[str]:
        """
        Извлекает ID голоса из метки в dropdown
        Например: "John (en) [Custom]" -> извлечет ID из словаря голосов
        """
        # Получаем все голоса и их метки
        choices = self.get_voice_choices()
        # Находим голос по метке и берем его ID
        voice_data = next((c for c in choices if c["label"] == voice_label), None)
        return voice_data["value"] if voice_data else None
    
    def get_voice_choices(self, language: str = None, accessibility: VoiceAccessibility = VoiceAccessibility.ALL) -> List[Dict]:
        """
        Возвращает список голосов для dropdown меню
        """
        voices = self.list_available_voices(
            languages=[language] if language else None,
            accessibility=accessibility
        )

        choices = []
        for voice in voices:
            # Сохраняем только ID в value
            choices.append({
                "label": f"{voice['name']} ({voice['language']}){' [Custom]' if voice.get('is_custom') else ''}",
                "value": voice['id']  # Здесь только ID
            })

        return sorted(choices, key=lambda x: x['label'])

    def get_voice_info(self, voice_id: str) -> Dict:
        """
        Возвращает информацию о голосе для отображения
        """
        voice = self.load_voice(voice_id)
        return {
            "name": voice['name'],
            "language": voice['language'],
            "is_custom": voice.get('is_custom', False),
            "is_public": voice.get('is_public', True),
            "id": voice['id']
        }
    
    def _save_voice_to_api(self, voice_data: Dict):
        voice_id = voice_data["id"]
        file_path = self.api_dir / f"{voice_id}.json"
        with open(file_path, "w") as f:
            json.dump(voice_data, f, indent=2)
        logger.info(f"Saved API voice {voice_id} to {file_path}")

    def _save_voice_to_custom(self, voice_data: Dict):
        voice_id = voice_data["id"]
        file_path = self.custom_dir / f"{voice_id}.json"
        with open(file_path, "w") as f:
            json.dump(voice_data, f, indent=2)
        logger.info(f"Saved custom voice {voice_id} to {file_path}")

    def update_voices_from_api(self):
        logger.info("Updating voices from API")
        api_voices = self.client.voices.list()
        for voice in tqdm(api_voices, desc="Updating voices"):
            voice_id = voice["id"]
            full_voice_data = self.client.voices.get(id=voice_id)
            self._save_voice_to_api(full_voice_data)
            if voice_id in self.loaded_voices:
                self.voices[voice_id] = full_voice_data
        logger.info(f"Updated {len(api_voices)} voices from API")

    def list_available_voices(self, languages: List[str] = None, accessibility: VoiceAccessibility = VoiceAccessibility.ALL) -> List[Dict]:
        filtered_voices = []

        # Получаем только метаданные из API (без эмбеддингов)
        if accessibility in [VoiceAccessibility.ALL, VoiceAccessibility.ONLY_PUBLIC]:
            try:
                api_voices = self.client.voices.list()
                # Сохраняем только метаданные
                for voice in api_voices:
                    metadata = {
                        'id': voice['id'],
                        'name': voice['name'],
                        'language': voice['language'],
                        'is_public': True
                    }
                    if languages is None or metadata['language'] in languages:
                        filtered_voices.append(metadata)
            except Exception as e:
                logger.error(f"Failed to fetch voices from API: {e}")

        # Добавляем кастомные голоса если нужно
        if accessibility in [VoiceAccessibility.ALL, VoiceAccessibility.ONLY_PRIVATE, VoiceAccessibility.ONLY_CUSTOM]:
            for file in self.custom_dir.glob("*.json"):
                with open(file, "r") as f:
                    voice_data = json.load(f)
                    if languages is None or voice_data['language'] in languages:
                        filtered_voices.append({
                            'id': voice_data['id'],
                            'name': voice_data['name'],
                            'language': voice_data['language'],
                            'is_public': False,
                            'is_custom': True
                        })

        logger.info(f"Found {len(filtered_voices)} voices matching criteria")
        return filtered_voices

    def set_voice(self, voice_id: str):
        # Проверяем наличие локального файла с эмбеддингом
        voice_file = None
        api_file = self.api_dir / f"{voice_id}.json"
        custom_file = self.custom_dir / f"{voice_id}.json"

        if api_file.exists():
            voice_file = api_file
        elif custom_file.exists():
            voice_file = custom_file

        if voice_file:
            # Используем локальные данные
            with open(voice_file, "r") as f:
                self.current_voice = json.load(f)
        else:
            # Получаем полные данные с эмбеддингом из API
            try:
                voice_data = self.client.voices.get(id=voice_id)
                # Сохраняем для будущего использования
                self._save_voice_to_api(voice_data)
                self.current_voice = voice_data
            except Exception as e:
                logger.error(f"Failed to get voice {voice_id}: {e}")
                raise ValueError(f"Voice with id {voice_id} not found")

        self.set_language(self.current_voice['language'])
        logger.info(f"Set current voice to {voice_id}")

    def set_model(self, language: str):
        if language.lower() in ['en', 'eng', 'english']:
            self.current_model = "sonic-english"
        else:
            self.current_model = "sonic-multilingual"
        self.current_language = language
        logger.info(f"Set model to {self.current_model} for language {language}")

    def set_language(self, language: str):
        self.current_language = language
        self.set_model(language)
        logger.info(f"Set language to {language}")

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, value):
        if isinstance(value, str):
            if value not in self.SPEED_OPTIONS:
                raise ValueError(f"Invalid speed value. Use one of: {list(self.SPEED_OPTIONS.keys())}")
            self._speed = self.SPEED_OPTIONS[value]
        elif isinstance(value, (int, float)):
            if not -1 <= value <= 1:
                raise ValueError("Speed value must be between -1 and 1")
            self._speed = value
        else:
            raise ValueError("Speed must be a string from SPEED_OPTIONS or a number between -1 and 1")
        logger.info(f"Set speed to {self._speed}")

    def set_emotions(self, emotions: List[Dict[str, str]] = None):
        if emotions is None:
            self._emotions = {}
            logger.info("Cleared all emotions")
            return
            
        self._emotions = {}
        for emotion in emotions:
            name = emotion.get("name")
            level = emotion.get("level")
            
            if name not in self.EMOTION_NAMES:
                raise ValueError(f"Invalid emotion name. Choose from: {self.EMOTION_NAMES}")
            if level not in self.EMOTION_LEVELS:
                raise ValueError(f"Invalid emotion level. Choose from: {self.EMOTION_LEVELS}")
                
            self._emotions[name] = level
        
        logger.info(f"Set emotions: {self._emotions}")

    def _get_voice_controls(self):
        controls = {"speed": self._speed}
        
        if self._emotions:
            controls["emotion"] = [f"{name}:{level}" for name, level in self._emotions.items()]
            
        return controls

    def speak(self, text: str, output_file: str = None):
        if not self.current_model or not (self.current_voice or self.current_mix):
            raise ValueError("Please set a model and a voice or voice mix before speaking.")

        voice_embedding = self.current_voice['embedding'] if self.current_voice else self.current_mix

        improved_text = improve_tts_text(text, self.current_language)

        output_format = {
            "container": "wav",
            "encoding": "pcm_f32le",
            "sample_rate": 44100,
        }

        voice_controls = self._get_voice_controls()
        
        logger.info(f"Generating audio for text: {text[:50]}... with voice controls: {voice_controls}")
        if self.current_language == 'en':
            audio_data = self.client.tts.bytes(
                model_id='sonic-english',
                transcript=improved_text,
                voice_embedding=voice_embedding,
                duration=None,
                output_format=output_format,
                # language=self.current_language,
                _experimental_voice_controls=voice_controls
            )
        else:
            audio_data = self.client.tts.bytes(
            model_id='sonic-multilingual',
            transcript=improved_text,
            voice_embedding=voice_embedding,
            duration=None,
            output_format=output_format,
            language=self.current_language,
            _experimental_voice_controls=voice_controls)

        if output_file is None:
            output_file = f"output_{self.current_language}.wav"

        with open(output_file, "wb") as f:
            f.write(audio_data)
        logger.info(f"Audio saved to {output_file}")
        print(f"Audio generated and saved to {output_file}")

        return output_file

    def _get_embedding(self, source: Union[str, Dict]) -> Dict:
        """
        Получает эмбеддинг из различных источников: ID, путь к файлу или существующий эмбеддинг
        """
        if isinstance(source, dict) and 'embedding' in source:
            return source['embedding']
        elif isinstance(source, str):
            if os.path.isfile(source):
                # Если это путь к файлу, создаем новый эмбеддинг
                return self.client.voices.clone(filepath=source)
            else:
                # Если это ID, загружаем голос и возвращаем его эмбеддинг
                voice = self.load_voice(source)
                return voice['embedding']
        else:
            raise ValueError(f"Invalid source type: {type(source)}")

    def create_mixed_embedding(self, components: List[Dict[str, Union[str, float, Dict]]]) -> Dict:
        """
        Создает смешанный эмбеддинг из нескольких компонентов
        
        :param components: Список словарей, каждый содержит 'id' (или 'path', или эмбеддинг) и 'weight'
        :return: Новый смешанный эмбеддинг
        """
        mix_components = []
        for component in components:
            embedding = self._get_embedding(component.get('id') or component.get('path') or component)
            mix_components.append({
                "embedding": embedding,
                "weight": component['weight']
            })
        
        return self.client.voices.mix(mix_components)

    def create_custom_voice(self, name: str, source: Union[str, List[Dict]], description: str = "", language: str = "en"):
        """
        Создает кастомный голос из файла или смеси голосов
        
        :param name: Имя нового голоса
        :param source: Путь к файлу или список компонентов для смешивания
        :param description: Описание голоса
        :param language: Язык голоса
        :return: ID нового голоса
        """
        logger.info(f"Creating custom voice: {name}")
        
        if isinstance(source, str):
            # Если источник - строка, считаем это путем к файлу
            embedding = self.client.voices.clone(filepath=source)
        elif isinstance(source, list):
            # Если источник - список, создаем смешанный эмбеддинг
            embedding = self.create_mixed_embedding(source)
        else:
            raise ValueError("Invalid source type. Expected file path or list of components.")

        voice_id = f"custom_{len([f for f in self.custom_dir.glob('*.json')])}"
        
        voice_data = {
            "id": voice_id,
            "name": name,
            "description": description,
            "embedding": embedding,
            "language": language,
            "is_public": False,
            "is_custom": True
        }
        
        self._save_voice_to_custom(voice_data)
        self.voices[voice_id] = voice_data
        self.loaded_voices.add(voice_id)
        
        logger.info(f"Created custom voice with id: {voice_id}")
        return voice_id

    def get_voice_id_by_name(self, name: str) -> List[str]:
        matching_voices = []
        
        # Проверяем оба каталога
        for directory in [self.api_dir, self.custom_dir]:
            for file in directory.glob("*.json"):
                with open(file, "r") as f:
                    voice_data = json.load(f)
                    if voice_data['name'] == name:
                        matching_voices.append(voice_data['id'])
        
        if not matching_voices:
            logger.warning(f"No voices found with name: {name}")
        else:
            logger.info(f"Found {len(matching_voices)} voice(s) with name: {name}")
        
        return matching_voices

def improve_tts_text(text: str, language: str = 'en') -> str:
    text = re.sub(r'(\w+)(\s*)$', r'\1.\2', text)
    text = re.sub(r'(\w+)(\s*\n)', r'\1.\2', text)

    def format_date(match):
        date = datetime.strptime(match.group(), '%Y-%m-%d')
        return date.strftime('%m/%d/%Y')
    
    text = re.sub(r'\d{4}-\d{2}-\d{2}', format_date, text)
    text = text.replace(' - ', ' - - ')
    text = re.sub(r'\?(?![\s\n])', '??', text)
    text = text.replace('"', '')
    text = text.replace("'", '')
    text = re.sub(r'(https?://\S+|\S+@\S+\.\S+)\?', r'\1 ?', text)

    if language.lower() in ['ru', 'rus', 'russian']:
        text = text.replace('г.', 'году')
    elif language.lower() in ['fr', 'fra', 'french']:
        text = text.replace('M.', 'Monsieur')

    return text