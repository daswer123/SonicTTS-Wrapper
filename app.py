from typing import List
import gradio as gr
from pathlib import Path
from sonic_api_wrapper import CartesiaVoiceManager, VoiceAccessibility, improve_tts_text
import os
import json

# Инициализация базовых переменных
DEFAULT_API_KEY = ""
LANGUAGE_CHOICES = ["all", "ru", "en", "es", "pl", "de", "fr"]
ACCESS_TYPE_MAP = {
    "Все": VoiceAccessibility.ALL,
    "Только кастомные": VoiceAccessibility.ONLY_CUSTOM,
    "Апи": VoiceAccessibility.ONLY_PUBLIC
}
# Обновленные константы
SPEED_CHOICES = ["Очень медленно", "Медленно", "Нормально", "Быстро", "Очень быстро"]
EMOTION_CHOICES = ["Нейтрально", "Весело", "Грустно", "Злобно", "Удивленно", "Любопытно"]
EMOTION_INTENSITY = ["Очень слабая", "Слабая", "Средняя", "Сильная", "Очень сильная"]

# Глобальная переменная для хранения экземпляра менеджера
manager = None

import datetime

def map_speed(speed_type: str) -> float:
    speed_map = {
        "Очень медленно": -1.0,
        "Медленно": -0.5,
        "Нормально": 0.0,
        "Быстро": 0.5,
        "Очень быстро": 1.0
    }
    return speed_map[speed_type]

def generate_output_filename(language: str) -> str:
    """Генерация имени файла с временной меткой и языком"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"output/{timestamp}_{language}.wav"

def extract_voice_id_from_label(voice_label: str) -> str:
    """
    Извлекает ID голоса из метки в dropdown
    Например: "John (en) [Custom]" -> извлечет ID из словаря голосов
    """
    if not manager:
        return None
        
    # Получаем все голоса и их метки
    choices = manager.get_voice_choices()
    # Находим голос по метке и берем его ID
    voice_data = next((c for c in choices if c["label"] == voice_label), None)
    return voice_data["value"] if voice_data else None

def initialize_manager(api_key: str) -> str:
    global manager
    try:
        manager = CartesiaVoiceManager(api_key=api_key, base_dir=Path("voice2voice"))
        return "✅ Менеджер инициализирован"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def get_initial_voices():
    """Получение начального списка голосов"""
    if not manager:
        initialize_manager(DEFAULT_API_KEY)
    choices = manager.get_voice_choices()
    return [c["label"] for c in choices], choices[0]["label"] if choices else None

def update_voice_list (language: str, access_type: str, current_voice: str = None):
    """
    Обновление списка голосов с сохранением текущего выбора
    """
    if not manager:
        return gr.update(choices=[], value=None), "❌ Менеджер не инициализирован"
    
    try:
        choices = manager.get_voice_choices(
            language=None if language == "all" else language,
            accessibility=ACCESS_TYPE_MAP[access_type]
        )
        
        # Преобразуем в список меток
        choice_labels = [c["label"] for c in choices]
        
        # Определяем значение для выбора
        if current_voice in choice_labels:
            # Сохраняем текущий выбор, если он доступен
            new_value = current_voice
        else:
            # Иначе берем первый доступный голос
            new_value = choice_labels[0] if choice_labels else None
            
        return gr.update(choices=choice_labels, value=new_value), "✅ Список голосов обновлен"
    except Exception as e:
        return gr.update(choices=[], value=None), f"❌ Ошибка: {str(e)}"

def update_voice_info(voice_label: str) -> str:
    """Обновление информации о голосе"""
    if not manager or not voice_label:
        return ""
    
    try:
        voice_id = extract_voice_id_from_label(voice_label)
        if not voice_id:
            return "❌ Голос не найден"
            
        info = manager.get_voice_info(voice_id)
        return (
            f"Имя: {info['name']}\n"
            f"Язык: {info['language']}\n"
            f"Тип: {'Кастомный' if info.get('is_custom') else 'API'}\n"
            f"ID: {info['id']}"
        )
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def create_custom_voice(name: str, language: str, audio_data: tuple) -> tuple:
    """
    Создание кастомного голоса и обновление списка голосов
    Возвращает: (статус, обновленный dropdown, информация о голосе)
    """
    if not manager:
        return "❌ Менеджер не инициализирован", gr.update(), ""
    
    if not name or not audio_data:
        return "❌ Необходимо указать имя и файл голоса", gr.update(), ""
    
    try:
        # Получаем путь к аудио файлу
        audio_path = audio_data[0] if isinstance(audio_data, tuple) else audio_data
        
        # Создаем голос
        voice_id = manager.create_custom_embedding(
            file_path=audio_path,
            name=name,
            language=language
        )
        
        print(voice_id)
        
        # Получаем обновленный список голосов
        choices = manager.get_voice_choices()
        choice_labels = [c["label"] for c in choices]
        
        # Находим метку для нового голоса
        new_voice_label = next(c["label"] for c in choices if c["value"] == voice_id)
        
        # Получаем информацию о новом голосе
        voice_info = manager.get_voice_info(voice_id)
        info_text = (
            f"Имя: {voice_info['name']}\n"
            f"Язык: {voice_info['language']}\n"
            f"Тип: Кастомный\n"
            f"ID: {voice_info['id']}"
        )
        
        return (
            f"✅ Создан кастомный голос: {voice_id}",
            gr.update(choices=choice_labels, value=new_voice_label),
            info_text
        )
        
    except Exception as e:
        return f"❌ Ошибка создания голоса: {str(e)}", gr.update(), ""

def on_auto_language_change(auto_language: bool):
    """Обработчик изменения галочки автоопределения языка"""
    return gr.update(visible=not auto_language)

def map_emotions(selected_emotions, intensity):
    emotion_map = {
        "Весело": "positivity",
        "Грустно": "sadness",
        "Злобно": "anger",
        "Удивленно": "surprise",
        "Любопытно": "curiosity"
    }
    
    intensity_map = {
        "Очень слабая": "lowest",
        "Слабая": "low",
        "Средняя": "medium",
        "Сильная": "high",
        "Очень сильная": "highest"
    }
    
    emotions = []
    for emotion in selected_emotions:
        if emotion == "Нейтрально":
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
    """Генерация речи с учетом настроек языка"""
    if not manager:
        return None, "❌ Менеджер не инициализирован"
    
    if not text or not voice_label:
        return None, "❌ Необходимо указать текст и голос"
    
    try:
        # Извлекаем ID голоса из метки
        voice_id = extract_voice_id_from_label(voice_label)
        if not voice_id:
            return None, "❌ Голос не найден"
            
        # Устанавливаем голос по ID
        manager.set_voice(voice_id)
        
        # Если автоопределение выключено, устанавливаем язык вручную
        if not auto_language:
            manager.set_language(manual_language)
        
        # В функции generate_speech обновите установку скорости:
        if use_custom_speed:
            manager.speed = custom_speed
        else:
            manager.speed = map_speed(speed_type)
        
        # Установка эмоций
        emotion_map = {
            "Нейтрально": None,
            "Весело": "positivity",
            "Грустно": "sadness",
            "Злобно": "anger",
            "Удивленно": "surprise",
            "Любопытно": "curiosity"
        }
        
        intensity_map = {
            "Слабая": "low",
            "Средняя": "medium",
            "Сильная": "high"
        }
        
        if emotions and emotions != ["Нейтрально"]:
            manager.set_emotions(map_emotions(emotions, emotion_intensity))
        else:
            manager.set_emotions()  # Сброс эмоций
        
        # Генерация имени файла
        output_file = generate_output_filename(
            manual_language if not auto_language else manager.current_language
        )
        
        # Создаем директорию для выходных файлов, если её нет
        os.makedirs("output", exist_ok=True)
        
        # Генерация речи
        output_path = manager.speak(
            text=text if not improve_text else improve_tts_text(text, manager.current_language),
            output_file=output_file
        )
        
        return output_path, "✅ Аудио сгенерировано успешно"
        
    except Exception as e:
        return None, f"❌ Ошибка генерации: {str(e)}"

# Создание интерфейса
with gr.Blocks() as demo:
    # API ключ
    cartesia_api_key = gr.Textbox(
        label="API ключ Cartesia",
        value=DEFAULT_API_KEY,
        type='password'
    )
    
    with gr.Row():
        # Левая колонка
        with gr.Column():
            cartesia_text = gr.TextArea(label="Текст")
            
            with gr.Accordion(label="Настройки", open=True):
                # Фильтры
                with gr.Accordion("Фильтры", open=True):
                    cartesia_setting_filter_lang = gr.Dropdown(
                        label="Язык",
                        choices=LANGUAGE_CHOICES,
                        value="all"
                    )
                    cartesia_setting_filter_type = gr.Dropdown(
                        label="Тип",
                        choices=ACCESS_TYPE_MAP,
                        value="Все"
                    )
                
                # Вкладки настроек
                with gr.Tab("Стандарт"):
                    cartesia_setting_voice_info = gr.Textbox(
                        label="Информация о голосе",
                        interactive=False
                    )
                    with gr.Row():
                        initial_choices, initial_value = get_initial_voices()
                        cartesia_setting_voice = gr.Dropdown(
                            label="Голос",
                            choices=initial_choices,
                            value=initial_value
                        )
                    cartesia_setting_voice_update = gr.Button("Обновить")
                    cartesia_setting_auto_language = gr.Checkbox(
                         label="Автоматически определять язык из голоса",
                         value=True
                     )
                    cartesia_setting_manual_language = gr.Dropdown(
                         label="Язык озвучки",
                         choices=["ru", "en", "es", "fr", "de", "pl", "it", "ja", "ko", "zh", "hi"],
                         value="en",
                         visible=False  # Изначально скрыт
                     )
                
                with gr.Tab("Кастомный"):
                    cartesia_setting_custom_name = gr.Textbox(label="Имя")
                    cartesia_setting_custom_lang = gr.Dropdown(
                        label="Язык",
                        choices=LANGUAGE_CHOICES[1:]  # Исключаем "all"
                    )
                    cartesia_setting_custom_voice = gr.Audio(label="Файл голоса",type='filepath')
                    cartesia_setting_custom_add = gr.Button("Добавить")
                
                # with gr.Tab("Микс"):
                #     cartesia_setting_custom_mix = gr.Dropdown(
                #         label="Выберите голоса",
                #         multiselect=True,
                #         choices=[]
                #     )
                #     cartesia_setting_custom_mix_update = gr.Button("Обновить")
                #     for i in range(5):
                #         setattr(
                #             demo,
                #             f'mix_voice_{i+1}',
                #             gr.Slider(
                #                 label=f"Голос {i+1}",
                #                 value=0.5,
                #                 minimum=0,
                #                 maximum=1,
                #                 step=0.01,
                #                 visible=False
                #             )
                #         )
            
            # Контроль эмоций
            with gr.Accordion(label="Контроль эмоций (Beta)", open=False):
                cartesia_emotions = gr.Dropdown(
                    label="Эмоции",
                    multiselect=True,
                    choices=EMOTION_CHOICES
                )
                cartesia_emotions_intensity = gr.Dropdown(
                    label="Интенсивность",
                    choices=EMOTION_INTENSITY,
                    value="Средняя"
                )
            
            # Настройки скорости
            with gr.Accordion("Скорость", open=True):
                cartesia_speed_speed = gr.Dropdown(
                    label="Скорость речи",
                    choices=SPEED_CHOICES,
                    value="Нормально"
                )
                cartesia_speed_speed_allow_custom = gr.Checkbox(
                    label="Использовать кастомное значение скорости"
                )
                cartesia_speed_speed_custom = gr.Slider(
                    label="Скорость",
                    value=0,
                    minimum=-1,
                    maximum=1,
                    step=0.1,
                    visible=False
                )
            
            cartesia_setting_improve_text = gr.Checkbox(
                label="Улучшить текст согласно рекомендациям",
                value=True
            )
        
        # Правая колонка
        with gr.Column():
            cartessia_status_bar = gr.Label(value="Статус")
            cartesia_output_audio = gr.Audio(
                label="Результат",
                interactive=False
            )
            cartesia_output_button = gr.Button("Генерация")
    
    # События
    cartesia_api_key.change(
        initialize_manager,
        inputs=[cartesia_api_key],
        outputs=[cartessia_status_bar]
    )
    
    cartesia_setting_filter_lang.change(
        update_voice_list,
        inputs=[
            cartesia_setting_filter_lang,
            cartesia_setting_filter_type,
            cartesia_setting_voice  # Передаем текущий выбор
        ],
        outputs=[cartesia_setting_voice, cartessia_status_bar]
    )

    cartesia_setting_filter_type.change(
        update_voice_list,
        inputs=[
            cartesia_setting_filter_lang,
            cartesia_setting_filter_type,
            cartesia_setting_voice  # Передаем текущий выбор
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
        inputs=[cartesia_setting_filter_lang, cartesia_setting_filter_type],
        outputs=[cartesia_setting_voice]
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
            cartesia_setting_voice,  # Обновляем dropdown
            cartesia_setting_voice_info  # Обновляем информацию о голосе
        ]
    )
    
    # Обновляем привязки событий
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

# Запуск приложения
if __name__ == "__main__":
    # Инициализация менеджера при запуске
    initialize_manager(DEFAULT_API_KEY)
    # Запуск интерфейса
    demo.launch()