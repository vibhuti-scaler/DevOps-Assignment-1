# Task 1 — three containers across three networks

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

Three containers, three user-defined bridge networks, and the **backend attached to two** of them.

```text
        host :8081
            |
    +---- public_net ----+
    |     frontend       |
    +--------------------+
            |
    +----- app_net ------+        frontend  -> public_net, app_net
    | frontend   backend |        backend   -> app_net, data_net   <-- two networks
    +--------------------+        database  -> data_net
            |
    +----- data_net -----+
    |  backend  database |
    +--------------------+
```

| Container | Image | Networks | Published |
| --- | --- | --- | --- |
| `frontend` | `nginx:1.27-alpine` | `public_net`, `app_net` | `8081:80` |
| `backend` | `nginx:1.27-alpine` | **`app_net`, `data_net`** | — |
| `database` | `mysql:8.4` | `data_net` | — |

Each network has a job: `public_net` is the edge where the published port lives, `app_net` carries
frontend-to-backend traffic, and `data_net` is the only way to reach the database. Because the
frontend and the database share no network, the frontend **cannot** reach the database at all. That
isolation is the reason for splitting the tiers rather than putting everything on one network.

## Run it

```bash
cp .env.example .env      # then set a throwaway password in .env
./network-lab.sh
```

[`network-lab.sh`](network-lab.sh) uses plain `docker` commands, as the homework asks. The key ones:

```bash
docker network create public_net
docker network create app_net
docker network create data_net

docker run -d --name database --network data_net \
  -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD" -e MYSQL_DATABASE=homework mysql:8.4
docker run -d --name backend  --network app_net    nginx:1.27-alpine
docker run -d --name frontend --network public_net -p 8081:80 nginx:1.27-alpine

# a container can only be given one network with `docker run`,
# so the second one is attached afterwards
docker network connect data_net backend
docker network connect app_net  frontend
```

## Connectivity results

| Check | Command | Expected | Result |
| --- | --- | --- | --- |
| frontend → backend | `docker exec frontend wget -qO- http://backend/` | works | returned the backend page |
| backend → database | `docker exec backend nc -z -w 3 database 3306` | works | `database` resolved to `172.21.0.2`, port 3306 open |
| frontend → database | `docker exec frontend getent hosts database` | **fails** | no DNS record returned |

The third row is the important one. Docker's embedded DNS only answers for containers that share a
network with the one asking, so the frontend gets no record for `database` at all — the request
fails at name resolution, before any packet is sent.

Final membership, straight from `docker network inspect`:

```text
public_net  : frontend
app_net     : backend frontend
data_net    : backend database
```

![Frontend served on port 8081](../screenshots/01-frontend-8081.png)

## A Docker Desktop quirk worth knowing

Step 4d — fetching the published page from the host — is wrapped in a retry loop in
[`network-lab.sh`](network-lab.sh), because on Docker Desktop it is not always immediately
available after the container starts.

While re-running these labs I also hit a heavier version of the same thing: after a lot of
container churn, **no published port worked on any port at all**. `curl` connected and then timed
out with zero bytes:

```text
* Connected to localhost (::1) port 8081
* Request completely sent off
* Operation timed out after 8001 milliseconds with 0 bytes received
```

The containers themselves were fine — `docker exec <container> wget -qO- http://localhost/`
returned the page every time, and `docker ps` still showed the mapping. It was Docker Desktop's
host-side port forwarder that had stopped passing traffic, and restarting Docker Desktop clears it.

Two things worth taking from that:

- A TCP connection that **succeeds and then returns nothing** points at the forwarding layer, not
  at the application. A refused connection would mean nothing is listening; a successful connect
  with no data means something accepted on the application's behalf and could not deliver.
- `docker ps` showing `0.0.0.0:8081->80/tcp` only proves the mapping is *configured*. It is not
  evidence that it works, so it is worth checking from both sides.

The transcript in [verification.txt](verification.txt) is from a clean run before that happened.

## Compose equivalent

[`docker-compose.yml`](docker-compose.yml) builds the same topology, for the "remaining exercises"
part of the session:

```bash
docker compose up -d
docker compose ps
docker compose exec frontend wget -qO- http://backend/
docker compose exec backend nc -z -w 3 database 3306
docker compose down -v
```

Compose prefixes network names with the project directory, so they appear as
`container-networking_public_net` and so on. Membership and behaviour are identical, and the
frontend still cannot resolve `database`. The database keeps its data in a named volume,
`container-networking_database_data`.

## A note on the password

The MySQL password is read from `.env`, which is not committed. Only
[`.env.example`](.env.example) is tracked. Compose fails fast with a clear message if the variable
is missing, rather than starting a database with a default password.

## Full transcript

[verification.txt](verification.txt) — both the CLI run and the Compose run.
