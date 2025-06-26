@echo off
echo Building and starting Docker container...
docker-compose down
docker-compose build
docker-compose up -d
echo.
echo Container is now running.
echo Access the application at:
echo   HTTP:  http://localhost:8000
echo   HTTPS: https://localhost:8443 (after enabling in docker-compose.yml)
echo.
echo To view logs: docker-compose logs -f
echo To stop: docker-compose down
echo. 