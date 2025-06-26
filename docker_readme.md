# Voice Bot Docker Deployment

This guide explains how to deploy the Voice Bot application using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose installed on your system
- Groq API key (for the Llama 3.3 model)

## Setup

1. Create a `.env` file in the project root with your configuration:

```
# Required
GROQ_API_KEY=your_groq_api_key_here

# Database configuration (optional - default values shown)
DB_HOST=db
DB_USER=voicebot
DB_PASSWORD=voicebot_password
DB_NAME=appointments_db
DB_PORT=3306
MYSQL_ROOT_PASSWORD=root_password
```

You can customize any of these database values as needed. If you don't specify them in the .env file, the default values shown above will be used.

2. Build and start the Docker containers:

```bash
docker-compose up -d
```

This will:
- Build the Docker image for the application
- Start the application container and a MySQL database container
- Set up the database with the credentials from your .env file
- Map port 8000 from the container to port 8000 on your host machine
- Create a persistent volume for the database data

3. Access the application at: http://localhost:8000

## Database Information

The application automatically connects to the MySQL database using the configuration from your .env file. The default settings are:
- Host: db (Docker service name)
- Database: appointments_db
- Username: voicebot
- Password: voicebot_password
- Port: 3306

The database data is stored in a Docker volume named `mysql_data` which persists even when containers are stopped or removed.

## Stopping the Application

To stop the application:

```bash
docker-compose down
```

This will stop both the application and database containers but will preserve the database data.

## Completely Removing the Application

If you want to remove everything including the database data:

```bash
docker-compose down -v
```

The `-v` flag removes the volumes as well.

## Viewing Logs

To view the application logs:

```bash
docker-compose logs -f voicebot
```

To view the database logs:

```bash
docker-compose logs -f db
```

## Rebuilding After Changes

If you make changes to the code, rebuild the container:

```bash
docker-compose build
docker-compose up -d
```

## Troubleshooting

### Database Connection Issues

If the application cannot connect to the database:
1. Make sure the database container is running: `docker-compose ps`
2. Check the database logs: `docker-compose logs db`
3. Verify your .env file has the correct database configuration
4. The application has a retry mechanism for database connections

### Audio Transcription Issues

If you encounter issues with the audio transcription inside Docker:
- Ensure your browser has permission to access the microphone
- The audio transcription may work differently in a containerized environment compared to local development

For other issues, check the application logs as described above. 