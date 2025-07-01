import yt_dlp
import os
import re
import requests
import json
import pymupdf
from io import BytesIO
from flask import current_app

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)


def download_audio(url, output_dir='instance/Music'):
    """Function for downloading from a yt

    Args:
        url (string): url
        output_dir (str, optional): string. Defaults to 'instance/Music'.

    Returns:
        string: Filename
    """
    current_app.logger.info(f'Downloading audio file from {url}')
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        title = sanitize_filename(info.get("title", "audio"))
    
    output_path = os.path.join(output_dir, f"{title}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    current_app.logger.info(f'Downloaded file {title}')
    return f"{title}.mp3"


def extract_json_from_text(text):
    matches = re.findall(r'{[\s\S]*}', text)
    for match in matches:
        try:
            parsed = json.loads(match)
            if "action" in parsed and "parameters" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue
        

    return None

def handle_action(message_dict):
    """Function for handling an user action.

    Args:
        message_dict (dict): 

    Returns:
        string: Response of handled actions
    """
    json_message = message_dict
    action = json_message['action']
    current_app.logger.info(f'action, {action}')
    current_app.logger.info(f'handle_action, {json_message}')
    if action == 'toggle_relay':
        location = json_message['parameters']['location']
        state = json_message['parameters']['state']
        if location == 'kitchen':
            IOT_URL = os.getenv("IOT_URL") + f'/api/togglerelay?choice={state}&relay=3'
            return f"Kitchen relay state is: {state}! Can I help you with something else?"
        if location == 'badroom':
            IOT_URL = os.getenv("IOT_URL") + f'/api/togglerelay?choice={state}&relay=3'
            return f"Bedroom turned {state}! Can I help you with something else?!"
        if location == 'heating':
            IOT_URL = os.getenv("IOT_URL") + f'/api/togglerelay?choice={state}&relay=3'
            post = requests.post(IOT_URL)
            return f'Heater state is: {state}! Can I help you with something else?' 
    elif action == "get_weather":
        location = json_message['parameters']['location']
        IOT_URL = 'https://api.open-meteo.com/v1/forecast?latitude=44.86833&longitude=13.84806&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m'
        post = requests.get(IOT_URL)
        if post.status_code == 200:
            data_json = post.json()
            if data_json:
                curr_weather_dict = data_json['current']
                return f'Current weather in {location}: {curr_weather_dict}'
        else: 
            return 'Request status code is not success. Try again later.'
    elif action == "play_music":
        filename = json_message['parameters']['filename']
        return f'Not implemented. Click play button instead to play {filename}.'
    elif action == "download_music":
        url = json_message['parameters']['url']
        download = download_audio(str(url))
        if download:
            return f'File {download} downloaded successfully!'
        return 'Something went wrong while downloading...'
    return 'Not found action...'

def chunk_text(text, chunk_size=1000):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def analyze_pdf_text_in_chunks(file, task):
    """Function for analyze text and separated into chunks.

    Args:
        file (file): .pdf file type
        task (string): user input from chat

    Returns:
        string | list: response as a string or a list of responses
    """
    stream = BytesIO(file.read())
    current_app.logger.info(f'reading file, {file}')
    doc = pymupdf.open(stream=stream, filetype='pdf') 
    for page in doc:
        text = page.get_text()
    text = "\n".join([page.get_text() for page in doc])
    chunks = chunk_text(text, 2000)
    current_app.logger.info(f'Chunks: {chunks}')
    results = []
    for i, chunk in enumerate(chunks):
        prompt = f"{task}:\n\n{chunk}"
        current_app.logger.info(f'Asking with new prompt: {prompt}')
        res = requests.post(
            os.getenv("GEMMA_URL") + "/api/generate",
            json={"model": "homeMate-model", "prompt": prompt, "stream": False}
        )
        response = res.json().get("response", "")
        results.append(response.strip())
        current_app.logger.info(f'Success message: {response.strip()}')
        return response # only 2000 char

    return results
