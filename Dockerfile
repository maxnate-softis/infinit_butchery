# Infinit Butchery App - Dockerfile
# This extends the base ERPNext image with the butchery app

FROM frappe/erpnext:v15

# Copy the app to the apps directory
COPY . /home/frappe/frappe-bench/apps/infinit_butchery

# Install the app
RUN cd /home/frappe/frappe-bench && \
    bench get-app file:///home/frappe/frappe-bench/apps/infinit_butchery --skip-assets && \
    bench build --app infinit_butchery
