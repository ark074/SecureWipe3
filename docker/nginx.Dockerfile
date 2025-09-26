# docker/nginx.Dockerfile
FROM nginx:stable
COPY ./frontend /usr/share/nginx/html
COPY ./docker/nginx.conf /etc/nginx/conf.d/default.conf
