# 🛠️ HP PAVILION: UBUNTU SERVER 24.04 LTS PROVISIONING GUIDE
**Role:** Worker Node 2 / Stream Compute & Kafka Cluster (Layer 4)  
**Target Architecture:** Headless Linux, Native Docker Engine, Tailscale Zero-Trust Mesh

---

## Step 1: Flash the USB Installer on your Lenovo Yoga

1. **Install Rufus (if not already installed):**
   ```powershell
   winget install Rufus.Rufus
   ```
2. **Download the Ubuntu Server 24.04 LTS ISO:**
   * Direct ISO Link: [https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso](https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso)
   * Size: ~2.6 GB
3. **Burn with Rufus:**
   * Plug in USB Flash Drive (8 GB+).
   * Open **Rufus**.
   * Under **Device**, select your USB stick.
   * Under **Boot selection**, choose `ubuntu-24.04-live-server-amd64.iso`.
   * Partition scheme: **GPT** | Target system: **UEFI (non-CSM)**.
   * Click **START** (Choose *Write in ISO Image mode* if prompted).

---

## Step 2: Boot & Install on the HP Pavilion

1. Insert the flashed USB drive into the HP Pavilion.
2. Power on the Pavilion and immediately tap **F9** repeatedly to open the **Boot Device Options** menu (or tap **ESC** $\rightarrow$ **F9**).
3. Select your **USB Flash Drive (UEFI)** and press Enter.
4. Follow the on-screen installer prompts:
   * **Language & Keyboard:** Default / English.
   * **Installation Type:** **Ubuntu Server (default)** (do not install Desktop GUI).
   * **Network Connections:** Connect via Ethernet cable to the TP-Link router (preferred) or select your Wi-Fi SSID.
   * **Storage Configuration:** Use an entire disk (Guided storage configuration).
   * **Profile Setup:**
     * Your Name: `rahshaunchambers` (or `rocky`)
     * Server Name: `qf-pavilion-worker`
     * Username: `quant` (or your preferred user)
     * Password: `SET_A_SECURE_PASSWORD`
   * **SSH Setup:** Check the box for **[X] Install OpenSSH server** (Essential for headless remote access).
   * **Featured Server Snaps:** Leave unselected (we will install Docker engine natively).
   * Select **Reboot Now** when finished and remove the USB drive.

---

## Step 3: Zero-Trust Mesh Joining (Tailscale)

Once the Pavilion boots to the login prompt:
1. Log in with your username and password.
2. Install and activate **Tailscale**:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh
   ```
3. Follow the authentication URL printed on screen to link the Pavilion to your Tailscale mesh account.
4. Run `tailscale ip -4` to get the Pavilion's Mesh IP (e.g., `100.x.y.z`).

From this point forward, you can disconnect the monitor/keyboard and control the Pavilion headlessly from your Yoga laptop:
```powershell
ssh quant@qf-pavilion-worker
```

---

## Step 4: Docker Engine & Layer 4 Kafka Deployment

On the HP Pavilion (via SSH or console):

1. **Install Official Docker Engine:**
   ```bash
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg

   echo \
     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
     $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
     sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo usermod -aG docker $USER
   ```

2. **Deploy the Layer 4 Kafka Cluster:**
   ```bash
   git clone https://github.com/your-org/mycelium.git
   cd mycelium
   docker compose -f docker-compose.kafka.yml up -d
   ```

3. **Verify Kafka Broker Live on Mesh:**
   * Kafka Broker: `100.x.y.z:9092`
   * Kafka UI: `http://100.x.y.z:8080` (or `http://100.x.y.z:8085`)
