# Docker at Containerization para sa EVEREST: Step-by-Step Guide

Para ito sa first time gagamit ng Docker. Unang bahagi: ano ba talaga ang Docker. Pangalawa: gagawin natin, step by step, ang Docker setup ng EVEREST (PostgreSQL + FastAPI backend + Angular frontend).

> Na-test na ang mga file sa guide na ito sa mismong project na ito (Docker 29.8.2, Windows 11). Gumana ang tatlong container: nag-load ang Angular app, sumagot ang backend, at nagawa ang 9 na table galing sa `schema.sql`.

> **Nagawa na ang Docker setup** sa branch na `docker-setup`: ang `docker-compose.yml`, `backend/Dockerfile`, `backend/.dockerignore`, at sa `frontend/event-registration/`: `Dockerfile`, `.dockerignore`, `nginx.conf`. Pumasa na rin ang Steps 1–6 at ang clean-state test (Step 9). Basahin ang guide bilang **paliwanag** ng bawat file na iyon. Ang kulang pa: Step 7 (admin), Step 10 (README), Step 11 (clone test, pagkatapos mag-commit), at Step 12 (push at PR).

---

## Workflow ng senior dev (checklist)

Ito ang pagkakasunod-sunod ng buong trabaho, mula umpisa hanggang ma-merge. Lagyan ng tsek (`[x]`) ang bawat isa pagkatapos mo. **Ang pinakamahalagang patakaran: isang hakbang lang bawat beses, at i-test muna bago lumipat sa susunod.** Kapag sabay-sabay mong ginawa lahat at may error, hindi mo malalaman kung saan galing.

**Paghahanda**
- [ ] Basahin ang Part 1 at Part 2. Alamin muna kung ano ang gagawin bago gumawa.
- [ ] **Step 0:** Gumawa ng branch na `docker-setup`.
- [ ] **Step 1:** Buksan ang Docker Desktop. Test: `docker run --rm hello-world`.
- [ ] **Step 2:** Warm-up gamit ang nginx. Test: makita ang "Welcome to nginx!" sa `localhost:8080`.

**Isa-isang service**
- [ ] **Step 3:** Backend Dockerfile at `.dockerignore`. Test: pumasa ang `docker build` → **commit #1**
- [ ] **Step 4:** Frontend Dockerfile, `nginx.conf`, at `.dockerignore`. Test: pumasa ang `docker build` → **commit #2**

**Pagsamahin**
- [ ] **Step 5:** `docker-compose.yml`. Test: walang error ang `docker compose config`.
- [ ] **Step 6:** `docker compose up --build`. Test: gumagana ang tatlong URL → **commit #3**
- [ ] **Step 7:** Gumawa ng admin. Test: makapag-login sa `localhost:4200`.
- [ ] **Step 8 (optional):** Kopyahin ang lumang data.
- [ ] **Step 9:** Clean-state test: burahin lahat at ulitin mula sa wala.

**Tapusin nang maayos**
- [ ] **Step 10:** Idagdag sa `README.md` kung paano patakbuhin → **commit #4**
- [ ] **Step 11:** Clone test: i-clone ang branch sa ibang folder at patakbuhin doon.
- [ ] **Step 12:** I-push ang branch, gumawa ng Pull Request, ipa-review, saka i-merge.

---

## Part 1: Ano ang Docker?

### Ang problema: "Gumagana naman sa laptop ko eh!"

Para patakbuhin ang EVEREST ngayon, kailangan ng kaklase mo (o ng teacher mo):

1. Python 3.13, tapos gagawa ng `venv`, tapos `pip install -r requirements.txt`
2. Node.js, tapos `npm install`
3. PostgreSQL 17, gagawa ng database `ers_db`, tapos ire-run ang `schema.sql`
4. Gagawa ng `backend/.env` na tama ang laman
5. Bubuksan ang dalawang terminal: `uvicorn` at `npm start`

Kapag iba ang Python version nila, o wala silang PostgreSQL, o mali ang password, **hindi gagana**. Iyon ang problemang sinosolusyunan ng Docker.

### Ang solusyon: i-"package" ang app kasama ang lahat ng kailangan nito

Isipin mo ang **shipping container** sa pantalan. Kahit ano pa ang laman (saging, kotse, damit), pareho ang hugis ng container, kaya kahit anong barko o truck ay kayang magbuhat nito.

Ganoon din ang Docker: ilalagay mo ang app mo **kasama ang Python, ang mga library, at ang settings** sa isang "container". Ang kailangan lang ng ibang computer ay Docker. Isang command lang (`docker compose up`) at tatakbo na ang buong EVEREST, pareho sa laptop mo.

### Container vs. Virtual Machine

| | Virtual Machine (hal. VirtualBox) | Docker Container |
|---|---|---|
| Laman | Buong operating system | App + libraries lang; ang kernel ay hiram sa host |
| Laki | Ilang GB | Ilang daang MB (backend natin: 292 MB, frontend: 94 MB) |
| Bilis mag-start | Minuto | Segundo |

Sa Windows, tumatakbo ang Docker Desktop sa loob ng isang maliit na Linux (WSL 2). Kaya ang mga container natin ay **Linux**, kahit Windows ang laptop mo.

### Mga salitang kailangan mong kabisaduhin

| Salita | Ibig sabihin | Analogy |
|---|---|---|
| **Image** | Ang "template" o naka-freeze na kopya ng app at lahat ng kailangan nito. Hindi ito tumatakbo. | Recipe / installer |
| **Container** | Isang tumatakbong kopya ng image. Puwede kang gumawa ng maraming container mula sa iisang image. | Ang lutong ulam galing sa recipe |
| **Dockerfile** | Text file na nagsasabi kung paano gagawin ang image, step by step. | Ang mismong recipe na nakasulat |
| **Docker Hub** | Online na "app store" ng mga image (`python`, `node`, `postgres`, `nginx`). Dito kinukuha ang base image. | Palengke ng sangkap |
| **Port mapping** (`-p 8000:8000`) | Nagdudugtong ng port ng laptop mo sa port sa loob ng container. Format: `LAPTOP:CONTAINER`. | Butas sa pader ng container |
| **Volume** | Storage na **hindi nabubura** kahit burahin ang container. Dito natin ilalagay ang data ng PostgreSQL. | External hard drive |
| **Network** | Ang mga container sa iisang Compose project ay nakakapag-usap gamit ang **pangalan ng service** (hal. `db`). | Group chat |
| **Docker Compose** | Isang YAML file (`docker-compose.yml`) na naglalarawan ng ilang container nang sabay, para isang command lang ang kailangan. | Ang "menu" ng buong handaan |

Mahalagang tandaan: **ang container ay pansamantala.** Kapag binura mo ito, nawawala ang lahat ng nasa loob, maliban sa nasa volume. Kaya ang database ay laging may volume.

---

## Part 2: Ang plano para sa EVEREST

Tatlong container ang gagawin natin:

```
            Laptop mo (browser)
   http://localhost:4200    http://localhost:8000
            │                       │
 ┌──────────▼─────────┐   ┌─────────▼──────────┐   ┌────────────────────┐
 │  frontend          │   │  backend           │   │  db                │
 │  nginx + Angular   │   │  FastAPI (uvicorn) │──▶│  PostgreSQL 17     │
 │  (built files)     │   │  python:3.13       │   │  volume: db_data   │
 │  port 80 → 4200    │   │  port 8000 → 8000  │   │  port 5432 → 5433  │
 └────────────────────┘   └────────────────────┘   └────────────────────┘
```

Bakit ganito:

- **Kailangang `4200` at `8000` pa rin ang ports.** Naka-hardcode sa Angular code ang `http://localhost:8000/api/...` (walang API service layer), ang CORS ng backend ay `localhost:4200` lang ang pinapayagan, at ang reCAPTCHA key ay naka-register para sa `localhost`. Kapag ganito pa rin ang ports, **walang code na kailangang baguhin.**
- **Ang Angular app ay hindi `ng serve` sa container.** Ibi-build natin ito (`ng build`) para maging plain HTML/JS/CSS files, tapos ise-serve ng **nginx**, isang mabilis at magaan na web server. Ang `ng serve` ay para sa development lang.
- **Ang browser ang tumatawag sa backend, hindi ang frontend container.** Ang Angular ay tumatakbo sa browser mo, kaya ang `localhost:8000` ay ang laptop mo, na naka-map sa backend container. Tama iyon.
- **Ang backend ay tumatawag sa database gamit ang pangalang `db`**, hindi `localhost`. Sa loob ng container, ang `localhost` ay ang container mismo, hindi ang laptop mo.
- **Ang database ay naka-map sa `5433`**, hindi `5432`, dahil may PostgreSQL 17 ka nang naka-install na gumagamit ng `5432`. Hindi sila mag-aagawan.

Mga file na gagawin mo:

```
EVEREST/
├── docker-compose.yml                    ← Step 5
├── backend/
│   ├── Dockerfile                        ← Step 3
│   └── .dockerignore                     ← Step 3
└── frontend/event-registration/
    ├── Dockerfile                        ← Step 4
    ├── .dockerignore                     ← Step 4
    └── nginx.conf                        ← Step 4
```

---

## Part 3: Step by step

Gamitin ang terminal ng VS Code (PowerShell). Lahat ng command ay ire-run mula sa **root ng repo** (`C:\Users\Kevin Dizon\EVEREST`) maliban kung sinabi.

### Step 0: Gumawa ng hiwalay na branch

Hindi gumagawa ng bagong feature ang senior dev nang diretso sa `main`. Gumagawa sila ng **branch**, isang hiwalay na "kopya" ng code kung saan puwede kang mag-eksperimento. Kapag may nasira, buo pa rin ang `main`. Kapag tapos at gumagana na, saka ito isasama (merge) sa `main`.

```powershell
git status                       # tingnan muna kung ano ang nabago na
git checkout main
git pull                         # kunin ang pinakabagong main galing GitHub
git checkout -b docker-setup     # gumawa ng branch na docker-setup at lumipat doon
git branch                       # may * sa tabi ng docker-setup = nandoon ka na
```

Mga dapat tandaan:
- **Sumasama sa bagong branch ang mga hindi pa naka-commit na pagbabago** (sa ngayon: `backend/main.py`, at ang dalawang `.docx` file). Hindi sila mawawala, pero **huwag gumamit ng `git add .`** o `git add -A` sa trabahong ito, dahil maisasama sila sa Docker commit. Laging pangalanan ang eksaktong file na ia-add, gaya ng nasa Part 6.
- Kung gusto mong bumalik sa `main` anumang oras: `git checkout main`. Para bumalik sa trabaho: `git checkout docker-setup`.

### Step 1: Buksan ang Docker Desktop at i-check

Naka-install na ang Docker Desktop sa laptop mo (`C:\Users\Kevin Dizon\AppData\Local\Programs\DockerDesktop`). Pero kailangan itong **nakabukas** bago gumana ang mga `docker` command.

1. Buksan ang **Docker Desktop** mula sa Start menu.
2. Hintayin hanggang "Engine running" ang nasa ibabang kaliwa (mga 30 segundo).
3. I-check sa terminal:

```powershell
docker --version          # Docker version 29.x
docker compose version    # Docker Compose version v2.x
docker run --rm hello-world
```

Kapag lumabas ang `Hello from Docker!`, ayos na. Ang nangyari:
- Hinanap ng Docker ang image na `hello-world` sa laptop mo; wala, kaya **dinownload (pull)** ito sa Docker Hub.
- Gumawa ito ng container, pinatakbo, nag-print ng mensahe, tapos huminto.
- Ang `--rm` ay nagsasabing burahin ang container pagkatapos.

> **Error na `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`?** Ibig sabihin hindi pa nakabukas ang Docker Desktop. Buksan ito at hintayin.

### Step 2: Warm-up, isang web server sa loob ng container

Bago ang EVEREST, subukan muna natin ang port mapping at ang basic commands:

```powershell
docker run -d --name test-nginx -p 8080:80 nginx:1.29-alpine
```

| Bahagi | Ibig sabihin |
|---|---|
| `docker run` | Gumawa at patakbuhin ang isang container |
| `-d` | "Detached": tumakbo sa background para magamit mo pa ang terminal |
| `--name test-nginx` | Pangalan ng container (kung wala, random ang ibibigay) |
| `-p 8080:80` | Ang port 8080 ng laptop mo → port 80 sa loob ng container |
| `nginx:1.29-alpine` | Image name `nginx`, tag (version) `1.29-alpine`. Ang `alpine` ay napakaliit na Linux. |

Buksan ang **http://localhost:8080** sa browser. Makikita mo ang "Welcome to nginx!". Tumatakbo iyan sa Linux sa loob ng laptop mo.

Subukan ang mga command na ito:

```powershell
docker ps                    # listahan ng tumatakbong containers
docker logs test-nginx       # output/logs ng container (makikita mo ang request ng browser mo)
docker exec -it test-nginx sh   # "pumasok" sa loob ng container (shell)
#   sa loob: ls /usr/share/nginx/html   → nandito ang index.html
#   sa loob: exit                       → lumabas
docker stop test-nginx       # ihinto
docker rm test-nginx         # burahin ang container
docker images                # listahan ng images na na-download mo
```

Ito ang buong cycle: **pull → run → logs/exec → stop → rm.** Ganito rin sa EVEREST, mas marami lang ang container.

### Step 3: Ang backend (FastAPI)

#### 3a. Gawin ang `backend/Dockerfile`

Gumawa ng file na `backend/Dockerfile` (walang extension) na may laman na:

```dockerfile
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Paliwanag, linya por linya:

| Linya | Ano ang ginagawa |
|---|---|
| `FROM python:3.13-slim` | Simulan sa official Python 3.13 image (parehong version ng `venv` mo). Ang `slim` ay maliit na Debian Linux. **Laging nagsisimula ang Dockerfile sa `FROM`.** |
| `ENV PYTHONDONTWRITEBYTECODE=1` | Huwag gumawa ng `__pycache__`/`.pyc` files sa container (hindi kailangan). |
| `ENV PYTHONUNBUFFERED=1` | Ipakita agad ang `print()` sa logs, para makita mo sa `docker compose logs`. |
| `ENV PYTHONIOENCODING=utf-8` | Nagpi-print ng emoji ang routes (✅ ⚠️). Kung walang UTF-8, puwedeng mag-`UnicodeEncodeError` at mag-fail ang request. |
| `WORKDIR /app` | Gawin ang `/app` na "current folder" sa loob ng container (parang `cd /app`). Dito mapupunta ang code. |
| `COPY requirements.txt .` | Kopyahin muna ang `requirements.txt` lang (paliwanag sa ibaba kung bakit). |
| `RUN pip install ...` | I-install ang mga library **habang binubuo ang image**. Ang `--no-cache-dir` ay para lumiit ang image. |
| `COPY . .` | Kopyahin ang buong `backend/` folder papunta sa `/app`. |
| `EXPOSE 8000` | Dokumentasyon lang: "port 8000 ang ginagamit ng app na ito". Hindi ito ang nagbubukas ng port; ang `ports:` sa Compose ang gumagawa noon. |
| `CMD [...]` | Ang command na tatakbo **kapag nag-start ang container**. Kapareho ito ng `python -m uvicorn main:app` na ginagamit mo, maliban sa dalawa: **walang `--reload`** (para sa development lang iyon), at **`--host 0.0.0.0`**. |

**Bakit `--host 0.0.0.0`?** Ang default ng uvicorn ay `127.0.0.1`, ibig sabihin "tanggapin lang ang requests galing sa loob ng container na ito." Ang browser mo ay nasa labas ng container, kaya hindi ito makakakonek. Ang `0.0.0.0` ay "tanggapin galing kahit saan." **Ito ang pinakakaraniwang pagkakamali ng mga baguhan.**

**`RUN` vs `CMD`:** Ang `RUN` ay tumatakbo **isang beses, habang nagbi-build** (pag-install). Ang `CMD` ay tumatakbo **tuwing magsisimula ang container** (pag-start ng server).

**Bakit hiwalay ang `COPY requirements.txt` bago ang `COPY . .`?** Dahil sa **layer caching**. Bawat linya ng Dockerfile ay isang "layer" na sine-save ng Docker. Kapag nag-build ka ulit at walang nagbago sa isang layer at sa lahat ng nauna rito, gagamitin na lang ang naka-save. Kaya:
- Binago mo lang ang `routes_db.py`? Ang `pip install` layer ay galing cache, at ilang segundo lang ang rebuild.
- Kung `COPY . .` muna bago `pip install`, bawat maliit na pagbabago sa code ay magre-reinstall ng lahat ng library (minuto).

#### 3b. Gawin ang `backend/.dockerignore`

Gaya ng `.gitignore`, pero para sa `COPY . .`. Ito ang mga file na **hindi** dapat makapasok sa image:

```
venv/
__pycache__/
**/__pycache__/
*.pyc
.env
uploads/
tests/
```

- **`venv/`**: Windows venv ito (`venv\Scripts\python.exe`), at hindi ito gagana sa Linux container. Malaki rin ito. Ang `pip install` sa Dockerfile ang gagawa ng sariling installation.
- **`.env`**: **Napakahalaga.** May password at secrets ito. Kapag nasa image, kasama ito kahit saan mo dalhin o i-upload ang image. Ibibigay natin ang `.env` sa container sa ibang paraan (`env_file` sa Step 5), habang tumatakbo lang.
- **`uploads/`**: Luma na ito; nasa database na ang mga cover photo (`events.cover_photo_data`). Gagawa rin ang `main.py` ng walang-lamang `uploads/events` folder pag-start.

#### 3c. Subukang i-build

```powershell
docker build -t everest-backend ./backend
```

- `-t everest-backend` ay ang pangalan (tag) ng image.
- `./backend` ay ang **build context**: ang folder na makikita ng `COPY`. Hindi makakakopya ang Dockerfile ng file sa labas nito.

Unang beses ay mga 1–2 minuto (dina-download ang `python:3.13-slim` at ini-install ang mga library). I-check:

```powershell
docker images everest-backend
```

Huwag mo pa itong i-`docker run`. Kailangan nito ng database, at sa Compose natin iyon ise-set up.

### Step 4: Ang frontend (Angular + nginx)

#### 4a. Gawin ang `frontend/event-registration/Dockerfile`

```dockerfile
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npx ng build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/event-registration/browser /usr/share/nginx/html
EXPOSE 80
```

Dalawang `FROM` ang nandito. Ito ang tinatawag na **multi-stage build**:

**Stage 1 (`AS build`): pag-compile.** Kailangan natin ng Node.js at ng `node_modules` (daan-daang MB) para i-build ang Angular. Pareho ang pattern sa backend: `package.json` muna, `npm ci`, saka ang code.
- **`npm ci`** sa halip na `npm install`: eksaktong sinusunod ang `package-lock.json` at hindi ito binabago. Ito ang tama para sa build.
- **`npx ng build`**: production build, kapareho ng `npx ng build` na alam mo. Ang output ay nasa `dist/event-registration/browser/`.

**Stage 2: ang talagang ise-serve.** Bagong simula mula sa malinis na `nginx` image. Ang **built files lang** ang kinokopya mula sa stage 1 (`COPY --from=build ...`). Ang Node.js at `node_modules` ay **naiiwan**, kaya **94 MB** lang ang final image sa halip na mahigit 1 GB.

#### 4b. Gawin ang `frontend/event-registration/nginx.conf`

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Bakit kailangan ang `try_files`?** Ang Angular ay *Single Page App*: iisa lang ang totoong page (`index.html`), at ang Angular router ang nagpapalit ng laman. Kapag binuksan mo nang diretso ang `http://localhost:4200/login` o pinindot ang Refresh sa `/event/5`, hahanapin ng nginx ang file na `/login`, na wala, kaya **404**. Ang `try_files` ay nagsasabing: "Kung walang ganoong file, ibigay ang `index.html`," at ang Angular na ang bahala sa route. Mahalaga ito sa EVEREST dahil ang verification email ay nagpapadala ng link papuntang `/verify-email?token=...`, at ang reset email ay `/reset-password?token=...`.

#### 4c. Gawin ang `frontend/event-registration/.dockerignore`

```
node_modules/
dist/
.angular/
coverage/
backend/
frontend/
```

Ang `node_modules/` at `dist/` ay ginagawa sa loob ng container, kaya hindi kailangan ang sa Windows. Kung isasama, mabagal ang build at baka magkagulo (Windows binaries sa Linux). Ang `backend/` at `frontend/` ay mga lumang tirang folder na baka bumalik; hindi sila parte ng Angular app.

#### 4d. Subukang i-build

```powershell
docker build -t everest-frontend ./frontend/event-registration
```

Mga 1–3 minuto sa unang beses (`npm ci` + `ng build`). Kapag nag-fail ito sa `ng build`, iyan din ang error na makukuha mo sa `npx ng build` sa laptop mo, kaya ayusin muna ito roon.

### Step 5: Pagsamahin lahat gamit ang Docker Compose

Kung walang Compose, kailangan mong gumawa ng network, volume, at tatlong mahahabang `docker run` command na tama ang pagkakasunod. Ginagawa ito lahat ng Compose gamit ang isang file.

Gumawa ng `docker-compose.yml` sa **root ng repo** (`EVEREST/docker-compose.yml`):

```yaml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: everest
      POSTGRES_PASSWORD: everest_pw
      POSTGRES_DB: ers_db
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./backend/database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U everest -d ers_db"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql://everest:everest_pw@db:5432/ers_db
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend/event-registration
    ports:
      - "4200:80"
    depends_on:
      - backend

volumes:
  db_data:
```

> **Mahalaga sa YAML:** Ang indentation ay **spaces**, hindi Tab, at may kahulugan ito. Ang `environment:` ay dapat nakapasok sa ilalim ng `db:`, atbp. Mali ang isang space, mali ang buong file. I-check gamit ang `docker compose config`, na magpapakita ng error kung may mali.

Paliwanag bawat bahagi:

**`services:`** Ang listahan ng mga container. Ang pangalan (`db`, `backend`, `frontend`) ay siya ring **hostname** nila sa internal network.

**`db`**
- `image: postgres:17-alpine`: walang Dockerfile; ginagamit ang official image nang diretso. Version 17, pareho sa naka-install sa laptop mo.
- `environment:`: binabasa ng postgres image ang mga variable na ito **sa unang pagbukas** para gawin ang user, password, at database.
- `db_data:/var/lib/postgresql/data`: dito sine-save ng PostgreSQL ang data, at naka-volume ito, kaya **hindi nawawala ang data kahit i-restart o i-rebuild**.
- `schema.sql:/docker-entrypoint-initdb.d/...`: espesyal na feature ng postgres image: ang mga `.sql` file sa folder na ito ay **awtomatikong nire-run, pero sa UNANG start lang** (kapag walang laman ang volume). Kaya nagagawa ang mga table nang hindi mo pinapatakbo ang `schema.sql` nang mano-mano. Ang `:ro` ay read-only. **Ligtas ito** kahit nagsisimula ang `schema.sql` sa `DROP TABLE`, dahil hindi na ito tatakbo ulit sa susunod na start.
- `ports: "5433:5432"`: para mabuksan mo ang database ng container sa pgAdmin (`localhost`, port **5433**, user `everest`). Puwede mo itong tanggalin kung hindi mo kailangan; hindi ito kailangan ng backend.
- `healthcheck:`: tinatanong ang PostgreSQL tuwing 5 segundo kung handa na ito (`pg_isready`).

**`backend`**
- `build: ./backend`: i-build ang image gamit ang `backend/Dockerfile`.
- `env_file: ./backend/.env`: ibigay sa container ang lahat ng laman ng `.env` mo (JWT secret, Brevo key, reCAPTCHA secret) **habang tumatakbo** lang. Hindi sila napupunta sa image.
- `environment: DATABASE_URL: ...@db:5432/ers_db`: **pinapalitan** nito ang `DATABASE_URL` mula sa `.env` mo (na `localhost:5432` at ang lokal mong password). Napapansin mo ang **`db`** bilang host: ang database container iyon. Ang port ay **5432** (ang port *sa loob* ng network), hindi 5433.
- `depends_on: db: condition: service_healthy`: huwag i-start ang backend hangga't hindi pa "healthy" ang database. Kung wala ito, maaaring mag-start ang backend bago pa handa ang PostgreSQL, at mag-crash ang startup hook nito (`ALTER TABLE ...`).

**`frontend`**
- `ports: "4200:80"`: port 80 ang nginx sa loob, pero `4200` sa laptop mo, kaya gumagana pa rin ang CORS at reCAPTCHA.

**`volumes: db_data:`** Ideklara ang named volume. Docker ang mamamahala kung saan ito naka-save.

### Step 6: Patakbuhin!

**Una, ihinto ang anumang EVEREST na tumatakbo na:** ang `uvicorn` (port 8000) at `npm start` (port 4200) sa ibang terminal. Hindi puwedeng gamitin ng dalawang program ang iisang port.

```powershell
docker compose up --build
```

- `up`: gawin at i-start ang lahat ng service.
- `--build`: i-build (o i-rebuild) muna ang images.

Makikita mo ang logs ng tatlong container nang magkakahalo, may kulay ang pangalan sa kaliwa (`db-1`, `backend-1`, `frontend-1`). Hintayin ito:

```
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Tapos i-check:

| Buksan | Dapat makita |
|---|---|
| http://localhost:8000/ | `{"message":"EVEREST Event Registration API", ..., "status":"running"}` |
| http://localhost:8000/docs | Ang FastAPI docs |
| http://localhost:4200/ | Ang EVEREST login page |

Para ihinto: **Ctrl+C** sa terminal na iyon.

Sa susunod, para tumakbo sa background (para magamit pa ang terminal):

```powershell
docker compose up -d --build
docker compose ps              # dapat "Up" ang tatlo, at "(healthy)" ang db
docker compose logs -f backend # sundan ang logs ng backend (Ctrl+C para lumabas sa logs lang)
```

### Step 7: Gumawa ng admin account

**Bago at walang laman ang database sa container**, hiwalay sa `ers_db` ng lokal mong PostgreSQL. Kaya walang admin. Patakbuhin ang `create_admin.py` **sa loob ng backend container**:

```powershell
docker compose exec backend python create_admin.py
```

- `exec backend` ay "patakbuhin ang command na ito sa loob ng tumatakbong `backend` container."
- Gumagamit ito ng `DATABASE_URL` ng container, kaya mapupunta ang admin sa database ng container.
- Itatanong nito ang pangalan, email, at password (nakatago ang password habang tina-type; dapat sumunod sa password rules: 8+ characters, uppercase, lowercase, number, symbol).

Ngayon, mag-login sa http://localhost:4200 gamit ang admin account. Ang mga student, participant, at organizer ay magre-register gaya ng dati: may verification email, kaya kailangang tama ang `BREVO_API_KEY` sa `.env` (o `EMAIL_ENABLED`/SMTP mo). Ang mga link sa email ay `localhost:4200`, na tama pa rin.

### Step 8 (optional): Kopyahin ang lumang data mo papunta sa container

Kung gusto mong dalhin ang mga event at account na nasa lokal mong `ers_db`:

```powershell
# 1. I-dump ang DATA lang (hindi ang tables) mula sa lokal mong PostgreSQL 17.
#    Itatanong nito ang password ng 'postgres' user mo.
& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -U postgres -d ers_db --data-only --no-owner -f everest_data.sql

# 2. Burahin ang sample departments na nilagay ng schema.sql (para hindi mag-duplicate),
#    pati anumang laman ng ibang table.
docker compose exec db psql -U everest -d ers_db -c "TRUNCATE attendees, registrations, events, user_roles, users, departments, pending_registrations, password_reset_tokens, revoked_tokens RESTART IDENTITY CASCADE;"

# 3. Kopyahin ang file sa loob ng db container at i-load.
docker compose cp everest_data.sql db:/tmp/everest_data.sql
docker compose exec db psql -U everest -d ers_db -f /tmp/everest_data.sql

# 4. Burahin ang dump file. May laman itong password hashes at personal data, kaya HUWAG i-commit.
Remove-Item everest_data.sql
```

Gawin ito **habang tumatakbo na ang stack** (pagkatapos ng Step 6), dahil ang backend ang nagdadagdag ng `employment_id` column na kailangan ng data.

### Step 9: Clean-state test (burahin lahat at ulitin mula sa wala)

Gumagana na ito sa laptop mo, pero baka dahil lang may natira sa mga naunang test: lumang image, lumang volume, o cache. Ang tanong ng senior dev: **"Gagana ba ito sa unang beses, sa computer na walang kahit ano?"** Kaya buburahin natin lahat at uulitin.

> **Babala:** Buburahin nito ang database sa container, kasama ang admin at data na kinopya mo sa Step 7–8. Hindi apektado ang lokal mong `ers_db`.

```powershell
docker compose down -v --rmi local   # burahin ang containers, volume, at images na ginawa ng compose
docker builder prune -f              # burahin ang build cache (para walang "CACHED" na daya)
docker compose up --build            # ulitin mula sa wala
```

Pasado kapag:
- [ ] Walang error sa build, at walang `CACHED` sa mga hakbang ng Dockerfile mo (bago lahat).
- [ ] `db-1` ay nagpakita ng `running /docker-entrypoint-initdb.d/01-schema.sql` (tumakbo ulit ang schema).
- [ ] `backend-1` ay umabot sa `Uvicorn running on http://0.0.0.0:8000`.
- [ ] Gumagana ang `localhost:8000` at `localhost:4200`.
- [ ] Nakagawa ulit ng admin (Step 7) at nakapag-login.

Kapag may bumagsak dito pero gumana noong una, ibig sabihin may "nakatagong" dependency: isang bagay na nasa laptop mo pero wala sa Dockerfile o compose. Iyan mismo ang hinahanap ng test na ito.

---

## Part 4: Pang-araw-araw na commands

| Gusto mong... | Command |
|---|---|
| I-start lahat (background) | `docker compose up -d` |
| I-start at i-rebuild pagkatapos magbago ang code | `docker compose up -d --build` |
| I-rebuild ang isa lang | `docker compose up -d --build backend` |
| Tingnan ang status | `docker compose ps` |
| Tingnan ang logs | `docker compose logs -f backend` (o `frontend`, `db`) |
| I-restart ang isa | `docker compose restart backend` |
| Ihinto lahat (data ay naiiwan) | `docker compose down` |
| Ihinto at **BURAHIN ang database** | `docker compose down -v` |
| Pumasok sa backend | `docker compose exec backend bash` |
| Buksan ang database sa SQL | `docker compose exec db psql -U everest -d ers_db` (`\dt` = mga table, `\q` = labas) |
| Linisin ang lumang images/cache | `docker system prune` (magtatanong muna) |

**`down` vs `down -v`:** Ang `docker compose down` ay nagbubura ng mga container, pero **naiiwan ang volume `db_data`**, kaya buo pa ang data mo sa susunod na `up`. Ang `-v` ay nagbubura rin ng volume: lahat ng account at event ay **mawawala**, at tatakbo ulit ang `schema.sql` sa susunod na `up`. Gamitin lang ang `-v` kung gusto mo talaga ng fresh database.

**Pagkatapos baguhin ang code:** Hindi automatic na makikita ang pagbabago sa container. Kopya ng code ang nasa image, hindi live. Kailangan ng `docker compose up -d --build`. Kaya sa **araw-araw na pag-develop**, mas mabilis pa rin ang dating paraan (`npm start` + `uvicorn --reload`, na may hot reload). Gamitin ang Docker para sa: pag-demo, pagbigay ng project sa kaklase o teacher, at pag-check na gumagana ito sa "malinis" na computer. Huwag lang sabay patakbuhin ang dalawa dahil parehong ports.

---

## Part 5: Kapag may error

| Error / sintomas | Dahilan at solusyon |
|---|---|
| `failed to connect to the docker API ... dockerDesktopLinuxEngine` | Hindi nakabukas ang Docker Desktop. Buksan at hintayin ang "Engine running". |
| `Bind for 0.0.0.0:8000 failed: port is already allocated` (o 4200) | May tumatakbo nang `uvicorn` o `ng serve`. Ihinto ito (Ctrl+C sa terminal nito), o tingnan kung ano: `netstat -ano \| findstr :8000`. |
| Port 5433 ay ginagamit | Palitan ang `"5433:5432"` ng `"5434:5432"`, o tanggalin ang `ports:` ng `db`. |
| Backend: `RuntimeError: JWT_SECRET_KEY is not set` | Walang `backend/.env`, o kulang ang laman. Ang `.env` ay hindi naka-commit, kaya **ang kaklase mong nag-clone ay kailangang gumawa ng sarili niyang `backend/.env`** (tingnan ang listahan ng settings sa `CLAUDE.md`). |
| Backend: may `$` sa password o secret sa `.env` at kakaiba ang value | Binabasa ng Compose ang `$` bilang variable. Gawing `$$` sa `.env`, o gumawa ng bagong secret na walang `$`. |
| Backend: `could not translate host name "db"` o `connection refused` | Na-start ang backend nang wala sa Compose (hal. `docker run` lang), o mali ang pangalan ng service. Gamitin ang `docker compose up`. |
| Bagong table o column sa `schema.sql` pero wala sa database | Ang `schema.sql` ay tumatakbo lang sa **unang** start. Para ulitin: `docker compose down -v` tapos `up` (mabubura ang data), o i-run ang `ALTER TABLE` mo sa `docker compose exec db psql ...`. |
| Frontend: blangko ang page o 404 kapag nag-Refresh | Kulang o mali ang `nginx.conf` (`try_files`). Tingnan ang `docker compose logs frontend`. |
| Login: "CORS error" sa browser console | Hindi `localhost:4200` ang binuksan mo (hal. `127.0.0.1:4200` o IP address). Gamitin ang `http://localhost:4200`. |
| reCAPTCHA: "Invalid domain for site key" | Gaya ng CORS: dapat `localhost` ang nasa address bar. |
| Hindi nagbago ang app pagkatapos mag-edit | Kailangang i-rebuild: `docker compose up -d --build`. |
| Napuno na ang disk | `docker system prune` para burahin ang lumang images at build cache. |

Laging unahin ang **logs**: `docker compose logs backend`. Nandoon halos lagi ang sagot.

---

## Part 6: Commits, README, at Pull Request

### Maliliit na commit, habang nagtatrabaho

Hindi isang malaking commit sa dulo ang ginagawa ng senior dev. **Nagko-commit sila tuwing may natapos at na-test na bahagi.** Bakit:
- Kapag may nasira mamaya, puwede kang bumalik sa huling commit na gumagana.
- Mas madaling i-review ng kagrupo ang maliliit na pagbabago.
- Ang `git log` ay nagiging kuwento ng ginawa mo, hakbang-hakbang.

Ito ang apat na commit, at kung kailan gagawin ang bawat isa (tingnan ang checklist sa itaas):

```powershell
# Commit #1: pagkatapos pumasa ang Step 3 (docker build ng backend)
git add backend/Dockerfile backend/.dockerignore
git commit -m "Add backend Dockerfile"

# Commit #2: pagkatapos pumasa ang Step 4 (docker build ng frontend)
git add frontend/event-registration/Dockerfile frontend/event-registration/.dockerignore frontend/event-registration/nginx.conf
git commit -m "Add frontend Dockerfile with nginx"

# Commit #3: pagkatapos gumana ang buong app sa Step 6
git add docker-compose.yml
git commit -m "Add docker-compose for db, backend, and frontend"

# Commit #4: pagkatapos ng Step 10 (README)
git add README.md DOCKER_GUIDE.md
git commit -m "Document how to run EVEREST with Docker"
```

Bago ang bawat `git commit`, patakbuhin ang **`git status`** at tingnan ang nasa "Changes to be committed". Dapat **ang mga Docker file lang** ang nandoon. Kung may nakita kang `.env`, `.docx`, o `backend/main.py`, alisin ito: `git restore --staged <file>`.

Hindi kailanman maisasama ang `backend/.env`: nasa `.gitignore` na ito, at dapat manatiling ganoon.

### Step 10: Idagdag sa README kung paano patakbuhin

Ang tanong ng kagrupo mo ay laging "Paano ko ito patatakbuhin?" Kaya isulat ang sagot sa `README.md` sa root ng repo. Maikli lang; ang detalye ay nasa guide na ito. Idagdag ito sa **itaas** ng README:

````markdown
## Running with Docker

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) and a `backend/.env` file (see CLAUDE.md for the settings it needs).

```bash
docker compose up --build                            # start the database, backend, and frontend
docker compose exec backend python create_admin.py   # first time only: create an admin
```

Open http://localhost:4200. Stop with `docker compose down` (add `-v` to also delete the database).
Step-by-step explanation: [DOCKER_GUIDE.md](DOCKER_GUIDE.md).
````

Tapos commit #4 (nasa itaas).

### Step 11: Clone test (gagana ba sa computer ng kaklase mo?)

Ang Step 9 ay gumamit pa rin ng folder mo, kasama ang mga file na hindi naka-commit. Ang clone test ay gumagamit **lang ng naka-commit**, eksaktong makukuha ng kagrupo mo. Kapag may nakalimutan kang i-commit, dito ito lalabas.

```powershell
docker compose down                        # ihinto muna ang stack sa main folder (parehong ports)

cd "C:\Users\Kevin Dizon"
git clone --branch docker-setup "C:\Users\Kevin Dizon\EVEREST" EVEREST-clone-test
cd EVEREST-clone-test

Copy-Item "..\EVEREST\backend\.env" "backend\.env"   # ang .env lang ang kinokopya nang mano-mano, gaya ng gagawin ng kaklase mo
docker compose up --build
```

Pasado kapag gumana ang `localhost:4200` gaya ng sa Step 9. Pagkatapos, linisin:

```powershell
docker compose down -v --rmi local        # sa loob pa rin ng EVEREST-clone-test
cd "C:\Users\Kevin Dizon"
Remove-Item -Recurse -Force EVEREST-clone-test
cd EVEREST
```

### Step 12: I-push at gumawa ng Pull Request

Ang **Pull Request (PR)** ay pakiusap na "pakisama ang branch ko sa `main`." Doon nakikita ng kagrupo mo ang lahat ng binago mo, nakakapag-comment sila, at sila (o ikaw) ang magme-merge kapag okay na.

1. I-push ang branch sa GitHub:

   ```powershell
   git push -u origin docker-setup
   ```

   Ang `-u` ay para sa susunod, `git push` na lang ang kailangan.

2. Buksan ang https://github.com/Kevntka/EVEREST. May lalabas na dilaw na banner na **"docker-setup had recent pushes"** → pindutin ang **Compare & pull request**.
3. Siguraduhing **base: `main`** ← **compare: `docker-setup`**.
4. Lagyan ng malinaw na title at description. Halimbawa:

   ```
   Title: Add Docker setup

   What: Dockerfiles for the backend and frontend, and a docker-compose.yml
   that runs PostgreSQL, FastAPI, and the Angular app (nginx) together.

   How to test:
   1. Create backend/.env
   2. docker compose up --build
   3. docker compose exec backend python create_admin.py
   4. Open http://localhost:4200 and log in

   Tested: clean-state test (Step 9) and clone test (Step 11) both passed.
   ```

5. **Create pull request.** Ipa-review sa kagrupo: hilingin sa kanila na sundin ang "How to test" sa sarili nilang laptop.
6. Kung may babaguhin sila, gawin ito sa `docker-setup` branch, commit, at `git push`. Kusang nadadagdag ang bagong commit sa parehong PR.
7. Kapag okay na: **Merge pull request** sa GitHub. Tapos sa laptop mo:

   ```powershell
   git checkout main
   git pull                          # kunin ang main na may Docker setup na
   git branch -d docker-setup        # burahin ang lokal na branch (tapos na)
   ```

---

## Part 7: Ano ang HINDI pa sakop nito

Ang setup na ito ay para sa **local na pagpapatakbo** (laptop mo, demo, kaklase). Para sa totoong deployment sa internet (server o cloud), kailangan pa ng:

1. **Palitan ang mga naka-hardcode na `http://localhost:8000`** (57 lugar sa frontend code) ng tunay na domain, mas maganda kung gamit ang Angular `environment` file o relative `/api` URL na ipapasa ng nginx sa backend.
2. **Itakda ang `FRONTEND_URL` at `ALLOWED_ORIGINS`** sa tunay na domain, at idagdag ang domain sa reCAPTCHA key.
3. **HTTPS**, tapos `HTTPS_ONLY=true` at `ENABLE_API_DOCS=false`.
4. **Tunay na password ng database** sa halip na `everest_pw`, na nakatago sa secret o env file, hindi nakasulat sa `docker-compose.yml`.
5. Tanggalin ang `ports:` ng `db` para hindi ito maabot mula sa labas.
6. Ang mga email link (`http://localhost:4200/login` sa `services/email_service.py`) ay naka-hardcode rin.

Iyan ang susunod na hakbang kapag kailangan na ninyong i-deploy talaga.

---

## Buod

1. **Image** = recipe. **Container** = tumatakbong kopya. **Dockerfile** = paano gawin ang image. **Compose** = maraming container sa isang file. **Volume** = data na hindi nawawala.
2. Sa EVEREST: tatlong container, `db` (PostgreSQL + `schema.sql`), `backend` (FastAPI, `--host 0.0.0.0`), at `frontend` (Angular build sa nginx).
3. Ports 4200 at 8000 ay pareho pa rin, kaya walang code na binago.
4. `docker compose up -d --build` para mag-start, `docker compose exec backend python create_admin.py` para sa admin, `docker compose down` para huminto, at **iwasan ang `-v` maliban kung gusto mong burahin ang data.**
