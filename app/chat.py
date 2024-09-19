import redis
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify, Response, stream_with_context
)
from flask_jwt_extended import (create_access_token, get_jwt_identity, jwt_required, get_jwt, create_refresh_token, unset_jwt_cookies)
import math
import os
import requests
import json
from dotenv import load_dotenv
from app.db import get_db

load_dotenv()
 
bp = Blueprint('chat', __name__, url_prefix='/chat')


def save_message_to_db(chat_id, user_id, message):
    db = get_db()
    
    try:
        db.execute('INSERT INTO chat_line (chat_id, user_id, line_text) VALUES (?, ?, ?)', (chat_id, user_id, message))
    except db.Error:
        db.rollback()
        error = 'Something went wrong, saving into a DB!'
        return jsonify(error=error), 406
        
    db.commit()
    
    return jsonify({'success' : {'chat_id': chat_id, 'user_id': user_id, 'message': message}}), 200


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

    user_id = data.get('user_id', None)
    chat_id = data.get('chat_id', None)
    user_message = data.get('user_message', None)
    request_messages = data.get('messages', None)
    model = data.get('model', None)
    messages = []
    for message in request_messages:
        messages.append({'content': message['content'], 'role': message['role']})
        if(len(messages) == 11):
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
        "messages": messages
    }
    if chat_id is None:
        chat_response = create_chat()
        chat_id = chat_response[0].get_json().get('chat_id')
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
                        yield jsonify({'chat_id': chat_id, 'response': message_content, 'json': json_data}).get_data(as_text=True) + '\n'
                
                except json.JSONDecodeError:
                    continue
        
        json_data['message']['content'] = message
        yield jsonify({'chat_id': chat_id, 'done': True, "json_data": json_data}).get_data(as_text=True) + '\n'

        homemate_id = db.execute(
            'SELECT id FROM user WHERE username = ? AND verified = 0', ('homemate',)
        ).fetchone()
        
        if homemate_id and user_id:
            save_message_to_db(chat_id, user_id, user_message)
            save_message_to_db(chat_id, homemate_id['id'], message)

    return Response(stream(), content_type='application/json')


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
    
# @bp.route('/send', methods=["POST"])
# @jwt_required(verify_type=False)
# def save_message():
#     if request.method == 'POST':
#         user_id = request.form.get('user_id')
#         message = request.form.get('message')
#         chat_id = request.form.get('chat_id')
        
#         db = get_db()
#         error = None
        
#         if not user_id:
#             error = 'user_id is required..'
#             return jsonify(error=error), 406
#         if not message or message == '':
#             error = 'message is required..'
#             return jsonify(error=error), 406
#         if not chat_id:
#             error = 'chat_id is required..'
#             return jsonify(error=error), 406
        
#         user_id = int(user_id)
#         chat_id = int(chat_id)
    
#         try:
#             db.execute('INSERT INTO chat_line (chat_id, user_id, line_text) VALUES (?, ?, ?)', (chat_id, user_id, message))
#         except db.Error:
#             db.rollback()
#             error = 'Something went wrong, while creating a chat!'
#             return jsonify(error=error), 406
        
#         db.commit()
#         return jsonify({'success' : {'chat_id': chat_id, 'user_id': user_id, 'message': message}}), 200
#     else:
#         return jsonify({'error':'Something went wrong, try again with new data!'}), 405

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
            print('total pages', total_pages, 'offset', offset, 'per_page', per_page)
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

            return jsonify({'chat_id': chat_id, 'messages': messages, 'pagination': {'total_pages': total_pages, 'current_page': page}}), 200  
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