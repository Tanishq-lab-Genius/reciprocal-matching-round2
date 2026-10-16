FROM python:3.12.7-slim
WORKDIR /app
COPY reciprocal_matching_policy.py ./
COPY matching_core.py ./
COPY allocation_voi.py ./
COPY directional_learning.py ./
COPY msmi_feedback.py ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65534:65534
ENTRYPOINT ["python", "reciprocal_matching_policy.py"]
