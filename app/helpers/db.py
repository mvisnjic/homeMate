import sqlite3

import click
from flask import current_app, g, jsonify

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()
        
def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

def save_message_to_db(chat_id, user_id, message):
    
    try:
        db = get_db()
        db.execute('INSERT INTO chat_line (chat_id, user_id, line_text) VALUES (?, ?, ?)', (chat_id, user_id, message))
        db.commit()
        current_app.logger.info(f'Saved chat into a DB. {chat_id}, {user_id}')
        return jsonify({'success' : {'chat_id': chat_id, 'user_id': user_id, 'message': message}}), 200
    except db.Error:
        db.rollback()
        error = 'Something went wrong, saving into a DB!'
        current_app.logger.error(error)
        return jsonify(error=error), 406
        

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')
    
def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)