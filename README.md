# Craft Application
The Craft application is a comprehensive platform that integrates multiple functionalities, including a social app, e-commerce app, courses app, and chat app. This extensive project features over 150 endpoints, ensuring seamless interaction and data flow between its various components. The application includes three distinct interfaces: Customer, Crafter, and Delivery, each tailored to meet the specific needs and workflows of its users.

## Table of Contents
- [Features](#features)
- [Endpoints](#endpoints)
- [Interfaces](#interfaces)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [Contact](#contact)

## Features
- **Social App**: Connect with other users, share updates, and follow each other's activities.
- **E-commerce App**: Browse and purchase products, manage orders, and handle payments.
- **Courses App**: Access and enroll in various courses, track progress, and receive certifications.
- **Chat App**: Communicate with other users through real-time messaging.

## Endpoints
This project features over 150 endpoints, ensuring seamless interaction and data flow between its various components. These endpoints are designed to handle a wide range of functionalities, from user authentication and profile management to order processing and real-time communication.

## Interfaces
The application includes three distinct interfaces, each tailored to meet the specific needs and workflows of its users:
- **Customer**: A user-friendly interface for customers to browse products, enroll in courses, and interact with other users.
- **Crafter**: A specialized interface for crafters to publish Courses, manage their products, track orders, and engage with customers.
- **Delivery**: A streamlined interface for delivery personnel to manage deliveries and update order statuses.

## Installation
To install and run the Craft application locally, follow these steps:

1. Clone the repository:
    ```sh
    git clone https://github.com/Waleeddarwesh/Craft.git
    ```
2. Set Up a Virtual Environment
Create and activate a virtual environment:
    ```sh
    pip install virtualenv
    virtualenv venv
    cd Craft
    cd venv
    Scripts/activate
    cd..
    ```
3. Navigate to the project directory:
    ```sh
    cd Handcrafts
    ```

4. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

5. Apply the migrations:
    ```sh
    python manage.py migrate
    ```

6. Create a superuser:
    ```sh
    python manage.py createsuperuser
    ```

7.Configure Django Settings:
   - Open your `settings.py` file and configure the `DATABASES` setting to use PostgreSQL:
     ```sh
     DATABASES = {
         'default': {
             'ENGINE': 'django.db.backends.postgresql',
             'NAME': 'swiftride_db',
             'USER': 'swiftride_user',
             'PASSWORD': 'your_password',
             'HOST': 'localhost',
             'PORT': '5432',
         }
     }
     ```
  - Configure Keys and Secrets:
    - Open `settings.py` and add your configuration details:
    ```python
    # STRIPE
    STRIPE_SECRET_KEY = 'your_stripe_secret_key'
    STRIPE_PUBLISHABLE_KEY = 'your_stripe_publishable_key'
    STRIPE_WEBHOOK_SECRET = 'your_stripe_webhook_secret'

    # GOOGLE
    GOOGLE_CLIENT_ID = 'your_google_client_id'
    GOOGLE_CLIENT_SECRET = 'your_google_client_secret'

    # SOCIAL AUTHENTICATION
    SOCIAL_AUTH_PASSWORD = 'your_social_auth_password'
    SOCIAL_AUTH_FACEBOOK_KEY = 'your_facebook_key'
    SOCIAL_AUTH_FACEBOOK_SECRET = 'your_facebook_secret'

    # EMAIL
    EMAIL_HOST = 'sandbox.smtp.mailtrap.io'
    EMAIL_HOST_USER = 'your_email_host_user'
    EMAIL_HOST_PASSWORD = 'your_email_host_password'
    EMAIL_PORT = '587'
    ```

    - You can find your Stripe API keys in your Stripe Dashboard under the Developers section.
    - Obtain Google Client ID and Client Secret from the Google Developers Console.
    - Use the Mailtrap credentials for testing email functionality. For production, replace with your email service provider’s credentials.


8. Run the development server:
    ```sh
    python manage.py runserver
    ```

## Usage
Access the Swagger documentation to view all endpoints and their details:
- **Documentation**: [http://localhost:8000/docs/](http://localhost:8000/docs/)

## Contributing
We welcome contributions to the Craft application! If you would like to contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix:
    ```sh
    git checkout -b your-feature-branch
    ```

3. Make your changes and commit them:
    ```sh
    git commit -m "Description of your changes"
    ```

4. Push your changes to your fork:
    ```sh
    git push origin your-feature-branch
    ```

5. Create a pull request with a detailed description of your changes.

## Contact
For any questions or inquiries, please contact:
- Name: [Waleed Darwesh]
- Email: [Waleeddarwesh2002@gmail.com]
