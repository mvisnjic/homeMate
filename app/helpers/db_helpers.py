from .db import get_db
from flask import (jsonify)

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

def get_username(user_id):
    db = get_db()
    
    try:
        cur = db.execute('SELECT username FROM user WHERE id = ?', (user_id,))
        print(cur)
    except db.Error:
        db.rollback()
        error = 'Something went wrong, saving into a DB!'
        # return jsonify(error=error), 406
        
    return cur[0] if cur else 'no-name'
