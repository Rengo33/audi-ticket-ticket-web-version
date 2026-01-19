# 🎫 Audi Ticket Bot Web

Web-basierte Version des Audi Ticket Bots mit Mobile-Checkout-Support.

## Features

- **Web Dashboard** - Tasks erstellen & verwalten über Browser
- **Echtzeit Updates** - WebSocket-basierte Live-Logs
- **Mobile Checkout** - Checkout-Links funktionieren auf iPhone/iPad
- **Multi-Task Support** - Mehrere Monitoring-Tasks gleichzeitig
- **Discord Notifications** - Optional: Benachrichtigungen über Discord

## Tech Stack

- **Backend**: FastAPI + SQLite + curl_cffi (TLS Fingerprinting)
- **Frontend**: Vue 3 + Vite + TailwindCSS
- **Deployment**: Docker + Nginx

---

## 🚀 Lokale Entwicklung

### Backend starten

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# .env erstellen
cp .env.example .env
# Passwort in .env anpassen!

# Server starten
uvicorn app.main:app --reload --port 8000
```

### Frontend starten

```bash
cd frontend
npm install
npm run dev
```

Öffne http://localhost:3000

---

## 🌐 Oracle Cloud Deployment

### 1. Oracle Cloud Account erstellen

1. Gehe zu [cloud.oracle.com](https://cloud.oracle.com)
2. Klick auf "Sign Up" → "Oracle Cloud Free Tier"
3. Registriere dich (Kreditkarte nur zur Verifizierung, wird NICHT belastet)
4. Wähle deine Home Region (Frankfurt empfohlen für DE)

### 2. VM erstellen (Always Free)

1. Gehe zu **Compute → Instances → Create Instance**
2. Konfiguration:
   - **Name**: `audi-ticket-bot`
   - **Image**: Ubuntu 22.04 (oder Canonical Ubuntu)
   - **Shape**: `VM.Standard.A1.Flex` (ARM)
     - OCPUs: 4
     - Memory: 24 GB
   - **Networking**: Create new VCN oder bestehende wählen
   - **SSH Key**: Lade deinen Public Key hoch (`~/.ssh/id_rsa.pub`)
3. Klick **Create**

### 3. Security Rules konfigurieren

1. Gehe zu **Networking → Virtual Cloud Networks**
2. Wähle dein VCN → **Security Lists** → Default Security List
3. Füge **Ingress Rules** hinzu:
   
   | Port | Protokoll | Source |
   |------|-----------|--------|
   | 80   | TCP       | 0.0.0.0/0 |
   | 443  | TCP       | 0.0.0.0/0 |

### 4. Firewall auf der VM öffnen

```bash
# SSH zur VM
ssh ubuntu@<deine-vm-ip>

# iptables Regeln hinzufügen
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

### 5. Docker installieren

```bash
# Docker installieren
curl -fsSL https://get.docker.com | sudo sh

# User zu docker Gruppe hinzufügen
sudo usermod -aG docker ubuntu

# Neu einloggen für Gruppenänderung
exit
ssh ubuntu@<deine-vm-ip>

# Docker Compose installieren
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 6. Projekt deployen

```bash
# Repository klonen
git clone https://github.com/dein-username/audi-ticket-web.git
cd audi-ticket-web

# Environment konfigurieren
cp .env.example .env
nano .env
# APP_PASSWORD und SECRET_KEY setzen!

# Starten
docker-compose up -d --build

# Logs prüfen
docker-compose logs -f
```

### 7. Domain & SSL (Optional aber empfohlen)

#### Option A: DuckDNS (Kostenlose Subdomain)

1. Gehe zu [duckdns.org](https://www.duckdns.org)
2. Logge dich ein und erstelle eine Subdomain (z.B. `audi-tickets`)
3. Trage deine Oracle VM IP ein

```bash
# Auf der VM: DuckDNS Updater einrichten
mkdir -p ~/duckdns
echo 'echo url="https://www.duckdns.org/update?domains=DEINE-SUBDOMAIN&token=DEIN-TOKEN&ip=" | curl -k -o ~/duckdns/duck.log -K -' > ~/duckdns/duck.sh
chmod 700 ~/duckdns/duck.sh

# Cron Job für automatische Updates
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

#### SSL mit Let's Encrypt

```bash
# nginx.conf anpassen - domain setzen
nano nginx/nginx.conf

# Certbot für SSL
docker-compose run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d deine-subdomain.duckdns.org

# HTTPS in nginx.conf aktivieren (Kommentare entfernen)
nano nginx/nginx.conf

# Neustart
docker-compose restart nginx
```

---

## 📱 Mobile Checkout nutzen

1. Starte einen Task auf dem Dashboard
2. Wenn der Bot erfolgreich carted, erscheint ein Checkout-Link
3. Öffne den Link auf deinem iPhone/iPad
4. Der Timer zeigt die verbleibende Zeit
5. Klick "Zur Kasse gehen" um den Kauf abzuschließen

---

## 🔧 Konfiguration

### Environment Variables

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `APP_PASSWORD` | Login-Passwort für Dashboard | `changeme` |
| `SECRET_KEY` | Geheimer Schlüssel für Tokens | - |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL | - |
| `DATABASE_URL` | SQLite Pfad | `sqlite:///./data/tickets.db` |

---

## 📂 Projektstruktur

```
audi-ticket-web/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI Entry
│   │   ├── config.py        # Settings
│   │   ├── database.py      # SQLite
│   │   ├── models.py        # DB Models
│   │   ├── schemas.py       # Pydantic Schemas
│   │   ├── auth.py          # Auth Logic
│   │   ├── api/             # REST Endpoints
│   │   │   ├── auth.py
│   │   │   ├── tasks.py
│   │   │   ├── checkout.py
│   │   │   └── websocket.py
│   │   └── bot/             # Bot Logic
│   │       ├── core.py      # Async Bot
│   │       ├── monitor.py   # Task Manager
│   │       └── discord.py   # Notifications
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/           # Pages
│   │   ├── components/      # UI Components
│   │   └── stores/          # Pinia State
│   ├── package.json
│   └── Dockerfile
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
└── .env.example
```

---

## 🐛 Troubleshooting

### Container startet nicht

```bash
docker-compose logs backend
```

### Keine Verbindung zur VM

1. Security Rules prüfen
2. iptables auf VM prüfen
3. VM läuft? (`sudo systemctl status docker`)

### Bot findet keine Tickets

- URL korrekt? (muss `audidefuehrungen2.regiondo.de` enthalten)
- Event noch verfügbar?

---

## 📄 Lizenz

Private Nutzung. Nicht für kommerzielle Zwecke.
