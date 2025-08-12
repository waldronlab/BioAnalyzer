FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy custom Nginx configuration
COPY deployment/nginx/nginx.conf /etc/nginx/nginx.conf

# Create necessary directories
RUN mkdir -p /var/cache/nginx /var/log/nginx /usr/share/nginx/html/error_pages

# Set proper permissions
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Start Nginx
CMD ["nginx", "-g", "daemon off;"] 