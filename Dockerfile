ARG PYTHON_IMAGE=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

ARG http_proxy
ARG https_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG no_proxy
ARG NO_PROXY
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PIP_FALLBACK_INDEX_URL=https://pypi.org/simple

COPY requirements.txt /app/
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} --trusted-host mirrors.aliyun.com -r requirements.txt \
    || pip install --no-cache-dir -i ${PIP_FALLBACK_INDEX_URL} -r requirements.txt

COPY . /app/
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/data /app/staticfiles

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "appointments.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
