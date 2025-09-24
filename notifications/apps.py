from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'

    def ready(self):
        """
        This method is called when the app is ready.
        We import our signals here to connect them.
        """
        import notifications.signals