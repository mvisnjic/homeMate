# homeMate - AI Home Assistant

_flask API backend that interacts with a Ollama API._

Link to frontend: https://github.com/mvisnjic/homeMate-frontend/tree/it

## Organization

[Juraj Dobrila University in Pula](https://www.unipu.hr/)

[Faculty of Informatics in Pula](https://fipu.unipu.hr/fipu)

Menthor: [doc. dr. sc. Nikola Tanković](https://fipu.unipu.hr/fipu/nikola.tankovic)

## Docker - that's all!

1. Create instance/config.py

- this is example

```
from datetime import timedelta
import os

TESTING=True
JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=30)
JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=15)
JWT_SECRET_KEY="something"
JWT_BLACKLIST_ENABLED=True
JWT_BLACKLIST_TOKEN_CHECKS=['access']
DATABASE=os.path.join('./instance', example-db-name)
```

2. Copy and modify .env

```
cp .env.example .env
```

4. Docker!

```
sudo docker compose up --build
```
