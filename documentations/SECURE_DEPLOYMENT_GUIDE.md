# Secure Deployment Guide - Organization-Only Access

## Overview
Deploy your WhatsApp Dashboard so only your organization can access it, with multiple security layers.

## Security Layers

### Layer 1: IP Whitelist (Recommended)
Only allow access from your organization's IP addresses.

### Layer 2: VPN/Private Network
Deploy on a private network accessible only via VPN.

### Layer 3: Strong Authentication
Use the built-in user authentication with strong passwords.

### Layer 4: Firewall Rules
Configure firewall to block unauthorized access.

---

## Deployment Options

### Option 1: Deploy with IP Whitelist (Best for Small Teams)

#### Using Nginx as Reverse Proxy

**Step 1: Install Nginx**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx
```

**Step 2: Configure Nginx with IP Whitelist**

Create `/etc/nginx/sites-available/whatsapp-dashboard`:

```nginx
# IP Whitelist - Only allow your organization's IPs
geo $allowed_ip {
    default 0;
    
    # Add your organization's IP addresses
    123.45.67.89 1;        # Office IP
    98.76.54.32 1;         # Secondary office
    11.22.33.44/24 1;      # IP range
    
    # Add more IPs as needed
}

server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # IP Whitelist Check
    if ($allowed_ip = 0) {
        return 403 "Access denied - Organization network only";
    }
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000" always;
    
    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
    
    location /login {
        limit_req zone=login burst=2;
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Step 3: Enable Configuration**
```bash
sudo ln -s /etc/nginx/sites-available/whatsapp-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Step 4: Setup SSL (Let's Encrypt)**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

### Option 2: Deploy with VPN (Best for Remote Teams)

#### Option 2A: Using Tailscale (Easiest)

**Step 1: Install Tailscale on Server**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

**Step 2: Share Access**
1. Go to Tailscale admin console
2. Share your server with team members
3. Team members install Tailscale on their devices
4. Access via Tailscale IP: `http://100.x.x.x:5000`

**Benefits:**
- Zero configuration
- Works from anywhere
- Encrypted by default
- No need for domain or SSL

#### Option 2B: Using WireGuard VPN

**Step 1: Install WireGuard on Server**
```bash
sudo apt install wireguard
```

**Step 2: Generate Keys**
```bash
wg genkey | tee server_private.key | wg pubkey > server_public.key
```

**Step 3: Configure WireGuard** (`/etc/wireguard/wg0.conf`)
```ini
[Interface]
PrivateKey = <SERVER_PRIVATE_KEY>
Address = 10.0.0.1/24
ListenPort = 51820

# Client 1
[Peer]
PublicKey = <CLIENT1_PUBLIC_KEY>
AllowedIPs = 10.0.0.2/32

# Client 2
[Peer]
PublicKey = <CLIENT2_PUBLIC_KEY>
AllowedIPs = 10.0.0.3/32
```

**Step 4: Start WireGuard**
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

**Step 5: Configure Firewall**
```bash
# Only allow VPN network to access Flask
sudo ufw allow 51820/udp  # WireGuard port
sudo ufw allow from 10.0.0.0/24 to any port 5000
sudo ufw deny 5000  # Block public access
```

---

### Option 3: Cloud Deployment with Security Groups

#### AWS Deployment

**Step 1: Launch EC2 Instance**
```bash
# Choose Ubuntu Server 20.04 LTS
# Instance type: t2.small (or larger)
```

**Step 2: Configure Security Group**
```
Inbound Rules:
- SSH: Port 22, Source: Your IP only
- HTTPS: Port 443, Source: Your organization IPs only
- Custom TCP: Port 5000, Source: 127.0.0.1/32 (localhost only)

Outbound Rules:
- All traffic allowed (for Shopify webhooks, WhatsApp API)
```

**Step 3: Setup Application**
```bash
# SSH into server
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv nginx git

# Clone your repo
git clone <your-repo>
cd whatsapp-dashboard

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure .env file
nano .env
# Add your credentials
```

**Step 4: Run with Gunicorn**
```bash
pip install gunicorn

# Create systemd service
sudo nano /etc/systemd/system/whatsapp-dashboard.service
```

```ini
[Unit]
Description=WhatsApp Dashboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/whatsapp-dashboard
Environment="PATH=/home/ubuntu/whatsapp-dashboard/venv/bin"
ExecStart=/home/ubuntu/whatsapp-dashboard/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable whatsapp-dashboard
sudo systemctl start whatsapp-dashboard
```

**Step 5: Configure Nginx (use config from Option 1)**

---

### Option 4: Docker Deployment with Private Network

**Step 1: Create Dockerfile**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

**Step 2: Create docker-compose.yml**
```yaml
version: '3.8'

services:
  whatsapp-dashboard:
    build: .
    ports:
      - "127.0.0.1:5000:5000"  # Only bind to localhost
    volumes:
      - ./whatsapp_dashboard.db:/app/whatsapp_dashboard.db
      - ./.env:/app/.env
    restart: unless-stopped
    networks:
      - internal

networks:
  internal:
    driver: bridge
```

**Step 3: Deploy**
```bash
docker-compose up -d
```

---

## Additional Security Measures

### 1. Update .env for Production

```bash
# .env file
SECRET_KEY=<generate-strong-random-key>  # Use: python -c "import secrets; print(secrets.token_hex(32))"

# WhatsApp API
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WABA_ID=your_waba_id

# Webhook (use your public domain)
WEBHOOK_VERIFY_TOKEN=<strong-random-token>

# Shopify
SHOPIFY_SHOP_NAME=your-store
SHOPIFY_ACCESS_TOKEN=your_token

# Rate limiting
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW=1.0
MESSAGE_QUEUE_WORKERS=2
```

### 2. Add IP-based Login Restrictions to Code

Add this to `app.py`:

```python
# At the top with other imports
ALLOWED_IPS = os.getenv('ALLOWED_IPS', '').split(',')

# Before @app.route("/login")
def check_ip_whitelist():
    client_ip = request.headers.get('X-Real-IP') or request.remote_addr
    if ALLOWED_IPS and client_ip not in ALLOWED_IPS:
        logger.warning(f"Access denied from IP: {client_ip}")
        abort(403, "Access denied - Organization network only")

# In login route
@app.route("/login", methods=["GET", "POST"])
def login():
    check_ip_whitelist()
    # ... rest of login code
```

Add to `.env`:
```
ALLOWED_IPS=123.45.67.89,98.76.54.32
```

### 3. Enable HTTPS Everywhere

```bash
# Force HTTPS in Flask
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

### 4. Setup Monitoring

```bash
# Install fail2ban to block brute force
sudo apt install fail2ban

# Configure for Flask
sudo nano /etc/fail2ban/jail.local
```

```ini
[whatsapp-dashboard]
enabled = true
port = 443
filter = whatsapp-dashboard
logpath = /var/log/nginx/access.log
maxretry = 5
bantime = 3600
```

### 5. Regular Security Updates

```bash
# Create update script
#!/bin/bash
cd /home/ubuntu/whatsapp-dashboard
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart whatsapp-dashboard
```

---

## Quick Start Deployment (Recommended)

**For small teams with static office IP:**

1. **Get a domain**: Register a domain (e.g., dashboard.yourcompany.com)

2. **Deploy on DigitalOcean/AWS:**
   ```bash
   # One-click Ubuntu droplet
   # SSH in and run:
   curl -L https://raw.githubusercontent.com/yourusername/whatsapp-dashboard/main/deploy.sh | bash
   ```

3. **Configure IP whitelist in Nginx** (see Option 1)

4. **Setup SSL with Certbot**

5. **Share credentials** with team members

**Estimated time:** 30 minutes  
**Cost:** $5-10/month (small VPS)

---

## Testing Access Control

### Test IP Whitelist
```bash
# From allowed IP (should work)
curl https://yourdomain.com

# From blocked IP (should get 403)
curl https://yourdomain.com
```

### Test VPN Access
```bash
# Without VPN (should timeout or be blocked)
curl http://your-server-ip:5000

# With VPN connected (should work)
curl http://10.0.0.1:5000
```

---

## Troubleshooting

### Issue: Can't access from organization IP

1. Check your public IP:
   ```bash
   curl ifconfig.me
   ```

2. Verify it's in Nginx whitelist

3. Check Nginx logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Issue: Webhooks not working after deployment

1. Update webhook URLs in Shopify to your public domain
2. Make sure Shopify can reach your server (don't block Shopify IPs)
3. Check webhook logs in Shopify admin

### Issue: SSL certificate errors

```bash
# Renew certificate
sudo certbot renew
sudo systemctl restart nginx
```

---

## Cost Comparison

| Option | Monthly Cost | Setup Time | Security Level |
|--------|-------------|------------|----------------|
| VPS + IP Whitelist | $5-10 | 30 min | High |
| VPS + Tailscale | $5-10 | 15 min | Very High |
| AWS EC2 | $10-20 | 1 hour | High |
| Self-hosted + VPN | $0 | 2 hours | Very High |

---

## Recommended Setup for Most Organizations

**Best Balance of Security, Cost, and Ease:**

1. DigitalOcean Droplet ($6/month)
2. Tailscale VPN (Free for up to 20 users)
3. Built-in user authentication
4. HTTPS with Let's Encrypt

**Total Time:** 20 minutes  
**Total Cost:** $6/month  
**Security:** ✅ Very High

Would you like me to create a step-by-step deployment script for your preferred option?
