import os
import redis
from flask import (
    Blueprint, request, session, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import (create_access_token, get_jwt_identity, jwt_required, get_jwt, create_refresh_token, unset_jwt_cookies)
from datetime import timedelta
from app.helpers.db import get_db
from dotenv import load_dotenv 
load_dotenv()

bp = Blueprint('auth', __name__, url_prefix='/auth')

jwt_redis_blocklist = redis.StrictRedis(
    host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0, decode_responses=True
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
                cursor = db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username.lower(), generate_password_hash(password)),
                )
                db.commit()
                return jsonify({'success' : {'registered_username': username.lower(), 'user_id': cursor.lastrowid}}), 200
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
            'SELECT * FROM user WHERE username = ? AND verified = 1', (username.lower(),)
        ).fetchone()
        
        if not username:
            error = 'Username is required.'
            return jsonify({'error' : error}), 406
        elif not password:
            error = 'Password is required.'
            return jsonify({'error' : error}), 406
        
        if user is None:
            error = 'Incorrect username/password or not verified!'
            return jsonify({'error' : error}), 406
            
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

@bp.route("/verify", methods=["POST"])
def verify():
    AUTH_HEADER=os.getenv("AUTH_HEADER")
    AUTH_VALUE=os.getenv("AUTH_VALUE")
    
    
    header = request.headers.get(AUTH_HEADER)
    user_id = request.form.get('user_id')
    db = get_db()
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 406
    
    if(header == AUTH_VALUE):
        
        try:
            db.execute(
                "UPDATE user SET verified = 1 WHERE id = ?",
                (user_id),
            )
            db.commit()
            return jsonify({'success' : {'verified_id': user_id}}), 200
        
        except db.IntegrityError:
            error = 'Something went wrong, try again with new data!'
            return jsonify(error=error), 406
        
    return jsonify(error = 'User not verified!'), 401