# Delibot

**Es un simple bot para discord**

## Primera etapa:

Minimo posible para connect with a simple test bot response

## Tools:

**discord.py**

[Disord.py](https://discordpy.readthedocs.io/en/stable/)


**Debian Requirements**

```bash
sudo apt install libffi-dev libnacl-dev python3-dev
```

### Usage:

```
python -m app.main
```

## Notas de desarrollo:
Este es el primer proyecto que uso  
```python
from __future__ import annotations
```
Me permite hacer una declaracion mas claras

**Without annotations Module**
```python
# app/core/example_no_types.py

import json
from pathlib import Path

def load_config(path):
    """Lee un JSON y devuelve un dict con opciones."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)  # ¿qué claves/valores trae?

def fetch_allowed_channels(cfg):
    """Devuelve canales permitidos (ids)."""
    # ¿lista de int? ¿de str?
    return cfg.get("allowed_channels", [])

class Message:
    def __init__(self, content, author_id, reply_to=None):
        self.content = content     # ¿str?
        self.author_id = author_id # ¿int? ¿str?
        self.reply_to = reply_to   # ¿Message o id?

def format_reply(msg, prefix="> "):
    """Formatea una respuesta."""
    base = f"{prefix}{msg.content}"
    if msg.reply_to:
        base += f"\n(in reply to {msg.reply_to.author_id})"
    return base

```

**With annotations Module**
```python
# app/core/example_with_types.py
from __future__ import annotations

import json
from pathlib import Path
from typing import NewType, TypedDict, Literal

# Tipos semánticos
UserID = NewType("UserID", int)
ChannelID = NewType("ChannelID", int)
Command = Literal["ping", "help", "about"]

# Estructura de config documentada por tipos
class Config(TypedDict, total=False):
    token: str
    prefix: str
    allowed_channels: list[ChannelID]

def load_config(path: Path) -> Config:
    """Lee un JSON y devuelve Config bien tipado."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # conversión segura a tipos esperados (ejemplo simple):
    allowed = [ChannelID(int(x)) for x in data.get("allowed_channels", [])]
    return {
        "token": str(data["token"]),
        "prefix": str(data.get("prefix", "!")),
        "allowed_channels": allowed,
    }

def fetch_allowed_channels(cfg: Config) -> list[ChannelID]:
    """Lista de canales permitidos (ChannelID)."""
    return cfg.get("allowed_channels", [])

class Message:
    def __init__(self, content: str, author_id: UserID, reply_to: Message | None = None) -> None:
        self.content: str = content
        self.author_id: UserID = author_id
        self.reply_to: Message | None = reply_to  # forward ref sin comillas

def format_reply(msg: Message, prefix: str = "> ") -> str:
    """Formatea una respuesta legible para el bot."""
    base = f"{prefix}{msg.content}"
    if msg.reply_to is not None:
        base += f"\n(in reply to {int(msg.reply_to.author_id)})"
    return base

```

* Config deja de ser “un dict cualquiera” y pasa a un TypedDict explícito.
* IDs se vuelven tipos semánticos (UserID, ChannelID) en vez de “int sueltos”.
* Retornos claros: sabes que fetch_allowed_channels devuelve list[ChannelID].
* Forward refs limpios (Message | None) gracias a from __future__ import annotations.
* Los linters/type checkers te avisan si pasas, por ejemplo, una str donde va un UserID.
