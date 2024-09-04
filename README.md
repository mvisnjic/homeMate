# homeMate - AI Home Assistant

homeMate is an assistant to help users to maintain their households. Easy to use via chat.

_The idea is also to use it with voice commands_

## Functionalities

With homeMate you can:

- [ ] interact with IoT devices
- [ ] tasks
- [ ] grocery list
- [ ] fridge monitoring
- [ ] recipes ideas
- [ ] alarms and reminders
- [ ] information (news, temperature, etc.)
- [ ] download & play music

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
