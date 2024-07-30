import functools
import redis
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import (create_access_token, get_jwt_identity, jwt_required, get_jwt, create_refresh_token, unset_jwt_cookies)
from datetime import timedelta
from app.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')

jwt_redis_blocklist = redis.StrictRedis(
        host="localhost", port=6379, db=0, decode_responses=True
    )

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        error = None
        
        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
                return jsonify({'success' : {'username': username.lower()}}), 200
            except db.IntegrityError:
                error = 'Something went wrong, try again with new data!'
                return jsonify(error=error), 406
        else:
            return jsonify({'error' : error}), 404
    else:
        return jsonify({'error':'Something went wrong, try again with new data!'}), 405
    
    
@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()
        
        if not username:
            error = 'Username is required.'
            return jsonify({'error' : error}), 406
        elif not password:
            error = 'Password is required.'
            return jsonify({'error' : error}), 406
        
        if user is None:
            error = 'Incorrect username or password!'
            
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect username or password!'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            additional_claims = {"username": user['username']}
            access_token = create_access_token(identity=user['id'], additional_claims=additional_claims)
            refresh_token = create_refresh_token(identity=user['id'], additional_claims=additional_claims)
            return jsonify({"id": user['id'], "username": user['username'], "token": access_token, "refreshToken": refresh_token}), 200
        else:
            return jsonify({'error' : error}), 404

    else:
        return jsonify({'error':'Something went wrong, try again with new data!'}), 405
    
@bp.route('/getuser', methods=["POST"])
@jwt_required(verify_type=False)
def protected():
    current_user = get_jwt_identity()
    claims = get_jwt()
    return jsonify({"id":current_user, "username": claims['username'],  }), 200

@bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    print(identity)
    db = get_db()
    user = db.execute(
        'SELECT * FROM user WHERE id = ?', (identity,)
        ).fetchone()
    if user is None:
        return jsonify(error = 'User not found!'), 404
    additional_claims = {"username": user['username']}
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    jti = get_jwt()['jti']
    jwt_redis_blocklist.set(jti, "", ex=timedelta(hours=1))
    return jsonify({"token" : access_token, "id": identity, "username": additional_claims['username']}), 200

@bp.route("/logout", methods=["DELETE"])
@jwt_required(verify_type=False)
def logout():
    token = get_jwt()
    jti = token["jti"]
    ttype = token["type"]
    jwt_redis_blocklist.set(jti, "", ex=timedelta(hours=1))

    return jsonify(msg=f"{ttype.capitalize()} token successfully revoked"), 200