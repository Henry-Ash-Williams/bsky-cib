# Bluesky Co-ordinated Inauthentic Behaviour Detection Dashboard 

Developed by [@Henry-Ash-Williams](https://github.com/Henry-Ash-Williams) & [@Speaty](https://github.com/Speaty) for the Hacksussex 2025 Hackathon, as part of the CASM Technology track, "Clear skies ahead". 

#![bsky cib app](https://raw.githubusercontent.com/Henry-Ash-Williams/bsky-cib/refs/heads/master/assets/app.png)


## Getting Started 

- Install `uv` 

```sh
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```

- Clone The Repo

```sh
$ git clone https://github.com/Henry-Ash-Williams/bsky-cib/ && cd bsky-cib
```

- Install dependencies 

```sh
$ uv sync
```

- Activate environment 

```sh
$ source .venv/bin/activate 
```

- Run dashboard 

```
$ python main.py
```

- Navigate to `localhost:8050`