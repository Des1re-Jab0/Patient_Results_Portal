# Patient Results Portal

A secure, data-driven healthcare demonstration system designed to simplify access to laboratory results, medical conclusions, prescriptions, and medication information through a command-line interface (CLI).

## Live Application & Demo

- **Live API:** https://www.manzijabo.tech
- **Health Endpoint:** https://www.manzijabo.tech/health
- **Demo Video:** https://youtu.be/I9glEzbILss
- ** codevibe-verify.js:** https://drive.google.com/file/d/1eANotKKUd9m9CPhpM1f6PCNN2f5VTg44/view?usp=sharing

## Problem Statement

Accessing laboratory results and medication information can be challenging for patients. Traditional processes may involve unnecessary hospital visits, communication delays, and limited access to medical information.

The Patient Results Portal addresses these challenges by providing a centralized platform where patients, doctors, and laboratory technicians can interact with medical information remotely.

## Key Features

- **Patient:** View released laboratory results, medical conclusions, and prescriptions.
- **Doctor:** Review patient cases, provide medical conclusions, prescribe medication, and release results.
- **Laboratory Technician:** Upload patient laboratory results.
- **Data Interaction:** Search, filter, and sort patient cases.
- **External API Integration:** Retrieve supplementary medication information through openFDA.
- **Authentication:** JWT-based authentication and role-based access control.
- **Performance:** API response caching and rate limiting.
- **Scalability:** Two application servers behind an HAProxy load balancer.
- **Security:** HTTPS encryption and environment-based credential management.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application development |
| Flask | REST API |
| PostgreSQL / Neon | Cloud database |
| SQLAlchemy | Database management |
| JWT | Authentication |
| openFDA | External medication information |
| Gunicorn | WSGI application server |
| Nginx | Reverse proxy |
| HAProxy | Load balancing |
| Ubuntu | Server operating system |
| Git & GitHub | Version control |

## System Architecture

```mermaid
graph TD
    A[Python CLI Client] -->|HTTPS| B[HAProxy - LB01]
    B -->|Round Robin| C[Web01]
    B -->|Round Robin| D[Web02]
    C --> E[Nginx + Gunicorn + Flask]
    D --> F[Nginx + Gunicorn + Flask]
    E --> G[(Neon PostgreSQL)]
    F --> G
    E --> H[openFDA REST API]
    F --> H
```

HAProxy distributes incoming requests between two application servers using the round-robin algorithm. Both servers connect to a shared PostgreSQL database, ensuring consistent application data.

Application-level health checks allow HAProxy to identify unhealthy backend servers.

## Project Structure

```text
Patient_Results_Portal/
├── cli/
│   └── portal.py
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── models.py
│   ├── openfda.py
│   └── seed.py
├── tests/
│   ├── smoke_test.py
│   └── test_cli_format.py
├── .gitignore
├── requirements.txt
└── README.md
```

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/Des1re-Jab0/Patient_Results_Portal
cd Patient_Results_Portal
```

### 2. Create a virtual environment

Python 3.12 is recommended.

```bash
python -m venv .venv
```

Activate on Linux or macOS:

```bash
source .venv/bin/activate
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root.

```env
SECRET_KEY=replace-with-a-strong-random-secret
SERVER_NAME=local
OPENFDA_API_KEY=
```

The application supports SQLite for local development and PostgreSQL for deployment.

To use PostgreSQL, add your database connection string:

```env
DATABASE_URL=postgresql://username:password@host/database?sslmode=require
```

Generate a strong secret key using:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit the `.env` file or sensitive credentials to GitHub.

### 5. Initialize the demonstration database

```bash
python -m server.seed
```

Use a separate local database for development and testing.

### 6. Start the application

```bash
python -m flask --app server.app run --port 5000
```

The local API will be available at:

`http://127.0.0.1:5000`

## Application Usage

Open a separate terminal inside the project directory and activate the virtual environment.

### Connect to the local application

Linux or macOS:

```bash
export PORTAL_URL="http://127.0.0.1:5000"
```

Windows PowerShell:

```powershell
$env:PORTAL_URL = "http://127.0.0.1:5000"
```

## External REST API — openFDA

The Patient Results Portal integrates with the openFDA Drug Label REST API to retrieve supplementary medication information, including indications and usage.

| Resource | Link |
|---|---|
| Official website | [openFDA](https://open.fda.gov/) |
| REST API endpoint | [Drug Label API](https://api.fda.gov/drug/label.json) |
| API documentation | [Drug Label Documentation](https://open.fda.gov/apis/drug/label/) |
| API authentication | [API Keys and Authentication](https://open.fda.gov/apis/authentication/) |

### Example API Request

```http
GET https://api.fda.gov/drug/label.json?search=openfda.generic_name:metformin&limit=1
```

### API Key

The application supports an optional API key through the `OPENFDA_API_KEY` environment variable. The API can also be accessed without a key, subject to rate limits.

### Optimization and Reliability

- Response caching to reduce repeated API requests.
- Request timeouts to prevent indefinite waiting.
- Error handling for unavailable or invalid API responses.
- Secure environment-based API key management.

### Acknowledgment

Medication information is provided by openFDA, developed and maintained by the United States Food and Drug Administration (FDA).

The retrieved information is intended for educational purposes and is not a substitute for professional medical advice.

### Connect to the deployed application

Linux or macOS:

```bash
export PORTAL_URL="https://www.manzijabo.tech"
```

Windows PowerShell:

```powershell
$env:PORTAL_URL = "https://www.manzijabo.tech"
```

### Available CLI commands

| Command | Description |
|---|---|
| `login` | Authenticate a user |
| `logout` | End the local session |
| `list` | List, search, filter, and sort cases |
| `show` | Display detailed laboratory results |
| `meds` | Display prescriptions and medication information |
| `upload` | Upload laboratory results |
| `conclude` | Add a medical conclusion |
| `prescribe` | Add a prescription |
| `release` | Release results to a patient |

### Example usage

```bash
python cli/portal.py login patient1
python cli/portal.py list
python cli/portal.py show 1
python cli/portal.py meds 2
python cli/portal.py logout
```

To explore available filtering, sorting, and searching options:

```bash
python cli/portal.py list --help
```

### Demonstration Accounts

| Username | Role |
|---|---|
| patient1 | Patient |
| patient2 | Patient |
| doctor1 | Doctor |
| lab1 | Laboratory Technician |

Demonstration passwords are provided through the assignment submission comments.

## External API Integration

The application integrates with the **openFDA Drug Label API**, maintained by the United States Food and Drug Administration (FDA).

The API provides supplementary medication information, including indications and usage information.

- **Endpoint:** https://api.fda.gov/drug/label.json
- **Documentation:** https://open.fda.gov/apis/drug/label/
- **API Key Information:** https://open.fda.gov/apis/authentication/

The integration implements:

- API response caching.
- Request timeouts.
- Error handling for unavailable responses.
- Optional API key authentication.

openFDA supports requests without an API key, subject to its rate limits.

## Deployment

The application is deployed across three Ubuntu servers.

| Server | Responsibility |
|---|---|
| Web01 | Application server |
| Web02 | Application server |
| LB01 | HAProxy load balancer |

### 1. Configure both application servers

On Web01 and Web02, install the required system packages:

```bash
sudo apt update
sudo apt install -y nginx git curl build-essential libpq-dev
```

Install Python 3.12, clone the repository, create a virtual environment, and install the application dependencies.

Configure the `.env` file on both servers with the same PostgreSQL connection string and JWT secret key.

Set a unique server identifier on each server:

```env
SERVER_NAME=7305-web-01
```

```env
SERVER_NAME=7305-web-02
```

Initialize the shared database once.

### 2. Configure Gunicorn and systemd

Create `/etc/systemd/system/patient-portal.service` on both application servers.

```ini
[Unit]
Description=Patient Results Portal
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/Patient_Results_Portal
EnvironmentFile=/home/ubuntu/Patient_Results_Portal/.env
ExecStart=/home/ubuntu/Patient_Results_Portal/.venv/bin/gunicorn --workers 1 --threads 2 --bind 127.0.0.1:5000 server.app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now patient-portal
sudo systemctl status patient-portal
```

### 3. Configure Nginx

Create `/etc/nginx/sites-available/patient-portal` on both web servers.

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        allow 127.0.0.1;
        allow ::1;
        allow 10.30.19.177;
        deny all;

        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

Enable the configuration:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/patient-portal /etc/nginx/sites-enabled/patient-portal
sudo nginx -t
sudo systemctl reload nginx
```

Direct backend access is restricted to localhost and the load balancer.

### 4. Configure HAProxy

On LB01, configure `/etc/haproxy/haproxy.cfg` with the following frontend and backend sections.

```haproxy
frontend www-http
    bind *:80
    redirect scheme https code 301 if !{ ssl_fc }
    default_backend web-backend

frontend www-https
    bind *:443 ssl crt /etc/haproxy/certs/www.manzijabo.tech.pem
    http-request set-header X-Forwarded-Proto https
    default_backend web-backend

backend web-backend
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200
    server web-01 10.30.29.37:80 check
    server web-02 10.30.15.63:80 check
```

Retain the existing HAProxy global and defaults sections. A valid TLS certificate and private key must be configured on the load balancer.

Validate and reload HAProxy:

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
```

## Testing and Verification

### Health check

```bash
curl -i https://www.manzijabo.tech/health
```

### Load balancing

```bash
for i in {1..6}; do
    curl -s https://www.manzijabo.tech/health
    echo
done
```

Observed results:

```json
{"server":"7305-web-01","status":"ok"}
{"server":"7305-web-02","status":"ok"}
{"server":"7305-web-01","status":"ok"}
{"server":"7305-web-02","status":"ok"}
{"server":"7305-web-01","status":"ok"}
{"server":"7305-web-02","status":"ok"}
```

### Verification results

| Test | Result |
|---|---|
| Public HTTPS accessibility | Passed |
| HTTP-to-HTTPS redirection | Passed |
| Round-robin load balancing | Passed |
| Shared database connectivity | Passed |
| Doctor and patient authentication | Passed |
| Cross-server JWT authentication | Passed |
| Role-based case filtering | Passed |
| Laboratory results retrieval | Passed |
| Prescription retrieval | Passed |
| openFDA API connectivity | Passed |

## Security and Performance

The application implements:

- JWT-based authentication.
- Role-based access control.
- Password hashing.
- HTTPS communication between clients and the load balancer.
- Environment-based secret management.
- Restricted backend access.
- API response caching.
- Request rate limiting.
- Backend health monitoring.

Sensitive configuration files are excluded from version control through `.gitignore`.

## Challenges and Solutions

| Challenge | Solution |
|---|---|
| Maintaining consistent data across servers | Shared Neon PostgreSQL database |
| Maintaining authentication across servers | Shared JWT signing secret |
| Distributing incoming traffic | HAProxy round-robin load balancing |
| Managing application processes | Gunicorn and systemd |
| Restricting direct backend access | Nginx access rules |
| External API failures | Timeouts, caching, and error handling |
| Intermittent database connections | Temporary service recovery and planned connection-pool improvements |

## Future Improvements

- Improve database connection resilience.
- Improve medication matching accuracy.
- Implement shared caching and rate limiting.
- Automate testing and deployment through CI/CD.
- Develop a graphical user interface.
- Conduct comprehensive security and failover testing.

## Credits

- [openFDA](https://open.fda.gov/) — Medication information API.
- [Flask](https://flask.palletsprojects.com/) — REST API framework.
- [Neon](https://neon.com/) — Cloud PostgreSQL database.
- [SQLAlchemy](https://www.sqlalchemy.org/) — Database toolkit.
- [Gunicorn](https://gunicorn.org/) — WSGI server.
- [Nginx](https://nginx.org/) — Reverse proxy.
- [HAProxy](https://www.haproxy.org/) — Load balancing.
- [PyJWT](https://pyjwt.readthedocs.io/) — JWT authentication.

## Disclaimer

This project was developed for educational and demonstration purposes using synthetic medical data.

It is not intended for clinical diagnosis, medical advice, or the management of real patient information. External medication information may require additional validation.

---

**Patient Results Portal — Making medical information more accessible through software engineering.**