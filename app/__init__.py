import os
from dotenv import load_dotenv 
import redis
from flask import (Flask)
from flask_jwt_extended import (JWTManager)
from flask_cors import CORS

load_dotenv()


def create_app(test_config=None):
    
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)
    
    jwt = JWTManager(app)
    
    # Setup our redis connection for storing the blocklisted tokens. You will probably
    # want your redis instance configured to persist data to disk, so that a restart
    # does not cause your application to forget that a JWT was revoked.
    jwt_redis_blocklist = redis.StrictRedis(
        host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), password=os.getenv('REDIS_PASSWORD'), db=0, decode_responses=True
    )


    # Callback function to check if a JWT exists in the redis blocklist
    @jwt.token_in_blocklist_loader
    def check_if_token_is_revoked(jwt_header, jwt_payload: dict):
        jti = jwt_payload["jti"]
        token_in_redis = jwt_redis_blocklist.get(jti)
        return token_in_redis is not None
     
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'homemate.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    try:
        os.makedirs(f'{app.instance_path}/Music')
    except OSError:
        pass
    try:
        os.makedirs(f'{app.instance_path}/upload_folder')
    except OSError:
        pass

    from .helpers import db
    db.init_app(app)
    
    from . import auth
    app.register_blueprint(auth.bp)
    
    from . import chat
    app.register_blueprint(chat.bp)

    return app