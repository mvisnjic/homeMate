import yt_dlp
import os
import re
import requests
import json

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)


def download_audio(url, output_dir='instance/Music'):
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
    print("action", message_dict)
    print(type(message_dict))
    json_message = message_dict
    print(type(json_message))
    action = json_message['action']
    print("handle_action", json_message)
    if action == 'toggle_relay':
        location = json_message['parameters']['location']
        print(json_message['action'])
        if location == 'kitchen':
            IOT_URL = os.getenv("IOT_URL") + f'/api/togglerelay?choice={json_message['parameters']['state']}&relay=1'
            return f'Kitchen relay state is: {json_message['parameters']['state']}! Can I help you with something else?'
        if location == 'badroom':
            IOT_URL = os.getenv("IOT_URL") + f'/api/togglerelay?choice={json_message['parameters']['state']}&relay=3'
            return f'Bedroom turned {json_message['parameters']['state']}! Can I help you with something else?!'
        if location == 'heating':
            IOT_URL = os.getenv("IOT_URL") + f'/api/togglerelay?choice={json_message['parameters']['state']}&relay=3'
            post = requests.post(IOT_URL)
            return f'Heater state is: {json_message['parameters']['state']}! Can I help you with something else?' 
        print(post)
    elif action == "get_weather":
        location = json_message['parameters']['location']
        IOT_URL = 'https://api.open-meteo.com/v1/forecast?latitude=44.86833&longitude=13.84806&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m'
        post = requests.get(IOT_URL)
        if post.status_code == 200:
            data_json = post.json()
            return f'Current weather in {location}: {data_json['current']}'
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