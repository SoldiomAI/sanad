---
title: SANAD Gemini Media Forensics
emoji: 🛡️
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
---

# SANAD Gemini media worker

Private-by-authentication analysis worker for SANAD Verify. The public health
route exposes capability metadata only. `/analyze` accepts bounded media bytes
only after validating the exact Vercel production OIDC identity.

