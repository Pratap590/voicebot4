# Setting up HTTPS for Voice Assistant

To allow microphone access in browsers when deployed in Docker or on AWS, the application needs to run over HTTPS.

## Local Development with Docker

1. Generate self-signed certificates:
   ```bash
   chmod +x generate_certs.sh
   ./generate_certs.sh
   ```

2. Start the Docker container:
   ```bash
   docker-compose up -d
   ```

3. Access the app at:
   - HTTP: http://localhost:8000
   - HTTPS: https://localhost:8443 (use this for microphone access)

4. When accessing via HTTPS with self-signed certificates, you'll need to:
   - Accept the security warning in your browser
   - Grant microphone permissions when prompted

## Production Deployment on AWS

For production deployment on AWS:

1. Obtain proper SSL certificates (options include):
   - AWS Certificate Manager (for use with AWS services)
   - Let's Encrypt for free certificates
   - Commercial SSL providers

2. Replace the self-signed certificates in the `certs` folder with your production certificates.

3. Ensure your domain name points to your AWS instance and that your security groups allow traffic on port 8443.

4. Set environment variables when deploying:
   ```bash
   USE_HTTPS=true
   SSL_CERTFILE=/path/to/cert.pem
   SSL_KEYFILE=/path/to/key.pem
   ```

## Troubleshooting

- If microphone access is still blocked, check browser console for errors
- Ensure you're accessing the app via HTTPS://
- Check that your certificates are valid and trusted by your browser
- On AWS, ensure your security groups allow traffic on port 8443 