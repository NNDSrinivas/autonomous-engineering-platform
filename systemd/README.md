# NAVI Systemd Services

This directory contains systemd service and timer files for running NAVI background tasks.

## Feedback Analyzer

The feedback analyzer runs periodically to analyze user feedback and generate learning insights.

### Installation

1. **Copy service files to systemd directory:**
```bash
sudo cp systemd/navi-feedback-analyzer.service /etc/systemd/system/
sudo cp systemd/navi-feedback-analyzer.timer /etc/systemd/system/
```

2. **Update environment variables in the service file:**
Edit `/etc/systemd/system/navi-feedback-analyzer.service` and update:
- `DATABASE_URL` - Your PostgreSQL connection string
- `WorkingDirectory` - Path to NAVI installation
- `ExecStart` - Path to Python virtualenv

3. **Create required directories:**
```bash
sudo mkdir -p /var/lib/navi/feedback
sudo mkdir -p /var/log/navi
sudo chown -R navi:navi /var/lib/navi /var/log/navi
```

4. **Enable and start the timer:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable navi-feedback-analyzer.timer
sudo systemctl start navi-feedback-analyzer.timer
```

### Management

**Check timer status:**
```bash
sudo systemctl status navi-feedback-analyzer.timer
```

**List next scheduled runs:**
```bash
sudo systemctl list-timers navi-feedback-analyzer.timer
```

**Run analyzer manually:**
```bash
sudo systemctl start navi-feedback-analyzer.service
```

**View logs:**
```bash
# Live tail
sudo journalctl -u navi-feedback-analyzer.service -f

# Last 100 lines
sudo journalctl -u navi-feedback-analyzer.service -n 100

# Logs since yesterday
sudo journalctl -u navi-feedback-analyzer.service --since yesterday
```

**Stop the timer:**
```bash
sudo systemctl stop navi-feedback-analyzer.timer
```

**Disable the timer:**
```bash
sudo systemctl disable navi-feedback-analyzer.timer
```

### Troubleshooting

**Timer not running:**
```bash
# Check if timer is active
sudo systemctl is-active navi-feedback-analyzer.timer

# Check for errors
sudo systemctl status navi-feedback-analyzer.timer
```

**Service failing:**
```bash
# Check service logs
sudo journalctl -u navi-feedback-analyzer.service -n 50

# Run service manually to see errors
sudo systemctl start navi-feedback-analyzer.service
```

**Change schedule:**
Edit `/etc/systemd/system/navi-feedback-analyzer.timer` and modify the `OnCalendar` line:
```ini
# Every 30 minutes instead of 15
OnCalendar=*:0/30

# Every hour
OnCalendar=hourly

# Daily at 2 AM
OnCalendar=02:00:00
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart navi-feedback-analyzer.timer
```

## Security Notes

The service file includes security hardening:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `PrivateTmp=true` - Isolated /tmp directory
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=true` - No access to user home directories
- Resource limits to prevent runaway processes

Adjust these based on your security requirements.
