# NavraLabs IP & License Enforcement Playbook

## Purpose

To protect the Autonomous Engineering Platform (AEP) intellectual property and enforce license terms.

---

## 1. Identify Violation

Check for:
- **Unauthorized public deployment** - ANY hosting of AEP or derivatives (even if free)
- **Published apps or websites** - Clones deployed on domains, cloud platforms, or app stores
- **Rebranded or white-labeled services** - Using AEP code under different branding
- **Code copying without attribution** - Substantial code reuse without proper license compliance
- **Commercial monetization** - Selling, licensing, or offering AEP-based services
- **Fork-and-deploy** - Public GitHub forks that are actively deployed/hosted
- **Trademark violations** - Using "NavraLabs", "AEP", or similar marks

### Detection Methods:
- **GitHub Search**: Search for forks and monitor for deployments
  ```
  site:github.com "Autonomous Engineering Platform" OR "AEP"
  ```
- **Google Dorks**: Find deployed instances
  ```
  inurl:"/api/context/pack" OR inurl:"/api/memory"
  "NavraLabs" OR "Autonomous Engineering"
  ```
- **Domain Monitoring**: Check WHOIS for similar domains
- **Cloud Detection**: Search AWS, Azure, GCP marketplaces for clones
- **Social Media**: Monitor Twitter, LinkedIn, Reddit for launches

---

## 2. Document Evidence

Capture:
- GitHub repo URL
- Domain or service URL
- Screenshots of cloned UI or code reuse
- API endpoints or commit logs proving derivation
- WHOIS info or business details

---

## 3. Send Notice

Use this template:

**Subject:** Unauthorized Use of NavraLabs Software and Trademarks

> Dear [Name or Organization],
>
> We have identified unauthorized use of NavraLabs' proprietary software ("Autonomous Engineering Platform").
> Your repository/service [URL] violates our Business Source License (BSL) by [describe action].
>
> Please remove or make your repository private immediately. Failure to comply within 72 hours will result
> in a DMCA takedown request and potential legal escalation.
>
> Regards,  
> **NavraLabs Legal Team**  
> legal@navralabs.ai

---

## 4. GitHub DMCA Process

Submit a formal takedown at:  
[https://github.com/contact/dmca](https://github.com/contact/dmca)

Use wording:
> "The infringing repository at [URL] violates NavraLabs' copyright and Business Source License 1.1.
> 
> The repository contains substantial portions of the Autonomous Engineering Platform (AEP), which is proprietary software owned by NavraLabs, Inc. (Copyright © 2025).
> 
> **Specific violations:**
> - Unauthorized public deployment of BSL-licensed software
> - Commercial use prohibited under BSL 1.1 without written agreement
> - Code copied from https://github.com/NNDSrinivas/autonomous-engineering-platform
> 
> **Evidence:** [Include screenshots, commit hashes, file comparisons]
> 
> I have a good faith belief that the use of the material is not authorized by the copyright owner, its agent, or the law.
> 
> I swear, under penalty of perjury, that the information in this notification is accurate and that I am authorized to act on behalf of the copyright owner.
> 
> **Requested Action:** Immediate takedown of the repository and all forks."

---

## 5. Hosting Provider Takedown

If deployed on cloud platforms, send abuse reports:

**AWS:**
- Email: abuse@amazonaws.com
- Include: Instance IP, URL, evidence of BSL violation

**Azure:**
- Portal: https://www.microsoft.com/concern/dmca
- Include: Resource details, copyright violation proof

**GCP:**
- Form: https://support.google.com/legal/troubleshooter/1114905
- Include: Project ID if known, deployment URL

**Vercel/Netlify/Heroku:**
- Support ticket with DMCA notice
- Reference BSL 1.1 commercial use prohibition

---

## 6. Automated Detection & Prevention

### GitHub Fork Monitoring (Setup Required)

Create a GitHub Action to monitor forks:

```yaml
# .github/workflows/fork-monitor.yml
name: Monitor Forks
on:
  schedule:
    - cron: '0 0 * * *'  # Daily
jobs:
  check-forks:
    runs-on: ubuntu-latest
    steps:
      - name: Check for deployed forks
        run: |
          # Script to check forks for deployments
          # Alert if detected
```

### License Verification Server

Add to your app (optional):
```python
# backend/core/license_check.py
import os
import requests

def verify_license_compliance():
    """Check if deployment is authorized"""
    license_key = os.getenv("NAVRALABS_LICENSE_KEY")
    if not license_key:
        # Log unauthorized deployment
        requests.post(
            "https://license.navralabs.com/report",
            json={"unauthorized": True, "ip": get_server_ip()}
        )
        raise Exception("Unauthorized deployment - license required")
```

---

## 7. Escalation

If the offender is a company or funded startup:
- Forward to legal@navralabs.ai
- Notify their hosting provider (AWS, Azure, GCP)
- Issue trademark enforcement letter if using AEP/brand name

---

## 8. Legal Contact

- **NavraLabs Legal & IP Enforcement**
  - Email: legal@navralabs.ai
  - Founder: NagaDurga S. Nidamanuri  
  - Registered: United States  
  - Trademark filings: "Autonomous Engineering Platform", "NavraLabs", "AEP"

---

*This playbook ensures you can act swiftly and legally to protect your IP.*
