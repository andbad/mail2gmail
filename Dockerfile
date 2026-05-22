FROM python:3.12-alpine
COPY forward.py /forward.py
CMD ["sh", "-c", "while true; do python /forward.py; sleep ${INTERVAL_SEC:-600}; done"]
