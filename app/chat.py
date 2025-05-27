import redis
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify, Response, stream_with_context, send_from_directory, current_app
)
from werkzeug.utils import secure_filename
from flask_jwt_extended import (create_access_token, get_jwt_identity, jwt_required, get_jwt, create_refresh_token, unset_jwt_cookies)
import math
import os
import requests
import json
import sys
from dotenv import load_dotenv
from app.helpers.db import get_db
from app.helpers.db_helpers import save_message_to_db
import re
from .helpers.chat_helpers import download_audio, extract_json_from_text, handle_action
import pymupdf
from io import BytesIO

load_dotenv()
 
bp = Blueprint('chat', __name__, url_prefix='/chat')


@bp.route('/loadmodel', methods=["POST"])
@jwt_required(verify_type=False)
def loadmodel():
    data = request.get_json()
    GEMMA_URL = os.getenv("GEMMA_URL") + '/api/chat'
    model = data.get('model', None)
    if model is None:
        return jsonify({'error': 'model is required'}), 406
    
    gemma_response = requests.post(GEMMA_URL, json=data)
    return Response(gemma_response, content_type='application/json')

@bp.route('/generate', methods=["POST"])
@jwt_required(verify_type=False)
def generate():
    data = request.get_json()
    GEMMA_URL = os.getenv("GEMMA_URL") + '/api/chat'
    db = get_db()
    user_id = data.get('user_id', None)
    user_username = data.get('username', None)
    chat_id = data.get('chat_id', None)
    user_message = data.get('user_message', None)
    request_messages = data.get('messages', None)
    model = data.get('model', None)
    messages = []
    for message in request_messages:
        messages.append({'content': message['content'], 'role': message['role']})
        if(len(messages) == 15):
            break
    print(messages)
    if user_id is None:
        return jsonify(error='user_id is required.'), 406
    if user_message is None:
        return jsonify(error='user_message is required.'), 406
    if len(user_message) > 1000:
        return jsonify(error='user_message is too large. 1000 char max.'), 413
    
    json_object = {
    "model": model,
    "messages": messages,
    "stream": True
    }

    if chat_id is None:
        chat_response = create_chat()
        chat_id = chat_response[0].get_json().get('chat_id')
        print(chat_id)
    gemma_response = requests.post(GEMMA_URL, json=json_object, stream=True)
    message = ""
    
    db = get_db()

    @stream_with_context
    def stream():
        nonlocal message
        for chunk in gemma_response.iter_lines():
            if chunk:
                decoded_chunk = chunk.decode('utf-8')
                try:
                    json_data = json.loads(decoded_chunk)
                    
                    if 'message' in json_data and 'content' in json_data['message']:
                        message_content = json_data['message']['content']
                        message += message_content
                    if "action" in message and "parameters" in message:
                        extracted = extract_json_from_text(message)

                        if extracted:
                            message = handle_action(extracted)
                            json_data['message']['content'] = message
                    yield jsonify({'chat_id': chat_id, 'response': message_content, 'json': json_data}).get_data(as_text=True) + '\n'
                
                except json.JSONDecodeError:
                    continue
                except requests.exceptions.ConnectionError:
                    message = 'ERROR: There is no connection with IOT server.'
        
        json_data['message']['content'] = message
        yield jsonify({'chat_id': chat_id, 'done': True, "json_data": json_data}).get_data(as_text=True) + '\n'

        homemate_id = db.execute(
            'SELECT id FROM user WHERE username = ? AND verified = 0', ('homemate',)
        ).fetchone()
        
        if homemate_id and user_id:
            save_message_to_db(chat_id, user_id, user_message)
            save_message_to_db(chat_id, homemate_id['id'], message)

    return Response(stream(), content_type='application/json')


@bp.route('/music/list')
def list_music():
    files = [f for f in os.listdir(f'{current_app.instance_path}/Music') if f.endswith('.mp3')]
    return jsonify(files)

@bp.route('/music/<filename>')
def serve_music(filename):
    return send_from_directory(f'{current_app.instance_path}/Music', f'{filename}')

# @bp.route('/analyze_pdf_direct', methods=["POST"])
# def analyze_pdf_direct():
#     file = request.files['file']
#     stream = BytesIO(file.read())
#     doc = pymupdf.open(stream=stream, filetype='pdf') # open a document
#     for page in doc: # iterate the document pages
#         text = page.get_text()
#     text = "\n".join([page.get_text() for page in doc])
    
#     task = 'sum_total_due'
#     summaries = analyze_pdf_text_in_chunks(text, task)
#     if task == "summarize":
#         final = final_summary_from_chunks(summaries)
#         return jsonify({"sum_total_due": final})
#     else:
#         return jsonify({"results": summaries})

# def chunk_text(text, chunk_size=1000):
#     return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

# def analyze_pdf_text_in_chunks(text, task):
#     chunks = chunk_text(text, 2000)
#     results = []
#     print("no of CHUNKS", len(chunks))
#     for i, chunk in enumerate(chunks):
#         if task == "sum_total_due":
#             print('sum task')
#             prompt = f"Can you sum all total amount values from all pages::\n\n{chunk}"
#         elif task == "summarize":
#             prompt = f"Summarize this part of the document:\n\n{chunk}"
#         else:
#             prompt = f"Analyze this part of the PDF:\n\n{chunk}"
#         print(prompt)
#         res = requests.post(
#             os.getenv("GEMMA_URL") + "/api/generate",
#             json={"model": "homeMate-model", "prompt": prompt, "stream": False}
#         )
#         print("res", res)
#         response = res.json().get("response", "")
#         print(response)
#         results.append(response.strip())
#         if "total" in response or "amount" in response:
#             return response

    # return results

# def final_summary_from_chunks(summaries):
#     full_summary_prompt = "Combine and summarize these parts:\n\n" + "\n\n".join(summaries)
    
#     res = requests.post(
#         os.getenv("GEMMA_URL") + "/api/generate",
#         json={"model": "homeMate-model", "prompt": full_summary_prompt, "stream": False}
#     )
#     return res.json().get("response", "")


# @bp.route('/upload_pdf', methods=["POST"])
# def upload_pdf():
#     if 'file' not in request.files:
#         return jsonify({"error": "No file part"}), 400

#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({"error": "No selected file"}), 400
#     if file.mimetype != 'application/pdf':
#         return jsonify({"error": "Invalid file type. Only PDFs are allowed."}), 400

#     file_id = request.form.get('file_id', 'temp.pdf')
#     save_path = os.path.join(current_app.instance_path, 'upload_folder', file_id)
#     file.save(save_path)
#     return jsonify({"status": "uploaded", "file_id": file_id})
            
@bp.route('/create', methods=["POST"])
@jwt_required(verify_type=False)
def create_chat():
    if request.method == 'POST':
        data = request.get_json()
        chat_name = data.get('chat_name', data.get('user_message'))
        user_id_param = data.get('user_id', None)
        
        db = get_db()
        error = None
        
        if not chat_name:
            chat_name = 'default-name-chat'
        if not user_id_param:
            error = 'user_id is required.'
            return jsonify(error=error), 406
        
        if error is None:
            try:
                create_chat = db.execute('''INSERT INTO chat (name, created_by) VALUES 
                                         (?, (SELECT id FROM user WHERE user.id = ?))''', (chat_name,user_id_param,))
                chat_id = create_chat.lastrowid
                if(chat_id):
                    return jsonify({'chat_id': chat_id, 'created_by': user_id_param}), 200
                    
            except db.IntegrityError:
                db.rollback()
                error = 'Something went wrong, while creating a chat_id!'
                return jsonify(error=error), 406
        else:
            return jsonify({'error' : error}), 404    
    else:
        return jsonify({'error':'Something went wrong, try again with new data!'}), 405
    

@bp.route('/getchats', methods=["POST"])
@jwt_required(verify_type=False)
def get_chats():
    if request.method == 'POST':
        current_user_id = get_jwt_identity()
        
        db = get_db()
        error = None
        
        try:
            cursor = db.execute('''SELECT id, name, created_by FROM chat
                                WHERE created_by = ?
                                ORDER BY chat.id DESC''', (current_user_id,))
            rows = cursor.fetchall()
            
            if not rows:
                return jsonify({'error': 'No chats found for this account.'}), 404
            
            chats = []
            
            for row in rows:
                chats.append({
                    'id': row['id'],
                    'name': row['name'],
                    'created_by': row['created_by']
                })

            return jsonify({'chats': chats}), 200  
        except db.Error:
            error = 'Something went wrong with a DB!'
            return jsonify(error=error), 406
    else:
        return jsonify({'error':'Something went wrong, try again with new data!'}), 405

@bp.route('/getmessages', methods=["POST"])
@jwt_required(verify_type=False)
def get_messages():
    if request.method == 'POST':
        data = request.get_json()
        current_user_id = get_jwt_identity()
        
        
        chat_id = data.get('chat_id', None)
        page = data.get('page', None)
        per_page = data.get('per_page', None)
        
        
        db = get_db()
        error = None
        
        if not chat_id:
            error = 'chat_id is required.'
            return jsonify(error=error), 406
        if not per_page:
            error = 'per_page is required.'
            return jsonify(error=error), 406
            
        try:
            cursor_number_of_rows = db.execute('''SELECT COUNT(cl.id)  FROM chat_line cl 
                                    INNER JOIN chat c ON c.id = cl.chat_id
                                    WHERE c.created_by = ? AND chat_id = ?''', (current_user_id, chat_id))
            total_count = cursor_number_of_rows.fetchone()[0]
            print(total_count)
            total_pages = (total_count / per_page)
            total_pages = math.ceil(total_pages)

            offset = (total_pages - 1) * per_page
            if(page):
                offset = (page - 1) * per_page
            else:
                page = total_pages
            
            offset = math.ceil(offset)
            print('total pages', total_pages, 'offset', offset, 'per_page', per_page, 'page', page)
            cursor = db.execute('''SELECT cl.*, user.username, c.created_by FROM chat_line cl 
                                INNER JOIN user ON user.id = cl.user_id
                                INNER JOIN chat c ON c.id = cl.chat_id
                                WHERE c.created_by = ? AND chat_id = ?
                                LIMIT ? OFFSET ?''', (current_user_id, chat_id, per_page, offset))
            rows = cursor.fetchall()
            
            if not rows:
                return jsonify({'error': 'No messages found for this chat ID'}), 404
            
            messages = []
            for row in rows:
                messages.append({
                    'line_text_id': row['id'],
                    'user_id': row['user_id'],
                    'sender_username': row['username'],
                    'role': 'user' if current_user_id == row['user_id'] else 'assistant',
                    'created_at': row['created_at'],
                    'created_by': row['created_by'],
                    'content': row['line_text']
                })

            return jsonify({'chat_id': chat_id, 'messages': messages, 'pagination': {'total_pages': total_pages, 'current_page': page, 'total_messages': total_count, 'page': page}}), 200  
        except db.Error:
            error = 'Something went wrong with a DB!'
            return jsonify(error=error), 406
    else:
        return jsonify({'error':'Something went wrong, try again with new data!'}), 405


@bp.route('/delete', methods=["DELETE"])
@jwt_required(verify_type=False)
def delete_chat():
    if request.method == 'DELETE':
        current_user_id = get_jwt_identity()
        print(current_user_id)
        data = request.get_json()
        print(request)
        chat_id = data.get('chat_id', None)
        print(chat_id)
        db = get_db()
        error = None
        
        try:
            cursor = db.execute('''DELETE FROM chat
                        WHERE created_by = ? AND id = ?''', (current_user_id, chat_id,))
            
            
            if(cursor.rowcount > 0):
                db.commit()
                return jsonify({'deleted': {"chat_id": chat_id}}), 200  
            
            return jsonify({"error": 'not found'}), 404

        except db.Error:
            db.rollback()
            error = 'Something went wrong with a DB!'
            return jsonify(error=error), 406
    else:
        return jsonify({'error':'Something went wrong, try again with new data!'}), 405