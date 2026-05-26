FROM python:3.12-alpine

RUN pip install --no-cache-dir \
    google-api-python-client==2.* \
    google-auth-httplib2==0.* \
    google-auth-oauthlib==1.*

COPY forward.py /forward.py
COPY import.py  /import.py
COPY auth.py    /auth.py

# MODE=forward (default) uses SMTP forwarding
# MODE=import            uses Gmail API direct insert (preserves original headers)
CMD ["sh", "-c", "\
  if [ \"${MODE:-forward}\" = \"import\" ]; then \
    while true; do python /import.py; sleep ${INTERVAL_SEC:-600}; done; \
  else \
    while true; do python /forward.py; sleep ${INTERVAL_SEC:-600}; done; \
  fi"]
