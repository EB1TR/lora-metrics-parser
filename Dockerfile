FROM python:3.12.7-alpine3.20

RUN rm -rf /root/.cache && rm -rf /var/cache/apk/*              \
    && find /                                                   \
        \( -type d -a -name test -o -name tests \)              \
        -o \( -type f -a -name '*.pyc' -o -name '*.pyo' \)      \
        -exec rm -rf '{}' +                                     \
    && mkdir /app && mkdir /app/log

WORKDIR /app
COPY . /app

RUN pip install --ignore-installed --no-cache-dir -r requirements.txt

ENTRYPOINT ["python3"]
CMD ["-u", "app.py"]