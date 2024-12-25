import os
import json
from pathlib import Path
from typing import List, Dict, Union, Optional
from enum import Enum
from tqdm import tqdm
from loguru import logger
from datetime import datetime
import re
from dotenv import load_dotenv

try:
    from cartesia import Cartesia
except ImportError:
    Cartesia = None  # Handle the case where Cartesia is not installed


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
    EMOTION_LEVELS = ["lowest", "low", "omit", "high", "highest"]

    def __init__(self, api_key: str = None, base_dir: Path = None):
        # -----------------------------------------
        # 1. Загрузка .env и установка API-ключа
        # -----------------------------------------
        load_dotenv()
        self.api_key = api_key or os.environ.get("CARTESIA_API_KEY")
        
        # -----------------------------------------
        # 2. Попытка инициализации Cartesia клиента
        # -----------------------------------------
        if self.api_key and Cartesia:
            try:
                self.client = Cartesia(api_key=self.api_key)
                logger.info("Cartesia client initialized with API key.")
            except Exception as e:
                logger.error(f"Failed to initialize Cartesia client: {e}")
                self.client = None
        else:
            self.client = None
            if not self.api_key:
                logger.warning("API key not provided. Cartesia client is not initialized. Some features will be unavailable.")
            else:
                logger.warning("Cartesia library not available. Cartesia client is not initialized.")

        # -----------------------------------------
        # 3. Внутренние статусы (доступность API, генерация)
        # -----------------------------------------
        self._is_api_available = False
        self._can_generate = False
        self._last_check_datetime: Optional[datetime] = None

        # -----------------------------------------
        # 4. Основные поля и настройки
        # -----------------------------------------
        self.current_voice = None
        self.current_model = None
        self.current_language = None
        self.current_mix = None

        # Setting up directories
        self.base_dir = base_dir or Path("voice2voice")
        self.api_dir = self.base_dir / "api"
        self.custom_dir = self.base_dir / "custom"

        # Create necessary directories
        self.api_dir.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)

        # Initialize voices
        self.voices = {}
        self.loaded_voices = set()

        # Speed and emotion settings
        self._speed = 0.0  # normal speed
        self._emotions = {}

        logger.add("cartesia_voice_manager.log", rotation="10 MB")
        logger.info("CartesiaVoiceManager initialized")

        # -----------------------------------------
        # 5. После инициализации проверим статус
        # -----------------------------------------
        self.update_api_status()


    # =========================================================================
    #                       СВОЙСТВА / ГЕТТЕРЫ / СЕТТЕРЫ
    # =========================================================================

    @property
    def is_api_available(self) -> bool:
        """
        Возвращает флаг, указывающий, доступен ли API (валидный ключ, 
        можем ли получить список голосов).
        """
        return self._is_api_available

    @property
    def can_generate(self) -> bool:
        """
        Возвращает флаг, указывающий, можем ли мы генерировать аудио 
        (проверяем путём генерации короткого фрагмента).
        """
        return self._can_generate

    @property
    def last_check_datetime(self) -> Optional[str]:
        """
        Дата/время последней проверки статуса в виде строки (YYYY-MM-DD HH:MM:SS).
        Если статус не проверялся, вернёт None.
        """
        if self._last_check_datetime:
            return self._last_check_datetime.strftime('%Y-%m-%d %H:%M:%S')
        return None

    def set_api_key(self, api_key: str):
        """
        Устанавливает новый API-ключ, переинициализирует клиента и 
        обновляет статусы доступности.
        """
        logger.info(f"Setting a new API key: {api_key}")
        self.api_key = api_key
        
        if Cartesia:
            try:
                self.client = Cartesia(api_key=self.api_key)
                logger.info("Cartesia client re-initialized with new API key.")
                # Сохраняем ключ в .env (при желании)
                self._save_api_key_to_env()
            except Exception as e:
                logger.error(f"Failed to re-initialize Cartesia client with provided API key: {e}")
                self.client = None
        else:
            logger.error("Cartesia library is not available. Cannot initialize Cartesia client.")
            self.client = None

        # Обновим статусы
        self.update_api_status()

    def _save_api_key_to_env(self):
        """
        Сохраняет текущий API-ключ в .env файл (по желанию).
        """
        env_path = Path('.env')
        with open(env_path, 'w', encoding='utf-8') as env_file:
            env_file.write(f'CARTESIA_API_KEY={self.api_key}\n')
        logger.info("API key saved to .env file.")

    # Если потребуется base_url или иные настройки для Cartesia, 
    # аналогичным образом можно сделать set_base_url(...).


    # =========================================================================
    #                     ПРОВЕРКА ДОСТУПНОСТИ API / ГЕНЕРАЦИИ
    # =========================================================================

    def update_api_status(self):
        """
        Последовательно вызывает методы check_api_availability() и check_can_generate().
        Обновляет внутренние флаги и сохраняет дату последней проверки.
        """
        self._is_api_available = self.check_api_availability()
        self._can_generate = False
        if self._is_api_available:
            self._can_generate = self.check_can_generate()

        self._last_check_datetime = datetime.now()
        logger.info(f"API status updated: is_api_available={self._is_api_available}, "
                    f"can_generate={self._can_generate}, last_check={self.last_check_datetime}")

    def check_api_availability(self) -> bool:
        """
        Проверяем, что API-ключ рабочий, пытаясь получить список голосов.
        Если запрос успешно возвращает хотя бы один голос — считаем, что API доступен.
        Возвращает True или False.
        """
        if not self.client:
            logger.warning("No Cartesia client to check availability.")
            return False

        try:
            voices = self.client.voices.list()
            if voices:
                logger.info("API key is valid, voices retrieved successfully.")
                return True
            else:
                logger.warning("API key might be invalid or no voices returned.")
                return False
        except Exception as e:
            logger.error(f"Error checking API availability: {e}")
            return False

    def check_can_generate(self) -> bool:
        """
        Проверяем, можем ли мы генерировать аудио, 
        попробовав сгенерировать короткий фрагмент (1 символ).
        Если сгенерировали без исключений — True, иначе False.
        """
        if not self.client:
            logger.warning("No Cartesia client to check generation.")
            return False

        # Для теста нам нужно хотя бы какой-то embedding. 
        # Можно взять публичный голос (если есть) или любой voice_embedding.
        # Здесь для примера попробуем просто получить список, взять первый голос и сгенерировать 1 символ.
        try:
            voices = self.client.voices.list()
            if not voices:
                logger.warning("No voices found to test generation.")
                return False

            # Берём embedding первого голоса из списка
            # Полноценная инфа: voices.get(id=voice_id)
            test_voice_id = voices[0]['id']
            test_voice_data = self.client.voices.get(id=test_voice_id)
            test_embedding = test_voice_data['embedding']

            # Пробуем сгенерировать 1 символ (например, "A")
            test_audio = self.client.tts.bytes(
                model_id='sonic-english',         # допустим, английская модель
                transcript='A',                   # всего 1 символ
                voice_embedding=test_embedding,
                duration=None,
                output_format={
                    "container": "wav",
                    "encoding": "pcm_f32le",
                    "sample_rate": 44100,
                },
                # Доп. настройки не задаём, главное, что бы работало
            )
            if test_audio:
                logger.info("Successfully generated a short test audio — generation is available.")
                return True
            else:
                logger.warning("Test audio is empty — generation might not be available.")
                return False
        except Exception as e:
            logger.error(f"Error checking generation capability: {e}")
            return False

    def get_api_status(self) -> Dict[str, Union[bool, str]]:
        """
        Возвращает словарь с текущим статусом:
        {
            "is_api_available": bool,
            "can_generate": bool,
            "last_check": str или None
        }
        """
        return {
            "is_api_available": self._is_api_available,
            "can_generate": self._can_generate,
            "last_check": self.last_check_datetime
        }

    # =========================================================================
    #                ОСТАЛЬНЫЕ МЕТОДЫ КЛАССА (Не менялись)
    # =========================================================================
    def load_voice(self, voice_id: str) -> Dict:
        if voice_id in self.loaded_voices:
            return self.voices[voice_id]

        voice_file = None
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
            if self.client:
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
            else:
                logger.error(f"Cannot load voice {voice_id} without API client.")
                raise ValueError(f"Voice with id {voice_id} not found and API client is not available.")

    def extract_voice_id_from_label(self, voice_label: str) -> Optional[str]:
        choices = self.get_voice_choices()
        voice_data = next((c for c in choices if c["label"] == voice_label), None)
        return voice_data["value"] if voice_data else None

    def get_voice_choices(self, language: str = None, accessibility: VoiceAccessibility = VoiceAccessibility.ALL) -> List[Dict]:
        voices = self.list_available_voices(
            languages=[language] if language else None,
            accessibility=accessibility
        )
        choices = []
        for voice in voices:
            choices.append({
                "label": f"{voice['name']} ({voice['language']}){' [Custom]' if voice.get('is_custom') else ''}",
                "value": voice['id']
            })
        return sorted(choices, key=lambda x: x['label'])

    def get_voice_info(self, voice_id: str) -> Dict:
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
        if not self.client:
            logger.warning("Cannot update voices from API without API client.")
            return
        logger.info("Updating voices from API")
        try:
            api_voices = self.client.voices.list()
            for voice in tqdm(api_voices, desc="Updating voices"):
                voice_id = voice["id"]
                full_voice_data = self.client.voices.get(id=voice_id)
                self._save_voice_to_api(full_voice_data)
                if voice_id in self.loaded_voices:
                    self.voices[voice_id] = full_voice_data
            logger.info(f"Updated {len(api_voices)} voices from API")
        except Exception as e:
            logger.error(f"Failed to update voices from API: {e}")

    def list_available_voices(self, languages: List[str] = None, accessibility: VoiceAccessibility = VoiceAccessibility.ALL) -> List[Dict]:
        filtered_voices = []
        # API голоса
        if self.client and accessibility in [VoiceAccessibility.ALL, VoiceAccessibility.ONLY_PUBLIC]:
            try:
                api_voices = self.client.voices.list()
                for voice in api_voices:
                    metadata = {
                        'id': voice['id'],
                        'name': voice['name'],
                        'language': voice['language'],
                        'is_public': voice['is_public'],
                        'is_custom': False
                    }
                    if accessibility == VoiceAccessibility.ONLY_PUBLIC:
                        if metadata['is_public'] and not metadata.get('is_custom'):
                            if languages is None or metadata['language'] in languages:
                                filtered_voices.append(metadata)
                    else:  # VoiceAccessibility.ALL
                        if languages is None or metadata['language'] in languages:
                            filtered_voices.append(metadata)
            except Exception as e:
                logger.error(f"Failed to fetch voices from API: {e}")
        else:
            logger.warning("API client is not available. Skipping API voices.")
        # Custom голоса
        if accessibility in [VoiceAccessibility.ALL, VoiceAccessibility.ONLY_CUSTOM]:
            for file in self.custom_dir.glob("*.json"):
                with open(file, "r") as f:
                    voice_data = json.load(f)
                    if languages is None or voice_data['language'] in languages:
                        metadata = {
                            'id': voice_data['id'],
                            'name': voice_data['name'],
                            'language': voice_data['language'],
                            'is_public': False,
                            'is_custom': True
                        }
                        filtered_voices.append(metadata)
        # Приватные голоса (не публичные, но из API)
        if accessibility in [VoiceAccessibility.ALL, VoiceAccessibility.ONLY_PRIVATE] and self.client:
            try:
                api_voices = self.client.voices.list()
                for voice in api_voices:
                    if not voice['is_public'] and not voice.get('is_custom'):
                        metadata = {
                            'id': voice['id'],
                            'name': voice['name'],
                            'language': voice['language'],
                            'is_public': False,
                            'is_custom': False
                        }
                        if languages is None or metadata['language'] in languages:
                            filtered_voices.append(metadata)
            except Exception as e:
                logger.error(f"Failed to fetch private voices from API: {e}")
        logger.info(f"Found {len(filtered_voices)} voices matching criteria")
        return filtered_voices

    def set_voice(self, voice_id: str):
        voice_file = None
        api_file = self.api_dir / f"{voice_id}.json"
        custom_file = self.custom_dir / f"{voice_id}.json"

        if api_file.exists():
            voice_file = api_file
        elif custom_file.exists():
            voice_file = custom_file

        if voice_file:
            with open(voice_file, "r") as f:
                self.current_voice = json.load(f)
        else:
            if self.client:
                try:
                    voice_data = self.client.voices.get(id=voice_id)
                    self._save_voice_to_api(voice_data)
                    self.current_voice = voice_data
                except Exception as e:
                    logger.error(f"Failed to get voice {voice_id}: {e}")
                    raise ValueError(f"Voice with id {voice_id} not found")
            else:
                logger.error(f"Cannot set voice {voice_id} without API client.")
                raise ValueError(f"Voice with id {voice_id} not found and API client is not available.")

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
        if not self.client:
            logger.error("Cannot generate speech without API client.")
            raise ValueError("API client is not initialized. Cannot generate speech.")

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
                _experimental_voice_controls=voice_controls
            )

        if output_file is None:
            output_file = f"output_{self.current_language}.wav"

        with open(output_file, "wb") as f:
            f.write(audio_data)
        logger.info(f"Audio saved to {output_file}")
        print(f"Audio generated and saved to {output_file}")

        return output_file

    def _get_embedding(self, source: Union[str, Dict]) -> Dict:
        if isinstance(source, dict) and 'embedding' in source:
            return source['embedding']
        elif isinstance(source, str):
            if os.path.isfile(source):
                if not self.client:
                    logger.error("Cannot clone voice without API client.")
                    raise ValueError("API client is not initialized. Cannot clone voice.")
                return self.client.voices.clone(filepath=source)
            else:
                voice = self.load_voice(source)
                return voice['embedding']
        else:
            raise ValueError(f"Invalid source type: {type(source)}")

    def create_mixed_embedding(self, components: List[Dict[str, Union[str, float, Dict]]]) -> Dict:
        if not self.client:
            logger.error("Cannot create mixed embedding without API client.")
            raise ValueError("API client is not initialized. Cannot create mixed embedding.")

        mix_components = []
        for component in components:
            embedding = self._get_embedding(component.get('id') or component.get('path') or component)
            mix_components.append({
                "embedding": embedding,
                "weight": component['weight']
            })
        return self.client.voices.mix(mix_components)

    def create_custom_voice(self, name: str, source: Union[str, List[Dict]], description: str = "", language: str = "en"):
        logger.info(f"Creating custom voice: {name}")

        if isinstance(source, str):
            if not self.client:
                logger.error("Cannot clone voice without API client.")
                raise ValueError("API client is not initialized. Cannot clone voice.")
            embedding = self.client.voices.clone(filepath=source)
        elif isinstance(source, list):
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


def improve_tts_text(text: str) -> str:
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

    return text


# ============================================================================
# Пример использования
# ============================================================================
if __name__ == "__main__":
    manager = CartesiaVoiceManager()
    status = manager.get_api_status()
    print("Current API status:", status)

    # Пробуем задать новый ключ (вы можете ввести реальный ключ)
    manager.set_api_key("NEW_FAKE_KEY_123")
    print("Updated status:", manager.get_api_status())

    # Если всё хорошо, можете попробовать говорить (при условии, что есть голос)
    # manager.set_voice("some_voice_id")
    # manager.speak("Hello world", output_file="test.wav")
